#!/usr/bin/env python3
"""
Order Co-occurrence Analysis

Queries NetSuite order history to find products frequently purchased together.
This is the foundation for upsell recommendations.

Usage:
    python scripts/analyze_cooccurrence.py
    python scripts/analyze_cooccurrence.py --months 24 --min-count 3
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from netsuite import NetSuiteClient


def get_orders_with_items(client: NetSuiteClient, since_date: str) -> list[dict]:
    """
    Fetch orders with their line items from NetSuite.
    
    Returns list of orders, each with list of item SKUs.
    """
    # Get orders with line items (using SuiteQL)
    # Note: Adjust field names based on your NetSuite schema
    query = f"""
        SELECT 
            t.tranid AS order_number,
            t.id AS order_id,
            t.trandate AS order_date,
            i.itemid AS sku,
            i.displayname AS item_name,
            tl.quantity
        FROM transaction t
        JOIN transactionline tl ON t.id = tl.transaction
        JOIN item i ON tl.item = i.id
        WHERE t.type = 'SalesOrd'
          AND t.trandate >= '{since_date}'
          AND tl.mainline = 'F'
          AND tl.itemtype IN ('InvtPart', 'NonInvtPart', 'Kit', 'Assembly')
        ORDER BY t.id, tl.linesequencenumber
    """
    
    all_items = []
    offset = 0
    limit = 1000
    
    print(f"Fetching orders since {since_date}...")
    
    while True:
        result = client.suiteql(query, limit=limit, offset=offset)
        items = result.get("items", [])
        
        if not items:
            break
            
        all_items.extend(items)
        offset += limit
        print(f"  Fetched {len(all_items)} line items...")
        
        if len(items) < limit:
            break
    
    return all_items


def group_items_by_order(line_items: list[dict]) -> dict[str, set[str]]:
    """Group SKUs by order."""
    orders = defaultdict(set)
    
    for line in line_items:
        order_id = line.get("order_id") or line.get("order_number")
        sku = line.get("sku")
        if order_id and sku:
            orders[order_id].add(sku)
    
    return orders


def calculate_cooccurrence(orders: dict[str, set[str]], min_count: int = 3) -> list[dict]:
    """
    Calculate co-occurrence statistics for product pairs.
    
    Returns list of pairs with:
    - product_a, product_b: SKUs
    - count: times purchased together
    - support: proportion of orders containing both
    """
    pair_counts = defaultdict(int)
    total_orders = len(orders)
    
    print(f"Analyzing {total_orders} orders for co-occurrence...")
    
    for order_id, skus in orders.items():
        if len(skus) < 2:
            continue
        
        # Count all pairs in this order
        for pair in combinations(sorted(skus), 2):
            pair_counts[pair] += 1
    
    # Filter and format results
    results = []
    for (sku_a, sku_b), count in pair_counts.items():
        if count >= min_count:
            results.append({
                "product_a": sku_a,
                "product_b": sku_b,
                "count": count,
                "support": round(count / total_orders, 6),
            })
    
    # Sort by count descending
    results.sort(key=lambda x: x["count"], reverse=True)
    
    return results


def save_results(results: list[dict], output_path: Path):
    """Save results to CSV and JSON."""
    # CSV
    csv_path = output_path.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["product_a", "product_b", "count", "support"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved CSV: {csv_path}")
    
    # JSON
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved JSON: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze order co-occurrence")
    parser.add_argument("--months", type=int, default=12, help="Months of history to analyze")
    parser.add_argument("--min-count", type=int, default=3, help="Minimum co-occurrence count")
    parser.add_argument("--output", default="data/cooccurrence", help="Output file path (without extension)")
    args = parser.parse_args()
    
    print("Order Co-occurrence Analysis")
    print("=" * 50)
    
    # Calculate date range
    since_date = (datetime.now() - timedelta(days=args.months * 30)).strftime("%Y-%m-%d")
    
    try:
        client = NetSuiteClient.from_env()
        print(f"Account: {client.creds.account_id}")
    except KeyError as e:
        print(f"❌ Missing environment variable: {e}")
        print("Copy .env.template to .env and fill in credentials.")
        return 1
    
    # Test connection
    result = client.test_connection()
    if not result["success"]:
        print(f"❌ Connection failed: {result.get('error')}")
        return 1
    print("✅ Connected to NetSuite\n")
    
    # Fetch and analyze
    line_items = get_orders_with_items(client, since_date)
    
    if not line_items:
        print("No order data found. Check query and date range.")
        return 1
    
    orders = group_items_by_order(line_items)
    print(f"Found {len(orders)} orders with {len(line_items)} line items\n")
    
    results = calculate_cooccurrence(orders, min_count=args.min_count)
    print(f"Found {len(results)} product pairs with {args.min_count}+ co-occurrences\n")
    
    if results:
        print("Top 10 pairs:")
        for r in results[:10]:
            print(f"  {r['product_a']} + {r['product_b']}: {r['count']} orders")
        print()
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_results(results, output_path)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
