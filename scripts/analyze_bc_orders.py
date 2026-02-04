#!/usr/bin/env python3
"""
BigCommerce Order Co-occurrence Analysis

Analyzes BigCommerce order history to find products frequently purchased together.
Generates two types of co-occurrence data:
1. Item-Item: "People who bought Item A also bought Item B"
2. Category-Item: "People who bought from Category X also bought Item Y"

Usage:
    python scripts/analyze_bc_orders.py
    python scripts/analyze_bc_orders.py --months 12 --min-count 2
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce import BigCommerceClient


def prefetch_product_categories(client: BigCommerceClient) -> tuple[dict[int, list[int]], dict[int, str]]:
    """
    Fetch all products to map Product ID -> Category IDs and Product ID -> SKU.
    """
    print("Prefetching product catalog...")
    products = client.get_products(limit=250)
    
    product_categories = {}
    product_skus = {}
    
    for p in products:
        pid = p.get("id")
        sku = p.get("sku")
        categories = p.get("categories", [])
        
        if pid and sku:
            product_categories[pid] = categories
            product_skus[pid] = sku
            
    print(f"Loaded {len(product_categories)} products from catalog.")
    return product_categories, product_skus


def get_order_data(client: BigCommerceClient, months: int = 12) -> tuple[list[dict], list[dict]]:
    """
    Fetch orders and their products from BigCommerce.
    
    Returns:
        - List of single-item order summaries (cross-sell gaps)
        - List of multi-item order details (list of {sku, product_id} dicts per order)
    """
    # Calculate date range
    min_date = datetime.now() - timedelta(days=months * 30)
    min_date_str = min_date.strftime("%a, %d %b %Y 00:00:00 +0000")
    
    print(f"Fetching orders since {min_date.strftime('%Y-%m-%d')}...")
    
    # Get completed/shipped orders
    orders = client.get_orders(min_date=min_date_str, status_id=11)  # 11 = Completed
    orders.extend(client.get_orders(min_date=min_date_str, status_id=10))  # 10 = Shipped
    
    print(f"Found {len(orders)} orders")
    
    single_item_orders = []
    multi_item_orders_details = []
    
    for i, order in enumerate(orders):
        order_id = order.get("id")
        
        try:
            products = client.get_order_products(order_id)
            # Filter out items without SKU or ID
            valid_products = [
                {"sku": p.get("sku"), "product_id": p.get("product_id"), "name": p.get("name")}
                for p in products if p.get("sku") and p.get("product_id")
            ]
            
            if len(valid_products) == 1:
                single_item_orders.append({
                    "order_id": order_id,
                    "sku": valid_products[0]["sku"],
                    "product_name": valid_products[0]["name"],
                })
            elif len(valid_products) > 1:
                multi_item_orders_details.append(valid_products)
            
            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(orders)} orders...")
                sleep(0.1)  # Rate limit courtesy
                
        except Exception as e:
            print(f"  ⚠️ Error fetching products for order {order_id}: {e}")
    
    print(f"\nOrder breakdown:")
    print(f"  Single-item orders: {len(single_item_orders)} (cross-sell opportunities)")
    print(f"  Multi-item orders: {len(multi_item_orders_details)} (co-occurrence data)")
    
    return single_item_orders, multi_item_orders_details


def analyze_cooccurrence(
    multi_item_orders: list[list[dict]],
    product_categories: dict[int, list[int]],
    min_count: int = 2
) -> dict[str, list]:
    """
    Calculate which products are bought together (Item-Item) 
    and which items are bought with categories (Category-Item).
    """
    item_pair_counts = defaultdict(int)
    category_item_counts = defaultdict(int)
    total_orders = len(multi_item_orders)
    
    print("\nAnalyzing co-occurrence...")
    
    for order_items in multi_item_orders:
        # Get unique SKUs and their categories in this order
        # item structure: {'sku': '...', 'product_id': 123}
        order_skus = set()
        order_categories = set()
        
        # Build maps for this specific order
        sku_to_cats = {}
        
        for item in order_items:
            sku = item["sku"]
            pid = item["product_id"]
            
            # Skip if we don't have catalog data for this product (e.g. discontinued)
            if pid not in product_categories:
                continue
                
            cats = product_categories[pid]
            sku_to_cats[sku] = cats
            order_skus.add(sku)
            for c in cats:
                order_categories.add(c)
        
        sorted_skus = sorted(list(order_skus))
        
        # 1. Item-Item Co-occurrence
        if len(sorted_skus) >= 2:
            for pair in combinations(sorted_skus, 2):
                item_pair_counts[pair] += 1
                
        # 2. Category-Item Co-occurrence
        # For each item in the order, check if it co-occurred with a category
        # (excluding its own categories to avoid self-matching)
        for sku_target in sorted_skus:
            # The categories of the target item
            target_cats = set(sku_to_cats.get(sku_target, []))
            
            # The categories present in the REST of the order
            other_cats = set()
            for sku_other in sorted_skus:
                if sku_other == sku_target:
                    continue
                other_cats.update(sku_to_cats.get(sku_other, []))
            
            # Increment count for each (Category -> Target Item)
            for cat_id in other_cats:
                category_item_counts[(cat_id, sku_target)] += 1

    # Format Item-Item Results
    item_results = []
    for (sku_a, sku_b), count in item_pair_counts.items():
        if count >= min_count:
            item_results.append({
                "item_a": sku_a,
                "item_b": sku_b,
                "count": count,
                "support": round(count / total_orders, 6) if total_orders else 0,
            })
    item_results.sort(key=lambda x: x["count"], reverse=True)

    # Format Category-Item Results
    category_results = []
    for (cat_id, sku), count in category_item_counts.items():
        if count >= min_count:
            category_results.append({
                "category_id": cat_id,
                "item_sku": sku,
                "count": count,
                "support": round(count / total_orders, 6) if total_orders else 0,
            })
    category_results.sort(key=lambda x: x["count"], reverse=True)

    return {
        "item_cooccurrence": item_results,
        "category_cooccurrence": category_results
    }


def identify_cross_sell_gaps(single_item_orders: list[dict]) -> list[dict]:
    """
    Identify products frequently bought alone (cross-sell opportunities).
    """
    sku_counts = defaultdict(int)
    sku_names = {}
    
    for order in single_item_orders:
        sku = order["sku"]
        sku_counts[sku] += 1
        sku_names[sku] = order.get("product_name", "")
    
    # Sort by frequency
    gaps = []
    for sku, count in sorted(sku_counts.items(), key=lambda x: -x[1]):
        gaps.append({
            "sku": sku,
            "name": sku_names.get(sku, ""),
            "single_item_order_count": count,
            "opportunity": "High" if count > 10 else "Medium" if count > 3 else "Low",
        })
    
    return gaps


def save_results(cooccurrence_data: dict, gaps: list, output_dir: Path):
    """Save analysis results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Co-occurrence (Item-Item and Category-Item)
    if cooccurrence_data:
        with open(output_dir / "bc_cooccurrence.json", "w") as f:
            json.dump(cooccurrence_data, f, indent=2)
        print(f"Saved: {output_dir / 'bc_cooccurrence.json'}")
    
    # Cross-sell gaps
    if gaps:
        with open(output_dir / "cross_sell_gaps.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["sku", "name", "single_item_order_count", "opportunity"])
            writer.writeheader()
            writer.writerows(gaps)
        print(f"Saved: {output_dir / 'cross_sell_gaps.csv'}")


def main():
    parser = argparse.ArgumentParser(description="Analyze BigCommerce orders")
    parser.add_argument("--months", type=int, default=12, help="Months of history")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum co-occurrence")
    parser.add_argument("--store", default="BC", help="Store prefix")
    args = parser.parse_args()
    
    print("BigCommerce Order Analysis (Dual-Level)")
    print("=" * 50)
    
    try:
        client = BigCommerceClient.from_env(store_prefix=args.store)
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    
    # Test connection
    result = client.test_connection()
    if not result["success"]:
        print(f"❌ Connection failed: {result.get('error')}")
        return 1
    print(f"✅ Connected to: {result.get('store_name')}\n")
    
    # 1. Prefetch Product Catalog (to map ID -> Categories)
    product_categories, _ = prefetch_product_categories(client)
    
    # 2. Fetch Orders
    single_item_orders, multi_item_orders = get_order_data(client, months=args.months)
    
    # 3. Analyze Co-occurrence
    cooccurrence_data = analyze_cooccurrence(
        multi_item_orders, 
        product_categories, 
        min_count=args.min_count
    )
    
    print(f"\nResults Summary:")
    print(f"  Item-Item Pairs: {len(cooccurrence_data['item_cooccurrence'])}")
    print(f"  Category-Item Pairs: {len(cooccurrence_data['category_cooccurrence'])}")
    
    if cooccurrence_data['item_cooccurrence']:
        print("\nTop Item-Item Pairs:")
        for r in cooccurrence_data['item_cooccurrence'][:5]:
            print(f"  {r['item_a']} + {r['item_b']}: {r['count']} orders")
            
    if cooccurrence_data['category_cooccurrence']:
        print("\nTop Category-Item Pairs:")
        for r in cooccurrence_data['category_cooccurrence'][:5]:
            print(f"  Category {r['category_id']} + Item {r['item_sku']}: {r['count']} orders")
    
    # 4. Analyze Gaps
    gaps = identify_cross_sell_gaps(single_item_orders)
    
    # 5. Save
    save_results(cooccurrence_data, gaps, Path("data"))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
