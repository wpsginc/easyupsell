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
    from bigquery_client import BigQueryClient
    from enrichment import EnrichmentService
    
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from validate_category_pairings import get_llm_validation
    
    # Connect to BigCommerce
    client = BigCommerceClient.from_env()
    result = client.test_connection()
    
    if not result["success"]:
        raise RuntimeError(f"BigCommerce connection failed: {result.get('error')}")
    
    console.print(f"[green]✓[/green] Connected to: {result.get('store_name')}")
    
    # Load enrichment data
    console.print("  [cyan]Loading enrichment data...[/cyan]")
    enrichment_service = EnrichmentService()
    
    # Get category mappings
    cats = client.get_categories()
    id_to_name = {c["id"]: c["name"] for c in cats}
    
    # Get order data from BigQuery
    if not skip_orders:
        console.print("  [cyan]Fetching sales metrics from BigQuery...[/cyan]")
        bq = BigQueryClient()
        
        df_cat_sales = bq.get_top_categories()
        category_sales = df_cat_sales.set_index("id").to_dict(orient="index")
        
        df_item_sales = bq.get_item_sales()
        item_sales = df_item_sales.set_index("id").to_dict(orient="index")
        
        # product_categories mapping still needs to be populated if used
        product_categories = {}
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
    high_value_items = get_high_value_items_with_sales(client, item_sales)
    
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
                enrichment_service=enrichment_service,
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


def get_all_leaf_categories(bc_client) -> list[dict]:
    """Get all leaf categories (no children)."""
    cats = bc_client.get_categories()
    parent_ids = set(c.get("parent_id", 0) for c in cats)
    
    leaves = []
    for c in cats:
        if c["id"] not in parent_ids:
            leaves.append(c)
            
    return leaves


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
    
    # Use Total Revenue to identify top performing categories per spec
    scored.sort(key=lambda x: -x["revenue"])
    return scored[:limit]


def get_high_value_items_with_sales(bc_client, item_sales: dict) -> list[dict]:
    """Get high-value upsell candidates with priority brand boosting."""
    from easyupsell.commands.brands import load_brands
    from bigquery_client import BigQueryClient
    
    priority_brands = load_brands()
    
    console.print("  Fetching upsell candidates...")
    
    products = bc_client.get_products(limit=2000)
    
    priority_items = []
    regular_items = []
    
    for p in products:
        price = float(p.get("price", 0) or 0)
        product_id = p["id"]
        name = p.get("name", "")
        bpn = p.get("bin_picking_number", "")
        
        if 15 <= price <= 200 and p.get("is_visible", True):
            sales = item_sales.get(product_id, {})
            
            # Extract NetSuite ID per spec
            netsuite_id = BigQueryClient.extract_netsuite_id(bpn)
            
            item = {
                "id": product_id,
                "sku": p.get("sku", ""),
                "netsuite_id": netsuite_id,
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
    enrichment_service = None,
) -> list[dict]:
    """Find best item recommendations for a category."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from validate_category_pairings import get_llm_validation
    
    category_id = category["id"]
    category_name = category["name"]
    category_name_lower = category_name.lower()
    
    from candidate_filter import filter_candidates
    eligible_items = filter_candidates(category, all_items)
    
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
        # Get enrichment data
        enrichment = None
        if enrichment_service:
            enrichment = enrichment_service.get_enrichment_for_category_pair(category_id, item["sku"])
        
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
            "recommended_netsuite_id": item.get("netsuite_id"),
            "same_category": item.get("same_category", False),
            "recommended_name": item["name"],
            "recommended_price": item["price"],
            "recommended_categories": " | ".join(filter(None, item_cat_names)),
            "item_orders_6mo": item["order_count"],
            "item_units_6mo": item["units_sold"],
            "item_revenue_6mo": item["revenue"],
            "enrichment_copurchase_count": enrichment.get("copurchase_count", 0) if enrichment else 0,
            "enrichment_margin": enrichment.get("rec_margin", 0) if enrichment else 0,
            "enrichment_velocity": enrichment.get("rec_velocity", 0) if enrichment else 0,
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
        "recommended_sku", "recommended_netsuite_id", "same_category", "recommended_name", 
        "recommended_price", "recommended_categories",
        "item_orders_6mo", "item_units_6mo", "item_revenue_6mo",
        "enrichment_copurchase_count", "enrichment_margin", "enrichment_velocity",
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
