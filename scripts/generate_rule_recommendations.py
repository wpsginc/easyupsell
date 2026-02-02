#!/usr/bin/env python3
"""
Attribute-Based Recommendation Rules

Defines logical product pairings based on category/type relationships,
independent of sparse sales data. These are merchandising-driven rules.

Usage:
    python scripts/generate_rule_recommendations.py
"""

import csv
import json
from pathlib import Path


# =============================================================================
# MERCHANDISING RULES
# Define complementary relationships between product types/categories
# =============================================================================

# Format: (source_type, recommend_type, weight, reason)
# Weight range 71-90 for product-level rules
COMPLEMENTARY_RULES = [
    # Footwear accessories
    ("boots", "socks", 85, "Footwear + socks pairing"),
    ("boots", "boot_care", 82, "Footwear + care products"),
    ("shoes", "socks", 85, "Footwear + socks pairing"),
    ("shoes", "shoe_care", 82, "Footwear + care products"),
    ("shoes", "insoles", 80, "Footwear + comfort accessories"),
    
    # Flooring
    ("flooring", "underlayment", 88, "Flooring + underlayment required"),
    ("flooring", "adhesive", 85, "Flooring + installation materials"),
    ("flooring", "transition_strips", 82, "Flooring + finishing accessories"),
    ("flooring", "cleaning_kit", 80, "Flooring + maintenance"),
    
    # Cleaning / care products
    ("cleaner", "applicator", 88, "Cleaner + applicator bundle"),
    ("cleaner", "microfiber_cloth", 85, "Cleaner + application supplies"),
    ("polish", "applicator", 85, "Polish + applicator bundle"),
    
    # Hardware
    ("hardware", "mounting_kit", 85, "Hardware + mounting accessories"),
    ("hardware", "fasteners", 82, "Hardware + fasteners"),
    
    # Samples → Full products (cross-sell)
    ("sample", "full_product", 90, "Sample → full product conversion"),
]

# Category-level affinities (for rollup when no product rule exists)
# Format: (source_category, recommend_category, weight, reason)
# Weight range 51-70 for category-level
CATEGORY_AFFINITIES = [
    ("Footwear", "Footwear Accessories", 65, "Category affinity"),
    ("Flooring", "Flooring Accessories", 65, "Category affinity"),
    ("Cleaning Supplies", "Applicators", 62, "Category affinity"),
    ("Paint", "Painting Supplies", 65, "Category affinity"),
]


def load_products(products_path: Path) -> list[dict]:
    """Load product catalog with categories/types."""
    if not products_path.exists():
        print(f"⚠️  Products file not found: {products_path}")
        print("   Run export script first or provide product data.")
        return []
    
    with open(products_path) as f:
        return json.load(f)


def classify_product(product: dict) -> list[str]:
    """
    Extract product type classifications from categories/attributes.
    Returns list of matched type keywords.
    """
    types = []
    
    # Check product name and categories for keywords
    name = product.get("name", "").lower()
    categories = [c.get("name", "").lower() for c in product.get("categories", [])]
    all_text = name + " " + " ".join(categories)
    
    # Match against rule keywords
    keywords = ["boots", "shoes", "socks", "flooring", "underlayment", 
                "cleaner", "polish", "applicator", "sample", "hardware"]
    
    for kw in keywords:
        if kw in all_text:
            types.append(kw)
    
    return types


def generate_recommendations(
    products: list[dict],
    rules: list[tuple] = COMPLEMENTARY_RULES,
) -> list[dict]:
    """
    Generate recommendations based on attribute rules.
    
    For each product, find matching rules and recommend appropriate products.
    """
    recommendations = []
    
    # Index products by type
    products_by_type = {}
    for p in products:
        types = classify_product(p)
        for t in types:
            if t not in products_by_type:
                products_by_type[t] = []
            products_by_type[t].append(p)
    
    print(f"Product types found: {list(products_by_type.keys())}")
    
    # Apply rules
    for source_type, recommend_type, weight, reason in rules:
        source_products = products_by_type.get(source_type, [])
        target_products = products_by_type.get(recommend_type, [])
        
        if not source_products or not target_products:
            continue
        
        for source in source_products:
            for target in target_products:
                if source.get("id") == target.get("id"):
                    continue  # Don't recommend self
                
                recommendations.append({
                    "source_sku": source.get("sku", ""),
                    "source_name": source.get("name", ""),
                    "recommend_sku": target.get("sku", ""),
                    "recommend_name": target.get("name", ""),
                    "weight": weight,
                    "rule_type": "attribute",
                    "reason": reason,
                })
    
    return recommendations


def save_recommendations(recommendations: list[dict], output_path: Path):
    """Save to CSV and JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # CSV
    csv_path = output_path.with_suffix(".csv")
    fieldnames = ["source_sku", "recommend_sku", "weight", "rule_type", "reason", 
                  "source_name", "recommend_name"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(recommendations)
    print(f"Saved: {csv_path}")
    
    # JSON
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(recommendations, f, indent=2)
    print(f"Saved: {json_path}")


def main():
    print("Attribute-Based Recommendation Generator")
    print("=" * 50)
    
    # Try to load products
    products_path = Path("data/products.json")
    products = load_products(products_path)
    
    if not products:
        print("\nGenerating sample rule output (no products loaded)...")
        print("\nDefined complementary rules:")
        for src, tgt, weight, reason in COMPLEMENTARY_RULES[:10]:
            print(f"  {src} → {tgt} (weight {weight}): {reason}")
        
        print("\nTo generate real recommendations:")
        print("  1. Export products: python scripts/export_products.py")
        print("  2. Re-run this script")
        return 0
    
    print(f"Loaded {len(products)} products\n")
    
    recommendations = generate_recommendations(products, COMPLEMENTARY_RULES)
    print(f"Generated {len(recommendations)} recommendations\n")
    
    if recommendations:
        print("Sample recommendations:")
        for r in recommendations[:5]:
            print(f"  {r['source_sku']} → {r['recommend_sku']} (w={r['weight']})")
        print()
    
    save_recommendations(recommendations, Path("data/attribute_recommendations"))
    
    return 0


if __name__ == "__main__":
    exit(main())
