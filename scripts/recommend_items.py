#!/usr/bin/env python3
"""
Category → Item Recommendation Generator

For each source category, find high-value ITEMS to recommend at checkout.
Uses LLM to validate that items make sense for category buyers.

Output CSV columns:
- source_category: Category the buyer is shopping in
- recommended_sku: Specific item to recommend
- recommended_name: Item name
- recommended_price: Item price
- recommended_margin_pct: Item margin (if NS data available)
- llm_valid: Does this make sense?
- llm_reason: Why/why not
- opportunity_score: Priority ranking

Usage:
    python scripts/recommend_items.py --limit 20
    python scripts/recommend_items.py --source-category "Tactical Pants"
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce import BigCommerceClient

# Try NetSuite for margin data
try:
    from netsuite import NetSuiteClient
    HAS_NETSUITE = True
except ImportError:
    HAS_NETSUITE = False

# Import LLM validation
sys.path.insert(0, str(Path(__file__).parent))
from validate_category_pairings import get_llm_validation


def get_high_value_items(bc_client: BigCommerceClient, limit: int = 200) -> list[dict]:
    """
    Get high-value items that make good upsell candidates.
    Filters for: in stock, visible, reasonable price range.
    """
    print("Fetching high-value item candidates...")
    
    products = bc_client.get_products(limit=500)
    
    # Filter for good upsell candidates
    candidates = []
    for p in products:
        price = float(p.get("price", 0) or 0)
        
        # Good upsell = $15-200, visible, not discontinued
        if 15 <= price <= 200:
            if p.get("is_visible", True):
                candidates.append({
                    "id": p["id"],
                    "sku": p.get("sku", ""),
                    "name": p.get("name", "")[:60],
                    "price": price,
                    "categories": p.get("categories", []),
                    "inventory": p.get("inventory_level", 0),
                })
    
    # Sort by price (mid-range = more likely to convert)
    candidates.sort(key=lambda x: abs(x["price"] - 50))  # Sweet spot around $50
    
    print(f"  Found {len(candidates)} upsell candidates ($15-$200)")
    return candidates[:limit]


def get_category_map(bc_client: BigCommerceClient) -> tuple[dict, dict]:
    """Return (id_to_name, name_to_id) mappings."""
    cats = bc_client.get_categories()
    id_to_name = {c["id"]: c["name"] for c in cats}
    name_to_id = {c["name"]: c["id"] for c in cats}
    return id_to_name, name_to_id


def get_child_categories(bc_client: BigCommerceClient) -> list[dict]:
    """Get leaf categories (no children)."""
    cats = bc_client.get_categories()
    parent_ids = set(c.get("parent_id", 0) for c in cats)
    
    # Filter: leaf, not root, not promo/price tier
    excluded = ["$", "sale", "clearance", "promo", "new arrival", "gift", "shop all"]
    
    children = []
    for c in cats:
        if c["id"] not in parent_ids and c.get("parent_id", 0) != 0:
            name_lower = c["name"].lower()
            if not any(ex in name_lower for ex in excluded):
                children.append(c)
    
    return children


def validate_item_for_category(
    category_name: str,
    item_name: str,
    item_price: float,
    provider: str = "azure",
) -> dict:
    """
    Ask LLM if this specific item makes sense for category buyers.
    """
    # Use existing validation - it already has store context
    return get_llm_validation(category_name, item_name, provider=provider)


def find_recommendations_for_category(
    category: dict,
    all_items: list[dict],
    id_to_name: dict,
    provider: str = "azure",
    max_items: int = 5,
) -> list[dict]:
    """
    Find best item recommendations for a category.
    - Items should NOT be in the same category (cross-sell, not same-sell)
    - LLM validates the pairing
    """
    category_id = category["id"]
    category_name = category["name"]
    
    # Items NOT in this category
    cross_sell_items = [
        item for item in all_items 
        if category_id not in item["categories"]
    ]
    
    # Sample items from diverse categories
    seen_cats = set()
    diverse_items = []
    for item in cross_sell_items:
        item_cats = tuple(sorted(item["categories"]))
        if item_cats not in seen_cats:
            diverse_items.append(item)
            seen_cats.add(item_cats)
            if len(diverse_items) >= max_items * 2:
                break
    
    # Validate each with LLM
    recommendations = []
    for item in diverse_items[:max_items]:
        result = validate_item_for_category(
            category_name, item["name"], item["price"], provider
        )
        
        # Get item's category names for context
        item_cat_names = [id_to_name.get(c, "") for c in item["categories"][:2]]
        
        recommendations.append({
            "source_category": category_name,
            "recommended_sku": item["sku"],
            "recommended_name": item["name"],
            "recommended_price": item["price"],
            "recommended_categories": " | ".join(item_cat_names),
            "llm_valid": result.get("valid"),
            "llm_confidence": result.get("confidence", 0),
            "relationship_type": result.get("relationship_type", ""),
            "llm_reason": result.get("reason", ""),
        })
        
        sleep(0.1)
    
    return recommendations


def main():
    parser = argparse.ArgumentParser(description="Generate item recommendations per category")
    parser.add_argument("--limit", type=int, default=10, help="Number of source categories to analyze")
    parser.add_argument("--items-per-category", type=int, default=5, help="Candidate items per category")
    parser.add_argument("--source-category", help="Analyze specific category only")
    parser.add_argument("--output", default="data/item_recommendations.csv", help="Output CSV")
    parser.add_argument("--provider", default="azure", help="LLM provider")
    args = parser.parse_args()
    
    print("Category → Item Recommendation Generator")
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
    
    # Get data
    id_to_name, name_to_id = get_category_map(client)
    high_value_items = get_high_value_items(client, limit=200)
    
    if args.source_category:
        # Single category mode
        cat_id = name_to_id.get(args.source_category)
        if not cat_id:
            print(f"❌ Category not found: {args.source_category}")
            return 1
        categories = [{"id": cat_id, "name": args.source_category}]
    else:
        # Multi-category mode
        categories = get_child_categories(client)
        print(f"  Found {len(categories)} child categories")
        categories = categories[:args.limit]
    
    # Generate recommendations
    all_recommendations = []
    
    for i, cat in enumerate(categories):
        print(f"\n[{i+1}/{len(categories)}] {cat['name']}")
        
        recs = find_recommendations_for_category(
            cat, high_value_items, id_to_name,
            provider=args.provider,
            max_items=args.items_per_category,
        )
        
        valid_count = sum(1 for r in recs if r["llm_valid"])
        print(f"  → {valid_count}/{len(recs)} valid recommendations")
        
        all_recommendations.extend(recs)
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = [
        "source_category", "recommended_sku", "recommended_name",
        "recommended_price", "recommended_categories",
        "llm_valid", "llm_confidence", "relationship_type", "llm_reason",
    ]
    
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Sort: valid first, then by confidence
        for r in sorted(all_recommendations, key=lambda x: (-int(x.get("llm_valid") or 0), -x.get("llm_confidence", 0))):
            writer.writerow(r)
    
    # Summary
    valid = [r for r in all_recommendations if r.get("llm_valid")]
    print(f"\n✅ Valid recommendations: {len(valid)} / {len(all_recommendations)}")
    print(f"✅ Saved: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
