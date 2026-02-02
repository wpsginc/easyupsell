#!/usr/bin/env python3
"""
Product-Level Accessory Mappings

For specific products that have dedicated accessories (radio → radio strap/holder).
These are MANUAL overrides at the product level, not category level.

Usage:
    python scripts/product_accessories.py --list
    python scripts/product_accessories.py --validate
"""

import argparse
import csv
import json
from pathlib import Path


# =============================================================================
# PRODUCT ACCESSORY MAPPINGS
# These are explicit product-to-product relationships
# Weight: 85-90 (highest non-override)
# =============================================================================

PRODUCT_ACCESSORIES = [
    # Format: (source_sku_pattern, accessory_sku_pattern, weight, reason)
    # Patterns can use * as wildcard
    
    # Radios and accessories
    ("RADIO-*", "RADIO-STRAP-*", 90, "Radio requires strap"),
    ("RADIO-*", "RADIO-HOLDER-*", 88, "Radio holder accessory"),
    ("RADIO-*", "RADIO-BATTERY-*", 85, "Replacement batteries"),
    
    # Helmets and accessories
    ("HELMET-FIRE-*", "HELMET-SHIELD-*", 90, "Helmet face shield"),
    ("HELMET-FIRE-*", "HELMET-LIGHT-*", 85, "Helmet mounted light"),
    ("HELMET-FIRE-*", "HELMET-COVER-*", 82, "Helmet cover/nomex"),
    
    # Boots and care
    ("BOOT-*", "BOOT-LACES-*", 85, "Replacement laces"),
    ("BOOT-*", "BOOT-INSOLE-*", 82, "Comfort insoles"),
    ("BOOT-*", "BOOT-CARE-*", 80, "Boot care products"),
    
    # Flashlights
    ("LIGHT-*", "LIGHT-BATTERY-*", 88, "Batteries for light"),
    ("LIGHT-*", "LIGHT-HOLSTER-*", 85, "Light holster"),
    ("LIGHT-*", "LIGHT-CHARGER-*", 82, "Charger for rechargeable"),
    
    # Body armor / carriers
    ("CARRIER-*", "CARRIER-POUCH-*", 85, "MOLLE pouches"),
    ("CARRIER-*", "CARRIER-PLATE-*", 88, "Armor plates"),
]


def match_sku_pattern(sku: str, pattern: str) -> bool:
    """Check if SKU matches a wildcard pattern."""
    if "*" not in pattern:
        return sku == pattern
    
    parts = pattern.split("*")
    if len(parts) == 2:
        prefix, suffix = parts
        return sku.startswith(prefix) and sku.endswith(suffix)
    
    # Simple prefix match
    return sku.startswith(parts[0])


def find_product_accessories(
    products: list[dict],
    mappings: list[tuple] = PRODUCT_ACCESSORIES,
) -> list[dict]:
    """
    Match products to their accessories using defined mappings.
    
    Returns list of specific SKU-to-SKU recommendations.
    """
    recommendations = []
    
    # Index products by SKU
    products_by_sku = {p.get("sku"): p for p in products if p.get("sku")}
    all_skus = list(products_by_sku.keys())
    
    for source_pattern, accessory_pattern, weight, reason in mappings:
        # Find matching source products
        source_skus = [s for s in all_skus if match_sku_pattern(s, source_pattern)]
        accessory_skus = [s for s in all_skus if match_sku_pattern(s, accessory_pattern)]
        
        if not source_skus or not accessory_skus:
            continue
        
        for source_sku in source_skus:
            for accessory_sku in accessory_skus:
                source_product = products_by_sku.get(source_sku, {})
                accessory_product = products_by_sku.get(accessory_sku, {})
                
                recommendations.append({
                    "source_sku": source_sku,
                    "source_name": source_product.get("name", ""),
                    "accessory_sku": accessory_sku,
                    "accessory_name": accessory_product.get("name", ""),
                    "weight": weight,
                    "reason": reason,
                    "level": "product",
                })
    
    return recommendations


def load_products(products_path: Path) -> list[dict]:
    """Load products from export."""
    if not products_path.exists():
        return []
    
    with open(products_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Product-level accessory mappings")
    parser.add_argument("--list", action="store_true", help="List defined mappings")
    parser.add_argument("--validate", action="store_true", help="Check mappings against products")
    parser.add_argument("--products", default="data/products.json", help="Products file")
    parser.add_argument("--output", default="data/product_accessories", help="Output path")
    args = parser.parse_args()
    
    print("Product-Level Accessory Mappings")
    print("=" * 50)
    
    if args.list:
        print("\nDefined accessory mappings:")
        for src, acc, weight, reason in PRODUCT_ACCESSORIES:
            print(f"  {src} → {acc} (w={weight})")
            print(f"    {reason}")
        return 0
    
    # Load products
    products_path = Path(args.products)
    products = load_products(products_path)
    
    if not products:
        print(f"⚠️  No products found at {products_path}")
        print("\nTo use this script:")
        print("  1. Export products from BigCommerce")
        print("  2. Or run with --list to see defined mappings")
        return 0
    
    print(f"Loaded {len(products)} products\n")
    
    # Find matches
    recommendations = find_product_accessories(products, PRODUCT_ACCESSORIES)
    print(f"Found {len(recommendations)} product-level recommendations\n")
    
    if recommendations:
        print("Sample recommendations:")
        for r in recommendations[:10]:
            print(f"  {r['source_sku']} → {r['accessory_sku']} (w={r['weight']})")
            print(f"    {r['reason']}")
        print()
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # JSON
    with open(output_path.with_suffix(".json"), "w") as f:
        json.dump(recommendations, f, indent=2)
    print(f"Saved: {output_path.with_suffix('.json')}")
    
    # CSV
    if recommendations:
        with open(output_path.with_suffix(".csv"), "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "source_sku", "accessory_sku", "weight", "level", "reason"
            ])
            writer.writeheader()
            for r in recommendations:
                writer.writerow({
                    "source_sku": r["source_sku"],
                    "accessory_sku": r["accessory_sku"],
                    "weight": r["weight"],
                    "level": r["level"],
                    "reason": r["reason"],
                })
        print(f"Saved: {output_path.with_suffix('.csv')}")
    
    return 0


if __name__ == "__main__":
    exit(main())
