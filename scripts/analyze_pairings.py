#!/usr/bin/env python3
"""
Category Pairing Analysis with Business Metrics

Validates category pairings using LLM and enriches with:
- Sales velocity (from BC orders)
- Product count in each category
- Avg margin (from NetSuite cost vs BC price)

Outputs CSV for spreadsheet review.

Usage:
    python scripts/analyze_pairings.py
    python scripts/analyze_pairings.py --limit 50 --output analysis.csv
    python scripts/analyze_pairings.py --skip-orders --skip-margin  # Fast mode
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce import BigCommerceClient

# Try to import NetSuite (optional)
try:
    from netsuite import NetSuiteClient
    HAS_NETSUITE = True
except ImportError:
    HAS_NETSUITE = False

# Import LLM validation
sys.path.insert(0, str(Path(__file__).parent))
from validate_category_pairings import get_llm_validation


def get_category_stats(client: BigCommerceClient) -> dict:
    """
    Get stats for each category:
    - product_count: number of SKUs in category
    - name: category name
    - parent_id: for hierarchy
    """
    print("Fetching category list...")
    categories = client.get_categories()
    
    stats = {}
    for cat in categories:
        stats[cat["id"]] = {
            "id": cat["id"],
            "name": cat.get("name", ""),
            "parent_id": cat.get("parent_id", 0),
            "product_count": 0,  # Will be enriched
            "url": cat.get("custom_url", {}).get("url", ""),
        }
    
    return stats


def get_sales_velocity(client: BigCommerceClient, months: int = 6) -> dict:
    """
    Calculate sales velocity per category from order history.
    
    Returns dict: category_id -> {order_count, units_sold, revenue}
    """
    print(f"Analyzing {months} months of order history...")
    
    min_date = datetime.now() - timedelta(days=months * 30)
    min_date_str = min_date.strftime("%a, %d %b %Y 00:00:00 +0000")
    
    # Get completed orders
    try:
        orders = client.get_orders(min_date=min_date_str, status_id=11)  # Completed
        orders.extend(client.get_orders(min_date=min_date_str, status_id=10))  # Shipped
    except Exception as e:
        print(f"  ⚠️ Could not fetch orders: {e}")
        return {}
    
    print(f"  Found {len(orders)} orders")
    
    # Aggregate by category
    category_sales = defaultdict(lambda: {"order_count": 0, "units_sold": 0, "revenue": 0.0})
    product_categories = {}  # product_id -> [category_ids]
    
    # We need product->category mapping
    # For efficiency, build this from a product sample
    
    for i, order in enumerate(orders[:200]):  # Sample 200 orders for velocity
        try:
            products = client.get_order_products(order["id"])
            for p in products:
                product_id = p.get("product_id")
                qty = p.get("quantity", 1)
                price = float(p.get("base_price", 0)) * qty
                
                # Get category for this product (cached)
                if product_id and product_id not in product_categories:
                    try:
                        prod = client.get_product(product_id)
                        product_categories[product_id] = prod.get("categories", [])
                    except:
                        product_categories[product_id] = []
                
                for cat_id in product_categories.get(product_id, []):
                    category_sales[cat_id]["order_count"] += 1
                    category_sales[cat_id]["units_sold"] += qty
                    category_sales[cat_id]["revenue"] += price
                    
        except Exception as e:
            continue
        
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{min(200, len(orders))} orders...")
            sleep(0.1)
    
    return dict(category_sales)


def get_product_counts(client: BigCommerceClient, category_stats: dict) -> dict:
    """Add product counts to category stats."""
    print("Counting products per category...")
    
    # Get products with categories
    products = client.get_products(limit=250)
    
    for prod in products:
        for cat_id in prod.get("categories", []):
            if cat_id in category_stats:
                category_stats[cat_id]["product_count"] += 1
    
    return category_stats


def get_category_margins(bc_client: BigCommerceClient) -> dict:
    """
    Calculate average margin per category by matching BC products with NS costs.
    
    Returns dict: category_id -> {avg_margin_pct, avg_price, avg_cost, product_count}
    """
    if not HAS_NETSUITE:
        print("  ⚠️ NetSuite module not available, skipping margin data")
        return {}
    
    print("Calculating category margins from NetSuite...")
    
    try:
        ns_client = NetSuiteClient.from_env()
        if not ns_client.test_connection().get("success"):
            print("  ⚠️ NetSuite connection failed")
            return {}
    except Exception as e:
        print(f"  ⚠️ NetSuite not configured: {e}")
        return {}
    
    # Get NS items with cost data
    query = """
    SELECT 
        i.id,
        i.itemid AS sku,
        i.cost,
        i.averagecost,
        p.unitprice AS base_price
    FROM item i
    LEFT JOIN pricing p ON p.item = i.id AND p.pricelevel = 1
    WHERE i.itemtype IN ('InvtPart', 'NonInvtPart')
      AND i.isinactive = 'F'
    """
    
    try:
        ns_data = ns_client.suiteql(query)
        ns_items = {item["sku"]: item for item in ns_data.get("items", [])}
        print(f"  Loaded {len(ns_items)} items from NetSuite")
    except Exception as e:
        print(f"  ⚠️ Could not fetch NS cost data: {e}")
        return {}
    
    # Match with BC products
    bc_products = bc_client.get_products(limit=500)
    
    category_margins = defaultdict(lambda: {
        "total_margin": 0.0,
        "total_price": 0.0,
        "total_cost": 0.0,
        "count": 0,
    })
    
    for prod in bc_products:
        sku = prod.get("sku", "")
        price = float(prod.get("price", 0) or 0)
        
        # Find NS cost
        ns_item = ns_items.get(sku, {})
        cost = float(ns_item.get("averagecost") or ns_item.get("cost") or 0)
        
        if price > 0 and cost > 0:
            margin_pct = ((price - cost) / price) * 100
            
            for cat_id in prod.get("categories", []):
                category_margins[cat_id]["total_margin"] += margin_pct
                category_margins[cat_id]["total_price"] += price
                category_margins[cat_id]["total_cost"] += cost
                category_margins[cat_id]["count"] += 1
    
    # Calculate averages
    result = {}
    for cat_id, data in category_margins.items():
        if data["count"] > 0:
            result[cat_id] = {
                "avg_margin_pct": round(data["total_margin"] / data["count"], 1),
                "avg_price": round(data["total_price"] / data["count"], 2),
                "avg_cost": round(data["total_cost"] / data["count"], 2),
                "product_count": data["count"],
            }
    
    print(f"  Margin data for {len(result)} categories")
    return result


def find_child_categories(category_stats: dict) -> list[dict]:
    """Find leaf categories (no children)."""
    parent_ids = set(c["parent_id"] for c in category_stats.values())
    
    children = []
    for cat in category_stats.values():
        # Is leaf if not used as parent and not root
        if cat["id"] not in parent_ids and cat["parent_id"] != 0:
            children.append(cat)
    
    return children


def filter_real_categories(categories: list[dict]) -> list[dict]:
    """Filter out price tiers, promos, and non-product categories."""
    excluded_patterns = [
        "$", "sale", "clearance", "promo", "special", "new arrival",
        "featured", "best seller", "shop all", "gift"
    ]
    
    filtered = []
    for cat in categories:
        name_lower = cat["name"].lower()
        if not any(p in name_lower for p in excluded_patterns):
            filtered.append(cat)
    
    return filtered


def generate_smart_pairings(categories: list[dict], limit: int = 50) -> list[tuple]:
    """
    Generate pairings between categories.
    Prioritize categories with:
    - Higher product counts
    - Similar parent (more likely related)
    """
    import random
    
    # Sort by product count (higher = more important)
    sorted_cats = sorted(categories, key=lambda c: c.get("product_count", 0), reverse=True)
    
    pairings = []
    names = [(c["name"], c.get("parent_id", 0)) for c in sorted_cats[:40]]  # Top 40 by product count
    
    # Generate pairings, preferring same-parent
    for i, (name1, parent1) in enumerate(names):
        for j, (name2, parent2) in enumerate(names[i+1:], i+1):
            if name1 != name2:
                # Boost same-parent pairings
                priority = 1 if parent1 == parent2 else 2
                pairings.append((name1, name2, priority))
    
    # Sort by priority, then shuffle within priority
    random.seed(42)
    pairings.sort(key=lambda x: x[2])
    
    return [(a, b) for a, b, _ in pairings[:limit]]


def analyze_pairings(
    pairings: list[tuple],
    category_stats: dict,
    sales_velocity: dict,
    margin_data: dict = None,
    provider: str = "azure",
) -> list[dict]:
    """
    Analyze each pairing with LLM and enrich with metrics.
    """
    margin_data = margin_data or {}
    
    # Build name->stats lookup
    name_to_cat = {c["name"]: c for c in category_stats.values()}
    
    results = []
    
    for i, (source, target) in enumerate(pairings):
        print(f"  {i+1}/{len(pairings)}: {source} → {target}")
        
        # LLM validation
        try:
            llm_result = get_llm_validation(source, target, provider=provider)
        except Exception as e:
            print(f"    ⚠️ LLM error: {e}")
            llm_result = {"valid": None, "reason": f"Error: {e}"}
        
        # Get category stats
        src_cat = name_to_cat.get(source, {})
        tgt_cat = name_to_cat.get(target, {})
        
        src_sales = sales_velocity.get(src_cat.get("id"), {})
        tgt_sales = sales_velocity.get(tgt_cat.get("id"), {})
        
        src_margin = margin_data.get(src_cat.get("id"), {})
        tgt_margin = margin_data.get(tgt_cat.get("id"), {})
        
        results.append({
            "source_category": source,
            "target_category": target,
            
            # LLM analysis
            "valid": llm_result.get("valid"),
            "confidence": llm_result.get("confidence", 0),
            "relationship_type": llm_result.get("relationship_type", ""),
            "suggested_weight": llm_result.get("suggested_weight", 0),
            "llm_reason": llm_result.get("reason", ""),
            
            # Source metrics
            "src_product_count": src_cat.get("product_count", 0),
            "src_orders_6mo": src_sales.get("order_count", 0),
            "src_units_6mo": src_sales.get("units_sold", 0),
            "src_revenue_6mo": round(src_sales.get("revenue", 0), 2),
            "src_avg_margin_pct": src_margin.get("avg_margin_pct", ""),
            "src_avg_price": src_margin.get("avg_price", ""),
            
            # Target metrics
            "tgt_product_count": tgt_cat.get("product_count", 0),
            "tgt_orders_6mo": tgt_sales.get("order_count", 0),
            "tgt_units_6mo": tgt_sales.get("units_sold", 0),
            "tgt_revenue_6mo": round(tgt_sales.get("revenue", 0), 2),
            "tgt_avg_margin_pct": tgt_margin.get("avg_margin_pct", ""),
            "tgt_avg_price": tgt_margin.get("avg_price", ""),
            
            # Derived
            "opportunity_score": calculate_opportunity_score(
                llm_result, src_sales, tgt_sales, tgt_margin
            ),
        })
        
        sleep(0.1)  # Rate limit courtesy
    
    return results


def calculate_opportunity_score(
    llm_result: dict, src_sales: dict, tgt_sales: dict, tgt_margin: dict = None
) -> int:
    """
    Calculate opportunity score (1-100) based on:
    - LLM validity and weight
    - Source category sales (high = more traffic to upsell)
    - Target category sales (high = proven demand)
    - Target margin (high = more profitable upsell)
    """
    tgt_margin = tgt_margin or {}
    
    if not llm_result.get("valid"):
        return 0
    
    base_score = llm_result.get("suggested_weight", 50)
    
    # Boost for high-traffic source
    if src_sales.get("order_count", 0) > 50:
        base_score += 10
    elif src_sales.get("order_count", 0) > 20:
        base_score += 5
    
    # Boost for proven target demand
    if tgt_sales.get("order_count", 0) > 30:
        base_score += 5
    
    # Boost for high-margin target (prioritize profitable upsells)
    margin_pct = tgt_margin.get("avg_margin_pct", 0)
    if margin_pct > 50:
        base_score += 10
    elif margin_pct > 35:
        base_score += 5
    
    return min(100, base_score)


def save_results(results: list[dict], output_path: Path):
    """Save to CSV for spreadsheet review."""
    fieldnames = [
        "source_category", "target_category",
        "valid", "confidence", "relationship_type", "suggested_weight",
        "opportunity_score",
        "src_product_count", "src_orders_6mo", "src_units_6mo", "src_revenue_6mo",
        "src_avg_margin_pct", "src_avg_price",
        "tgt_product_count", "tgt_orders_6mo", "tgt_units_6mo", "tgt_revenue_6mo",
        "tgt_avg_margin_pct", "tgt_avg_price",
        "llm_reason",
    ]
    
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Sort by opportunity score descending
        for r in sorted(results, key=lambda x: -x.get("opportunity_score", 0)):
            writer.writerow(r)
    
    print(f"\n✅ Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze category pairings")
    parser.add_argument("--limit", type=int, default=30, help="Max pairings to analyze")
    parser.add_argument("--output", default="data/pairing_analysis.csv", help="Output CSV")
    parser.add_argument("--provider", default="azure", help="LLM provider")
    parser.add_argument("--skip-orders", action="store_true", help="Skip order analysis (faster)")
    parser.add_argument("--skip-margin", action="store_true", help="Skip NetSuite margin lookup")
    args = parser.parse_args()
    
    print("Category Pairing Analysis")
    print("=" * 60)
    
    # Connect to BigCommerce
    try:
        client = BigCommerceClient.from_env()
        result = client.test_connection()
        if not result["success"]:
            print(f"❌ Connection failed: {result.get('error')}")
            return 1
        print(f"✅ Connected to: {result.get('store_name')}\n")
    except Exception as e:
        print(f"❌ {e}")
        return 1
    
    # Gather data
    category_stats = get_category_stats(client)
    print(f"  Found {len(category_stats)} categories")
    
    category_stats = get_product_counts(client, category_stats)
    
    if not args.skip_orders:
        sales_velocity = get_sales_velocity(client, months=6)
        print(f"  Sales data for {len(sales_velocity)} categories")
    else:
        sales_velocity = {}
        print("  (Skipped order analysis)")
    
    # NetSuite margin data
    if not args.skip_margin:
        margin_data = get_category_margins(client)
    else:
        margin_data = {}
        print("  (Skipped margin analysis)")
    
    # Find child categories
    children = find_child_categories(category_stats)
    print(f"  Found {len(children)} child categories")
    
    # Filter out price tiers, promos
    real_cats = filter_real_categories(children)
    print(f"  {len(real_cats)} after filtering promos/price tiers")
    
    # Generate smart pairings
    pairings = generate_smart_pairings(real_cats, limit=args.limit)
    print(f"\nAnalyzing {len(pairings)} pairings with {args.provider}...\n")
    
    # Analyze with LLM + metrics
    results = analyze_pairings(
        pairings, category_stats, sales_velocity, margin_data, args.provider
    )
    
    # Summary
    valid = [r for r in results if r.get("valid")]
    print(f"\n✅ Valid pairings: {len(valid)} / {len(results)}")
    
    if valid:
        print("\nTop opportunities (by score):")
        for r in sorted(valid, key=lambda x: -x.get("opportunity_score", 0))[:5]:
            print(f"  {r['source_category']} → {r['target_category']}")
            print(f"    Score: {r['opportunity_score']}, Type: {r['relationship_type']}")
            print(f"    Source: {r['src_orders_6mo']} orders, Target: {r['tgt_orders_6mo']} orders")
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_results(results, output_path)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
