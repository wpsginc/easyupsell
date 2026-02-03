"""
Core Analyzer - Main analysis engine.

Wraps the prototype analysis logic into a clean interface.
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


def run_analysis(
    category_name: Optional[str] = None,
    limit: int = 50,
    items_per_category: int = 8,
    output_path: Path = Path("data/recommendations.csv"),
    skip_orders: bool = False,
    resume: bool = False,
    provider: str = "azure",
) -> dict:
    """
    Run full recommendation analysis.
    
    Returns dict with:
        - valid_count: Number of valid recommendations
        - total_count: Total analyzed pairs
        - output_path: Path to CSV
    """
    # Import here to avoid circular deps
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from bigcommerce import BigCommerceClient
    
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from validate_category_pairings import get_llm_validation
    
    # Connect to BigCommerce
    client = BigCommerceClient.from_env()
    result = client.test_connection()
    
    if not result["success"]:
        raise RuntimeError(f"BigCommerce connection failed: {result.get('error')}")
    
    console.print(f"[green]✓[/green] Connected to: {result.get('store_name')}")
    
    # Get category mappings
    cats = client.get_categories()
    id_to_name = {c["id"]: c["name"] for c in cats}
    
    # Get order data
    if not skip_orders:
        category_sales, item_sales, product_categories = get_order_data(client, months=6)
    else:
        category_sales, item_sales, product_categories = {}, {}, {}
        console.print("  [dim](Skipped order analysis)[/dim]")
    
    # Get top categories
    if category_name:
        # Single category mode
        top_categories = [c for c in get_top_categories_by_sales(client, category_sales, 9999)
                         if c["name"].lower() == category_name.lower()]
        if not top_categories:
            raise ValueError(f"Category not found: {category_name}")
    else:
        top_categories = get_top_categories_by_sales(client, category_sales, limit)
    
    console.print(f"\nAnalyzing {len(top_categories)} categories...")
    
    # Get high-value items
    high_value_items = get_high_value_items_with_sales(client, item_sales, product_categories)
    
    # Generate recommendations
    all_recommendations = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        
        task = progress.add_task("Categories", total=len(top_categories))
        
        for cat in top_categories:
            progress.update(task, description=f"[cyan]{cat['name'][:30]}[/cyan]")
            
            recs = find_recommendations_for_category(
                cat, high_value_items, id_to_name,
                provider=provider,
                max_items=items_per_category,
            )
            
            all_recommendations.extend(recs)
            progress.advance(task)
    
    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_recommendations(all_recommendations, output_path)
    
    valid = [r for r in all_recommendations if r.get("llm_valid")]
    
    return {
        "valid_count": len(valid),
        "total_count": len(all_recommendations),
        "output_path": output_path,
    }


def get_order_data(bc_client, months: int = 6) -> tuple[dict, dict, dict]:
    """Analyze order history for sales metrics."""
    console.print(f"  Analyzing {months} months of orders...")
    
    min_date = datetime.now() - timedelta(days=months * 30)
    min_date_str = min_date.strftime("%a, %d %b %Y 00:00:00 +0000")
    
    try:
        orders = bc_client.get_orders(min_date=min_date_str, status_id=11)
        orders.extend(bc_client.get_orders(min_date=min_date_str, status_id=10))
    except Exception as e:
        console.print(f"  [yellow]⚠ Could not fetch orders: {e}[/yellow]")
        return {}, {}, {}
    
    console.print(f"  Found {len(orders)} orders")
    
    category_sales = defaultdict(lambda: {"order_count": 0, "revenue": 0.0})
    item_sales = defaultdict(lambda: {"order_count": 0, "units_sold": 0, "revenue": 0.0})
    product_categories = {}
    
    sample_size = min(300, len(orders))
    
    for i, order in enumerate(orders[:sample_size]):
        try:
            products = bc_client.get_order_products(order["id"])
            for p in products:
                product_id = p.get("product_id")
                qty = p.get("quantity", 1)
                price = float(p.get("base_price", 0)) * qty
                
                item_sales[product_id]["order_count"] += 1
                item_sales[product_id]["units_sold"] += qty
                item_sales[product_id]["revenue"] += price
                
                if product_id and product_id not in product_categories:
                    try:
                        prod = bc_client.get_product(product_id)
                        product_categories[product_id] = prod.get("categories", [])
                    except:
                        product_categories[product_id] = []
                
                for cat_id in product_categories.get(product_id, []):
                    category_sales[cat_id]["order_count"] += 1
                    category_sales[cat_id]["revenue"] += price
        except:
            continue
        
        if (i + 1) % 100 == 0:
            console.print(f"    Processed {i + 1}/{sample_size} orders...")
            sleep(0.1)
    
    console.print(f"  [green]✓[/green] Sales data: {len(category_sales)} categories, {len(item_sales)} items")
    return dict(category_sales), dict(item_sales), product_categories


def get_top_categories_by_sales(bc_client, category_sales: dict, limit: int) -> list[dict]:
    """Get top categories by order volume."""
    cats = bc_client.get_categories()
    parent_ids = set(c.get("parent_id", 0) for c in cats)
    
    excluded = ["$", "sale", "clearance", "promo", "new arrival", "gift", "shop all",
                "featured", "hot", "best seller"]
    
    scored = []
    for c in cats:
        cat_id = c["id"]
        name = c.get("name", "")
        name_lower = name.lower()
        
        if c.get("parent_id", 0) == 0:
            continue
        if any(ex in name_lower for ex in excluded):
            continue
        
        sales = category_sales.get(cat_id, {})
        
        scored.append({
            "id": cat_id,
            "name": name,
            "parent_id": c.get("parent_id", 0),
            "order_count": sales.get("order_count", 0),
            "revenue": round(sales.get("revenue", 0), 2),
            "is_leaf": cat_id not in parent_ids,
        })
    
    scored.sort(key=lambda x: -x["order_count"])
    return scored[:limit]


def get_high_value_items_with_sales(bc_client, item_sales: dict, product_categories: dict) -> list[dict]:
    """Get high-value upsell candidates with priority brand boosting."""
    from easyupsell.commands.brands import load_brands
    
    priority_brands = load_brands()
    
    console.print("  Fetching upsell candidates...")
    
    products = bc_client.get_products(limit=2000)
    
    priority_items = []
    regular_items = []
    
    for p in products:
        price = float(p.get("price", 0) or 0)
        product_id = p["id"]
        name = p.get("name", "")
        
        if 15 <= price <= 200 and p.get("is_visible", True):
            sales = item_sales.get(product_id, {})
            
            item = {
                "id": product_id,
                "sku": p.get("sku", ""),
                "name": name[:60],
                "price": price,
                "categories": p.get("categories", []),
                "inventory": p.get("inventory_level", 0),
                "order_count": sales.get("order_count", 0),
                "units_sold": sales.get("units_sold", 0),
                "revenue": round(sales.get("revenue", 0), 2),
            }
            
            name_lower = name.lower()
            is_priority = any(brand in name_lower for brand in priority_brands)
            
            if is_priority:
                priority_items.append(item)
            else:
                regular_items.append(item)
    
    priority_items.sort(key=lambda x: (-x["order_count"], abs(x["price"] - 50)))
    regular_items.sort(key=lambda x: (-x["order_count"], abs(x["price"] - 50)))
    
    limit = 300
    priority_limit = min(len(priority_items), limit // 2)
    regular_limit = limit - priority_limit
    
    candidates = priority_items[:priority_limit] + regular_items[:regular_limit]
    
    console.print(f"  [green]✓[/green] {len(priority_items)} priority + {len(regular_items)} regular = {len(candidates)} candidates")
    return candidates


def find_recommendations_for_category(
    category: dict,
    all_items: list[dict],
    id_to_name: dict,
    provider: str = "azure",
    max_items: int = 8,
) -> list[dict]:
    """Find best item recommendations for a category."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from validate_category_pairings import get_llm_validation
    
    category_id = category["id"]
    category_name = category["name"]
    category_name_lower = category_name.lower()
    
    # Filter items
    eligible_items = []
    for item in all_items:
        item_name_lower = item["name"].lower()
        
        # Skip same product type
        if category_name_lower in item_name_lower:
            continue
        
        item_type = item_name_lower.split()[0] if item_name_lower else ""
        if len(item_type) > 4 and item_type in category_name_lower:
            continue
        
        eligible_items.append(item)
    
    eligible_items.sort(key=lambda x: -x.get("order_count", 0))
    
    # Pick diverse items
    selected = []
    seen_names = set()
    
    for item in eligible_items:
        name_key = " ".join(item["name"].lower().split()[:3])
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        selected.append(item)
        if len(selected) >= max_items:
            break
    
    # Validate with LLM
    recommendations = []
    for item in selected:
        try:
            result = get_llm_validation(category_name, item["name"], provider=provider)
        except Exception as e:
            result = {"valid": None, "reason": f"Error: {e}"}
        
        item_cat_names = [id_to_name.get(c, "") for c in item["categories"][:2]]
        
        recommendations.append({
            "source_category": category_name,
            "src_orders_6mo": category["order_count"],
            "src_revenue_6mo": category["revenue"],
            "recommended_sku": item["sku"],
            "recommended_name": item["name"],
            "recommended_price": item["price"],
            "recommended_categories": " | ".join(filter(None, item_cat_names)),
            "item_orders_6mo": item["order_count"],
            "item_units_6mo": item["units_sold"],
            "item_revenue_6mo": item["revenue"],
            "llm_valid": result.get("valid"),
            "llm_confidence": result.get("confidence", 0),
            "relationship_type": result.get("relationship_type", ""),
            "llm_reason": result.get("reason", ""),
        })
        
        sleep(0.1)
    
    return recommendations


def save_recommendations(recommendations: list[dict], output_path: Path):
    """Save recommendations to CSV."""
    if not recommendations:
        return
    
    fieldnames = [
        "source_category", "src_orders_6mo", "src_revenue_6mo",
        "recommended_sku", "recommended_name", "recommended_price", "recommended_categories",
        "item_orders_6mo", "item_units_6mo", "item_revenue_6mo",
        "llm_valid", "llm_confidence", "relationship_type", "llm_reason",
    ]
    
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in sorted(recommendations, key=lambda x: (
            -int(x.get("llm_valid") or 0),
            -x.get("src_orders_6mo", 0),
            -x.get("item_orders_6mo", 0),
        )):
            writer.writerow(r)
