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
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce import BigCommerceClient

# Import LLM validation
sys.path.insert(0, str(Path(__file__).parent))
from validate_category_pairings import get_llm_validation, get_batch_llm_validation


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
) -> list[dict]:
    """Get top categories by order volume, excluding meta-categories."""
    cats = bc_client.get_categories()
    
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
    
    products = bc_client.get_products(limit=2000)  # Get more products
    
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
    
    # Filter items - exclude only if item IS the exact category being shopped
    # e.g., don't recommend "Helmets" product to someone in "Helmets" category
    # BUT DO recommend "Flashlights" even if they're also tagged in "Helmets"
    eligible_items = []
    for item in all_items:
        item_name_lower = item["name"].lower()
        
        # Skip if item name contains the category name (same product type)
        if category_name_lower in item_name_lower:
            continue
        
        # Skip if category name contains the item type (e.g., "Helmets" category, "Helmet" item)
        item_type = item_name_lower.split()[0] if item_name_lower else ""
        if len(item_type) > 4 and item_type in category_name_lower:
            continue
            
        eligible_items.append(item)
    
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
    batch_items = [
        {"name": item["name"], "sku": item.get("sku", ""), "brand": item.get("brand", "")}
        for item in selected
    ]
    
    try:
        batch_results = get_batch_llm_validation(
            category_name, 
            batch_items, 
            provider=provider,
            max_items=50,  # Process up to 50 at a time
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
            
            # Item sales
            "item_orders_6mo": item["order_count"],
            "item_units_6mo": item["units_sold"],
            "item_revenue_6mo": item["revenue"],
            
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
    parser.add_argument("--output", default="data/full_recommendations.csv", help="Output CSV")
    parser.add_argument("--provider", default="azure", help="LLM provider")
    parser.add_argument("--skip-orders", action="store_true", help="Skip order analysis (use random categories)")
    args = parser.parse_args()
    
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
    
    # Get order data
    if not args.skip_orders:
        category_sales, item_sales, product_categories = get_order_data(client, months=6)
    else:
        category_sales, item_sales, product_categories = {}, {}, {}
        print("  (Skipped order analysis)")
    
    # Get top categories
    top_categories = get_top_categories_by_sales(client, category_sales, limit=args.top_categories)
    print(f"\nTop {len(top_categories)} categories by sales:")
    for i, cat in enumerate(top_categories[:10]):
        print(f"  {i+1}. {cat['name']} ({cat['order_count']} orders, ${cat['revenue']})")
    if len(top_categories) > 10:
        print(f"  ... and {len(top_categories) - 10} more")
    
    # Get high-value items
    high_value_items = get_high_value_items_with_sales(client, item_sales, product_categories, limit=300)
    
    # Prepare output file - write header first
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = [
        "source_category", "src_orders_6mo", "src_revenue_6mo",
        "recommended_sku", "recommended_name", "recommended_price", "recommended_categories",
        "item_orders_6mo", "item_units_6mo", "item_revenue_6mo",
        "llm_valid", "llm_confidence", "relationship_type", "llm_reason",
    ]
    
    # Write header
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
    
    # Generate recommendations and write incrementally
    all_recommendations = []
    
    for i, cat in enumerate(top_categories):
        print(f"\n[{i+1}/{len(top_categories)}] {cat['name']} ({cat['order_count']} orders)")
        sys.stdout.flush()
        
        recs = find_recommendations_for_category(
            cat, high_value_items, id_to_name,
            provider=args.provider,
            max_items=args.items_per_category,
        )
        
        valid_count = sum(1 for r in recs if r["llm_valid"])
        print(f"  → {valid_count}/{len(recs)} valid recommendations")
        sys.stdout.flush()
        
        # Append to CSV immediately
        with open(output_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            for r in recs:
                writer.writerow(r)
        
        all_recommendations.extend(recs)
    
    # Summary
    valid = [r for r in all_recommendations if r.get("llm_valid")]
    print(f"\n{'=' * 60}")
    print(f"✅ Valid recommendations: {len(valid)} / {len(all_recommendations)} ({100*len(valid)//len(all_recommendations) if all_recommendations else 0}%)")
    print(f"✅ Saved: {output_path}")
    
    # Show top valid recommendations
    if valid:
        print(f"\nTop 10 recommendations:")
        for r in sorted(valid, key=lambda x: (-x["src_orders_6mo"], -x["item_orders_6mo"]))[:10]:
            print(f"  {r['source_category']} → {r['recommended_name']} (${r['recommended_price']})")
            print(f"    Cat orders: {r['src_orders_6mo']}, Item orders: {r['item_orders_6mo']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
