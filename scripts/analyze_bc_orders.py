#!/usr/bin/env python3
"""
BigCommerce Order Co-occurrence Analysis

Analyzes BigCommerce order history to find products frequently purchased together.
Works with sparse data by also identifying single-item orders that COULD benefit
from cross-sell recommendations.

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


def get_order_data(client: BigCommerceClient, months: int = 12) -> tuple[list[dict], dict]:
    """
    Fetch orders and their products from BigCommerce.
    
    Returns:
        - List of order summaries
        - Dict mapping order_id to list of product SKUs
    """
    # Calculate date range
    min_date = datetime.now() - timedelta(days=months * 30)
    min_date_str = min_date.strftime("%a, %d %b %Y 00:00:00 +0000")
    
    print(f"Fetching orders since {min_date.strftime('%Y-%m-%d')}...")
    
    # Get completed/shipped orders
    orders = client.get_orders(min_date=min_date_str, status_id=11)  # 11 = Completed
    orders.extend(client.get_orders(min_date=min_date_str, status_id=10))  # 10 = Shipped
    
    print(f"Found {len(orders)} orders")
    
    order_products = {}
    single_item_orders = []
    multi_item_orders = []
    
    for i, order in enumerate(orders):
        order_id = order.get("id")
        
        try:
            products = client.get_order_products(order_id)
            skus = [p.get("sku") for p in products if p.get("sku")]
            
            if len(skus) == 1:
                single_item_orders.append({
                    "order_id": order_id,
                    "sku": skus[0],
                    "product_name": products[0].get("name"),
                })
            elif len(skus) > 1:
                multi_item_orders.append({"order_id": order_id, "skus": skus})
                order_products[order_id] = set(skus)
            
            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(orders)} orders...")
                sleep(0.1)  # Rate limit courtesy
                
        except Exception as e:
            print(f"  ⚠️ Error fetching products for order {order_id}: {e}")
    
    print(f"\nOrder breakdown:")
    print(f"  Single-item orders: {len(single_item_orders)} (cross-sell opportunities)")
    print(f"  Multi-item orders: {len(multi_item_orders)} (co-occurrence data)")
    
    return single_item_orders, order_products


def analyze_cooccurrence(order_products: dict[int, set[str]], min_count: int = 2) -> list[dict]:
    """Calculate which products are bought together."""
    pair_counts = defaultdict(int)
    total_orders = len(order_products)
    
    for order_id, skus in order_products.items():
        if len(skus) < 2:
            continue
        
        for pair in combinations(sorted(skus), 2):
            pair_counts[pair] += 1
    
    results = []
    for (sku_a, sku_b), count in pair_counts.items():
        if count >= min_count:
            results.append({
                "product_a": sku_a,
                "product_b": sku_b,
                "count": count,
                "support": round(count / total_orders, 6) if total_orders else 0,
            })
    
    results.sort(key=lambda x: x["count"], reverse=True)
    return results


def identify_cross_sell_gaps(single_item_orders: list[dict]) -> list[dict]:
    """
    Identify products frequently bought alone (cross-sell opportunities).
    
    These are products where customers DIDN'T buy complementary items.
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


def save_results(cooccurrence: list, gaps: list, output_dir: Path):
    """Save analysis results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Co-occurrence
    if cooccurrence:
        with open(output_dir / "bc_cooccurrence.json", "w") as f:
            json.dump(cooccurrence, f, indent=2)
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
    
    print("BigCommerce Order Analysis")
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
    
    # Fetch and analyze
    single_item_orders, order_products = get_order_data(client, months=args.months)
    
    # Co-occurrence (likely sparse)
    cooccurrence = analyze_cooccurrence(order_products, min_count=args.min_count)
    print(f"\nFound {len(cooccurrence)} product pairs with {args.min_count}+ co-occurrences")
    
    if cooccurrence:
        print("\nTop co-purchased pairs:")
        for r in cooccurrence[:10]:
            print(f"  {r['product_a']} + {r['product_b']}: {r['count']} orders")
    else:
        print("(Sparse data - use attribute-based rules instead)")
    
    # Cross-sell gaps
    gaps = identify_cross_sell_gaps(single_item_orders)
    print(f"\nTop single-item products (cross-sell opportunities):")
    for g in gaps[:10]:
        print(f"  {g['sku']}: {g['single_item_order_count']} solo orders ({g['opportunity']})")
    
    # Save
    save_results(cooccurrence, gaps, Path("data"))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
