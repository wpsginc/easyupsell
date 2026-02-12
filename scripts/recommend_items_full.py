#!/usr/bin/env python3
"""
Full Category → Item Recommendation Analysis

For each high-traffic source category, find high-value ITEMS to recommend.
Includes full business metrics for human review:
- Source category sales (orders, revenue)
- Recommended item sales (how well does it sell?)
- LLM validation (does pairing make sense?)

Usage:
    python scripts/recommend_items_full.py --limit 50
    python scripts/recommend_items_full.py --top-categories 30 --items-per-category 8

Output: Excel (.xlsx) with per-category tabs
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce import BigCommerceClient
from bigquery_client import BigQueryClient
from config import settings
from enrichment import EnrichmentService

# Import LLM validation
sys.path.insert(0, str(Path(__file__).parent))
from validate_category_pairings import get_llm_validation, get_batch_llm_validation

console = Console()


def _extract_netsuite_id(bpn: str) -> str:
    """Extract NetSuite Internal ID from bin_picking_number (first comma-separated value)."""
    if not bpn or not bpn.strip():
        return ""
    return bpn.split(",")[0].strip()

def get_processed_categories(output_path: Path) -> set[str]:
    """Get list of categories already processed in the output CSV."""
    if not output_path.exists():
        return set()
    
    processed = set()
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("source_category"):
                    processed.add(row["source_category"])
    except Exception:
        pass
        
    return processed


def get_order_data(bc_client: BigCommerceClient, months: int = 6) -> tuple[dict, dict, dict]:
    """
    Analyze order history to get:
    1. Category sales: category_id -> {order_count, revenue}
    2. Item sales: product_id -> {order_count, units_sold, revenue}
    3. Product categories: product_id -> [category_ids]
    """
    print(f"Analyzing {months} months of order history...")
    
    min_date = datetime.now() - timedelta(days=months * 30)
    min_date_str = min_date.strftime("%a, %d %b %Y 00:00:00 +0000")
    
    # Get orders
    try:
        orders = bc_client.get_orders(min_date=min_date_str, status_id=11)  # Completed
        orders.extend(bc_client.get_orders(min_date=min_date_str, status_id=10))  # Shipped
    except Exception as e:
        print(f"  ⚠️ Could not fetch orders: {e}")
        return {}, {}, {}
    
    print(f"  Found {len(orders)} orders")
    
    category_sales = defaultdict(lambda: {"order_count": 0, "revenue": 0.0})
    item_sales = defaultdict(lambda: {"order_count": 0, "units_sold": 0, "revenue": 0.0})
    product_categories = {}
    
    # Sample orders for analysis
    sample_size = min(300, len(orders))
    
    for i, order in enumerate(orders[:sample_size]):
        try:
            products = bc_client.get_order_products(order["id"])
            for p in products:
                product_id = p.get("product_id")
                qty = p.get("quantity", 1)
                price = float(p.get("base_price", 0)) * qty
                
                # Item-level sales
                item_sales[product_id]["order_count"] += 1
                item_sales[product_id]["units_sold"] += qty
                item_sales[product_id]["revenue"] += price
                
                # Get category for this product
                if product_id and product_id not in product_categories:
                    try:
                        prod = bc_client.get_product(product_id)
                        product_categories[product_id] = prod.get("categories", [])
                    except:
                        product_categories[product_id] = []
                
                # Category-level sales
                for cat_id in product_categories.get(product_id, []):
                    category_sales[cat_id]["order_count"] += 1
                    category_sales[cat_id]["revenue"] += price
                    
        except Exception:
            continue
        
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{sample_size} orders...")
            sleep(0.1)
    
    print(f"  Sales data: {len(category_sales)} categories, {len(item_sales)} items")
    return dict(category_sales), dict(item_sales), product_categories


def get_top_categories_by_sales(
    bc_client: BigCommerceClient,
    category_sales: dict,
    limit: int = 30,
    use_cache: bool = True,
) -> list[dict]:
    """Get top categories by order volume, excluding meta-categories."""
    cats = bc_client.get_categories(use_cache=use_cache)
    
    # Build parent set
    parent_ids = set(c.get("parent_id", 0) for c in cats)
    
    # Exclude patterns
    excluded = ["$", "sale", "clearance", "promo", "new arrival", "gift", "shop all", 
                "featured", "hot", "best seller"]
    
    # Score categories
    scored = []
    for c in cats:
        cat_id = c["id"]
        name = c.get("name", "")
        name_lower = name.lower()
        
        # Skip: root, meta, excluded patterns
        if c.get("parent_id", 0) == 0:
            continue
        if any(ex in name_lower for ex in excluded):
            continue
        
        sales = category_sales.get(cat_id, {})
        order_count = sales.get("order_count", 0)
        revenue = sales.get("revenue", 0)
        
        scored.append({
            "id": cat_id,
            "name": name,
            "parent_id": c.get("parent_id", 0),
            "order_count": order_count,
            "revenue": round(revenue, 2),
            "is_leaf": cat_id not in parent_ids,
        })
    
    # Sort by order count
    scored.sort(key=lambda x: -x["order_count"])
    
    return scored[:limit]


def get_high_value_items_with_sales(
    bc_client: BigCommerceClient,
    item_sales: dict,
    product_categories: dict,
    limit: int = 300,
    priority_brands: list[str] = None,
    use_cache: bool = True,
) -> list[dict]:
    """
    Get high-value items that make good upsell candidates.
    Include sales data for each item.
    Priority brands are boosted to ensure inclusion.
    """
    # Known high-performing add-on brands
    priority_brands = priority_brands or [
        "streamlight", "benchmade", "channellock", "pelican", 
        "gerber", "leatherman", "5.11", "blackinton"
    ]
    
    print("Fetching high-value item candidates...")
    
    products = bc_client.get_products(limit=2000, use_cache=use_cache)  # Get more products
    
    priority_items = []
    regular_items = []
    
    for p in products:
        price = float(p.get("price", 0) or 0)
        product_id = p["id"]
        name = p.get("name", "")
        
        # Good upsell = $15-200, visible
        if 15 <= price <= 200 and p.get("is_visible", True):
            sales = item_sales.get(product_id, {})
            
            item = {
                "id": product_id,
                "sku": p.get("sku", ""),
                "name": name[:60],
                "price": price,
                "categories": p.get("categories", []),
                "inventory": p.get("inventory_level", 0),
                # Sales metrics
                "order_count": sales.get("order_count", 0),
                "units_sold": sales.get("units_sold", 0),
                "revenue": round(sales.get("revenue", 0), 2),
                # NetSuite ID from bin_picking_number (always on parent product)
                "netsuite_id": _extract_netsuite_id(p.get("bin_picking_number", "")),
            }
            
            # Check if priority brand
            name_lower = name.lower()
            is_priority = any(brand in name_lower for brand in priority_brands)
            
            if is_priority:
                priority_items.append(item)
            else:
                regular_items.append(item)
    
    # Sort each by sales
    priority_items.sort(key=lambda x: (-x["order_count"], abs(x["price"] - 50)))
    regular_items.sort(key=lambda x: (-x["order_count"], abs(x["price"] - 50)))
    
    # Ensure priority brands are included (at least 50% of limit)
    priority_limit = min(len(priority_items), limit // 2)
    regular_limit = limit - priority_limit
    
    candidates = priority_items[:priority_limit] + regular_items[:regular_limit]
    
    print(f"  Found {len(priority_items)} priority brand items, {len(regular_items)} regular")
    print(f"  Selected: {priority_limit} priority + {regular_limit} regular = {len(candidates)}")
    return candidates


def find_recommendations_for_category(
    category: dict,
    all_items: list[dict],
    id_to_name: dict,
    enrichment_service: EnrichmentService,
    provider: str = "azure",
    max_items: int = 8,
) -> list[dict]:
    """
    Find best item recommendations for a category.
    - Prioritize proven sellers (high order count)
    - Allow items that share categories (flashlights in Helmets are still good cross-sells)
    - LLM validates the pairing
    """
    category_id = category["id"]
    category_name = category["name"]
    category_name_lower = category_name.lower()
    
    from candidate_filter import filter_candidates
    eligible_items = filter_candidates(category, all_items)
    
    # Sort by sales (proven sellers first)
    eligible_items.sort(key=lambda x: -x.get("order_count", 0))
    
    # Pick top sellers with diversity
    selected = []
    seen_names = set()  # Avoid duplicates by name prefix
    
    for item in eligible_items:
        # Unique by first 3 words of name
        name_key = " ".join(item["name"].lower().split()[:3])
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        selected.append(item)
        if len(selected) >= max_items:
            break
    
    # Validate with LLM in batch (much faster - single prompt processing)
    batch_items = []
    
    # Pre-fetch category co-purchase stats for efficient lookup
    cat_id = category["id"]
    cat_recs = enrichment_service.category_map.get(cat_id, [])
    # Create lookup map by SKU for O(1) access
    stats_by_sku = {r.get("rec_sku"): r for r in cat_recs if r.get("rec_sku")}

    for item in selected:
        sku = item.get("sku", "")
        stats = stats_by_sku.get(sku, {})
        
        copurchase_count = stats.get("copurchase_count", 0)
        margin = stats.get("rec_margin")
        velocity = stats.get("rec_velocity")
        
        item_data = {
            "name": item["name"], 
            "sku": sku, 
            "brand": item.get("brand", ""),
            "price": item.get("price"),
        }
        
        if copurchase_count > 0:
            item_data["copurchase_text"] = f"Co-purchased with '{category_name}': {copurchase_count} times"
        
        if margin is not None:
            item_data["margin_pct"] = margin
            
        if velocity is not None:
             item_data["velocity_text"] = f"Velocity: {velocity} units/90d"
             
        batch_items.append(item_data)
    
    try:
        batch_results = get_batch_llm_validation(
            category_name, 
            batch_items, 
            provider=provider,
            max_items=settings.MAX_BATCH_SIZE,  # Process up to 50 at a time
        )
    except Exception as e:
        print(f"    Batch validation error: {e}")
        batch_results = [{"valid": None, "reason": f"Batch error: {e}"} for _ in selected]
    
    # Build recommendations from batch results
    recommendations = []
    for i, item in enumerate(selected):
        result = batch_results[i] if i < len(batch_results) else {"valid": None}
        
        # Get item's category names
        item_cat_names = [id_to_name.get(c, "") for c in item["categories"][:2]]
        
        # Get enrichment stats again
        stats = stats_by_sku.get(item.get("sku", ""), {})
        
        recommendations.append({
            # Source category
            "source_category": category_name,
            "src_orders_6mo": category["order_count"],
            "src_revenue_6mo": category["revenue"],
            
            # Recommended item
            "recommended_sku": item["sku"],
            "recommended_name": item["name"],
            "recommended_price": item["price"],
            "recommended_categories": " | ".join(filter(None, item_cat_names)),
            "recommended_netsuite_id": item.get("netsuite_id") or stats.get("rec_netsuite_id", ""),
            "same_category": item.get("same_category", False),
            
            # Item sales
            "item_orders_6mo": item["order_count"],
            "item_units_6mo": item["units_sold"],
            "item_revenue_6mo": item["revenue"],
            
            # Enrichment
            "copurchase_count": stats.get("copurchase_count", 0),
            "margin_pct": stats.get("rec_margin", ""),
            "velocity_90d": stats.get("rec_velocity", ""),
            
            # LLM
            "llm_valid": result.get("valid"),
            "llm_confidence": result.get("confidence", 0),
            "relationship_type": result.get("relationship_type", ""),
            "llm_reason": result.get("reason", ""),
        })
    
    return recommendations


def main():
    parser = argparse.ArgumentParser(description="Full recommendation analysis with sales data")
    parser.add_argument("--top-categories", type=int, default=20, help="Number of top categories by sales")
    parser.add_argument("--items-per-category", type=int, default=6, help="Candidate items per category")
    parser.add_argument("--output", default=str(settings.DATA_DIR / "full_historical_recommendations.xlsx"), help="Output Excel file")
    parser.add_argument("--provider", default=settings.DEFAULT_PROVIDER, help="LLM provider")
    parser.add_argument("--skip-orders", action="store_true", help="Skip order analysis (use random categories)")
    parser.add_argument("--use-bq", action="store_true", help="Use BigQuery for category ranking (FAST, recommended)")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    args = parser.parse_args()
    
    use_cache = not args.no_cache
    
    print("Full Category → Item Recommendation Analysis")
    print("=" * 60)
    
    # Connect
    try:
        client = BigCommerceClient.from_env()
        result = client.test_connection()
        if not result["success"]:
            print(f"❌ {result.get('error')}")
            return 1
        print(f"✅ Connected to: {result.get('store_name')}\n")
    except Exception as e:
        print(f"❌ {e}")
        return 1
    
    # Get category mappings
    cats = client.get_categories()
    id_to_name = {c["id"]: c["name"] for c in cats}

    # Initialize Enrichment
    enrichment = EnrichmentService()
    
    # Get order data - use BigQuery if available (FAST), else fall back to BC API (SLOW)
    if args.use_bq:
        print("\n📊 Using BigQuery for category ranking (fast mode)...")
        try:
            bq_client = BigQueryClient()
            bq_categories = bq_client.get_top_categories()
            # Convert DataFrame to list of dicts matching expected format
            category_sales = {}
            for _, row in bq_categories.iterrows():
                category_sales[row['id']] = {
                    'order_count': int(row['order_count']),
                    'revenue': float(row['revenue']),
                    'total_quantity': int(row['total_quantity'])
                }
            print(f"  ✅ Loaded {len(category_sales)} categories from BigQuery")
            
            # Also fetch item-level sales from BQ
            try:
                item_sales_df = bq_client.get_item_sales()
                item_sales = {}
                for _, row in item_sales_df.iterrows():
                    item_sales[row['id']] = {
                        'order_count': int(row['order_count']),
                        'units_sold': int(row['units_sold']),
                        'revenue': float(row['revenue']),
                    }
                print(f"  ✅ Loaded {len(item_sales)} item sales from BigQuery")
            except Exception as e:
                print(f"  ⚠️ Item sales BQ query failed: {e}")
                item_sales = {}
            product_categories = {}
        except Exception as e:
            print(f"  ⚠️ BigQuery failed: {e}")
            print("  Falling back to BC API...")
            category_sales, item_sales, product_categories = get_order_data(client, months=6)
    elif not args.skip_orders:
        print("\n⏳ Using BigCommerce API for order analysis (slow)...")
        category_sales, item_sales, product_categories = get_order_data(client, months=6)
    else:
        category_sales, item_sales, product_categories = {}, {}, {}
        print("  (Skipped order analysis)")
    
    # Get top categories
    top_categories = get_top_categories_by_sales(
        client, 
        category_sales, 
        limit=args.top_categories, 
        use_cache=use_cache
    )
    print(f"\nTop {len(top_categories)} categories by sales:")
    for i, cat in enumerate(top_categories[:10]):
        print(f"  {i+1}. {cat['name']} ({cat['order_count']} orders, ${cat['revenue']})")
    if len(top_categories) > 10:
        print(f"  ... and {len(top_categories) - 10} more")
    
    # Get high-value items
    high_value_items = get_high_value_items_with_sales(
        client, 
        item_sales, 
        product_categories, 
        limit=300, 
        use_cache=use_cache
    )
    
    # Prepare output paths
    # Intermediate CSV for resume capability, final Excel for delivery
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = output_path.with_suffix(".csv")  # Intermediate CSV
    
    # Check for existing work
    processed_categories = get_processed_categories(csv_path)
    if processed_categories:
        console.print(f"[yellow]Found {len(processed_categories)} already processed categories. Resuming...[/yellow]")
    
    fieldnames = [
        "source_category", "src_orders_6mo", "src_revenue_6mo",
        "recommended_sku", "recommended_name", "recommended_price", "recommended_categories", "recommended_netsuite_id", "same_category",
        "item_orders_6mo", "item_units_6mo", "item_revenue_6mo",
        "copurchase_count", "margin_pct", "velocity_90d",
        "llm_valid", "llm_confidence", "relationship_type", "llm_reason",
    ]
    
    # Write header if new file
    if not csv_path.exists():
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
    
    # Generate recommendations
    all_recommendations = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
    ) as progress:
        
        task_id = progress.add_task("Processing Categories...", total=len(top_categories))
        
        for i, cat in enumerate(top_categories):
            cat_name = cat['name']
            
            # Resume Check
            if cat_name in processed_categories:
                progress.update(task_id, advance=1, description=f"Skipping {cat_name} (Done)")
                continue

            progress.update(task_id, description=f"Analyzing {cat_name}...")
            
            try:
                recs = find_recommendations_for_category(
                    cat, high_value_items, id_to_name,
                    enrichment_service=enrichment,
                    provider=args.provider,
                    max_items=args.items_per_category,
                )
                
                valid_count = sum(1 for r in recs if r["llm_valid"])
                
                # Append to CSV immediately
                with open(csv_path, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    for r in recs:
                        writer.writerow(r)
                
                all_recommendations.extend(recs)
                progress.console.print(f"  ✓ {cat_name}: {valid_count}/{len(recs)} valid")
                
            except Exception as e:
                progress.console.print(f"[red]Error analyzing {cat_name}: {e}[/red]")
            
            progress.advance(task_id)
    
    # Summary
    # Note: all_recommendations only contains THIS run's items. 
    # To be accurate, we'd need to re-read the CSV.
    
    # Convert intermediate CSV to formatted Excel
    excel_path = Path(args.output)
    if excel_path.suffix != '.xlsx':
        excel_path = excel_path.with_suffix('.xlsx')
    
    console.print(f"\n📊 Building Excel workbook...")
    write_excel_output(csv_path, excel_path, fieldnames)
    
    console.print(f"\n✅ Run Complete.")
    console.print(f"  Excel: {excel_path}")
    console.print(f"  CSV:   {csv_path} (intermediate)")
    
    return 0


def write_excel_output(csv_path: Path, excel_path: Path, fieldnames: list[str]):
    """Convert intermediate CSV to a single formatted Excel workbook."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    
    # Read all data from CSV
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
    
    if not all_rows:
        console.print("[yellow]No data to export[/yellow]")
        return
    
    wb = Workbook()
    
    # Style definitions
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    valid_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    invalid_fill = PatternFill(start_color="FF9999", end_color="FF9999", fill_type="solid")
    
    ws = wb.active
    ws.title = "All Recommendations"
    
    # Headers
    for col_idx, field in enumerate(fieldnames, 1):
        cell = ws.cell(row=1, column=col_idx, value=field)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    
    # Data rows
    for row_idx, row in enumerate(all_rows, 2):
        for col_idx, field in enumerate(fieldnames, 1):
            value = row.get(field, "")
            # Convert numeric fields
            if field in ("src_orders_6mo", "item_orders_6mo", "item_units_6mo", "copurchase_count"):
                try:
                    value = int(value) if value else 0
                except (ValueError, TypeError):
                    pass
            elif field in ("src_revenue_6mo", "item_revenue_6mo", "recommended_price", "velocity_90d"):
                try:
                    value = float(value) if value else 0.0
                except (ValueError, TypeError):
                    pass
            elif field in ("margin_pct", "llm_confidence"):
                # Store as decimal, let Excel format as percentage
                try:
                    raw = float(value) if value else 0.0
                    # llm_confidence comes as 0-100 from the LLM, convert to 0-1
                    value = raw if raw <= 1.0 else raw / 100.0
                except (ValueError, TypeError):
                    value = 0.0
            elif field == "llm_valid":
                if value == "True":
                    value = True
                elif value == "False":
                    value = False
            
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            
            # Apply percentage format for margin and confidence
            if field in ("margin_pct", "llm_confidence"):
                cell.number_format = '0%'
        
        # Row coloring: green for valid, RED for invalid
        llm_valid = row.get("llm_valid", "")
        if llm_valid == "True":
            for col_idx in range(1, len(fieldnames) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = valid_fill
        elif llm_valid == "False":
            for col_idx in range(1, len(fieldnames) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = invalid_fill
    
    # Auto-width columns
    for col_idx, field in enumerate(fieldnames, 1):
        max_len = len(field)
        for row_idx in range(2, min(len(all_rows) + 2, 50)):
            cell_value = str(ws.cell(row=row_idx, column=col_idx).value or "")
            max_len = max(max_len, min(len(cell_value), 40))
        ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 2
    
    # Freeze header row
    ws.freeze_panes = "A2"
    
    wb.save(excel_path)
    
    categories = set(r.get("source_category", "") for r in all_rows)
    invalid_count = sum(1 for r in all_rows if r.get("llm_valid") == "False")
    console.print(f"  ✅ {len(all_rows)} recommendations ({len(categories)} categories, {invalid_count} invalid) → single workbook")


if __name__ == "__main__":
    sys.exit(main())
