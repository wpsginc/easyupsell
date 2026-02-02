#!/usr/bin/env python3
"""
Export BigCommerce Category Structure

Exports the full category tree with parent-child relationships for analysis.

Usage:
    python scripts/export_categories.py
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigcommerce import BigCommerceClient


def flatten_tree(tree: list[dict], parent_id: int = 0, depth: int = 0) -> list[dict]:
    """Flatten category tree into list with parent info."""
    results = []
    
    for node in tree:
        results.append({
            "id": node.get("id"),
            "name": node.get("name"),
            "parent_id": parent_id,
            "depth": depth,
            "url": node.get("url", ""),
        })
        
        # Recurse into children
        children = node.get("children", [])
        if children:
            results.extend(flatten_tree(children, parent_id=node.get("id"), depth=depth + 1))
    
    return results


def main():
    print("BigCommerce Category Export")
    print("=" * 50)
    
    try:
        client = BigCommerceClient.from_env()
        print(f"Store: {client.store_hash}")
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    
    # Test connection
    result = client.test_connection()
    if not result["success"]:
        print(f"❌ Connection failed: {result.get('error')}")
        return 1
    print(f"✅ Connected to: {result.get('store_name')}\n")
    
    # Get category tree
    print("Fetching category tree...")
    tree = client.get_category_tree()
    
    # Flatten for analysis
    categories = flatten_tree(tree)
    print(f"Found {len(categories)} categories\n")
    
    # Summarize by depth
    depth_counts = {}
    for cat in categories:
        d = cat["depth"]
        depth_counts[d] = depth_counts.get(d, 0) + 1
    
    print("Categories by depth:")
    for depth, count in sorted(depth_counts.items()):
        level = ["Root", "Parent", "Category", "Child", "Sub-child"][depth] if depth < 5 else f"Level {depth}"
        print(f"  {level} (depth {depth}): {count}")
    print()
    
    # Save results
    output_path = Path("data/categories")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # CSV
    csv_path = output_path.with_suffix(".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "parent_id", "depth", "url"])
        writer.writeheader()
        writer.writerows(categories)
    print(f"Saved: {csv_path}")
    
    # JSON (with full tree structure)
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump({"tree": tree, "flat": categories}, f, indent=2)
    print(f"Saved: {json_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
