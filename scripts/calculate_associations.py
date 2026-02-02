#!/usr/bin/env python3
"""
Association Rules Calculator

Takes co-occurrence data and calculates confidence, lift, and assigns weights
for the Peasisoft weight-based rollup system.

Usage:
    python scripts/calculate_associations.py
    python scripts/calculate_associations.py --input data/cooccurrence.json --min-lift 2.0
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_cooccurrence(input_path: Path) -> list[dict]:
    """Load co-occurrence data from JSON or CSV."""
    if input_path.suffix == ".json":
        with open(input_path) as f:
            return json.load(f)
    else:
        with open(input_path) as f:
            return list(csv.DictReader(f))


def calculate_product_frequencies(cooccurrence: list[dict]) -> dict[str, int]:
    """Estimate product frequency from co-occurrence data."""
    freq = defaultdict(int)
    
    for pair in cooccurrence:
        # Each appearance in a pair means the product was in that order
        freq[pair["product_a"]] += int(pair["count"])
        freq[pair["product_b"]] += int(pair["count"])
    
    return freq


def calculate_associations(
    cooccurrence: list[dict],
    product_freq: dict[str, int],
    total_orders: int,
    min_confidence: float = 0.1,
    min_lift: float = 1.5,
) -> list[dict]:
    """
    Calculate association rules from co-occurrence data.
    
    For each pair (A, B), calculates:
    - confidence(A→B): P(B|A) = P(A∩B) / P(A)
    - lift(A→B): confidence / P(B) = P(A∩B) / (P(A) * P(B))
    
    Returns directional rules (A recommends B and B recommends A separately).
    """
    rules = []
    
    for pair in cooccurrence:
        sku_a = pair["product_a"]
        sku_b = pair["product_b"]
        count = int(pair["count"])
        
        freq_a = product_freq.get(sku_a, count)
        freq_b = product_freq.get(sku_b, count)
        
        # Avoid division by zero
        if freq_a == 0 or freq_b == 0 or total_orders == 0:
            continue
        
        support = count / total_orders
        
        # Rule: A → B (buying A, recommend B)
        conf_a_to_b = count / freq_a
        lift_a_to_b = conf_a_to_b / (freq_b / total_orders) if freq_b > 0 else 0
        
        if conf_a_to_b >= min_confidence and lift_a_to_b >= min_lift:
            rules.append({
                "source_sku": sku_a,
                "recommend_sku": sku_b,
                "count": count,
                "support": round(support, 6),
                "confidence": round(conf_a_to_b, 4),
                "lift": round(lift_a_to_b, 4),
            })
        
        # Rule: B → A (buying B, recommend A)
        conf_b_to_a = count / freq_b
        lift_b_to_a = conf_b_to_a / (freq_a / total_orders) if freq_a > 0 else 0
        
        if conf_b_to_a >= min_confidence and lift_b_to_a >= min_lift:
            rules.append({
                "source_sku": sku_b,
                "recommend_sku": sku_a,
                "count": count,
                "support": round(support, 6),
                "confidence": round(conf_b_to_a, 4),
                "lift": round(lift_b_to_a, 4),
            })
    
    # Sort by lift descending
    rules.sort(key=lambda x: x["lift"], reverse=True)
    
    return rules


def assign_weights(rules: list[dict]) -> list[dict]:
    """
    Assign Peasisoft weights based on confidence/lift scores.
    
    Weight ranges:
    - 71-90: Strong product-level recommendations
    - Higher confidence/lift = higher weight within range
    """
    for rule in rules:
        # Score based on confidence (60%) and lift (40%)
        score = (rule["confidence"] * 0.6) + (min(rule["lift"], 10) / 10 * 0.4)
        
        # Map to weight range 71-90
        weight = int(71 + score * 19)
        weight = max(71, min(90, weight))  # Clamp to range
        
        rule["weight"] = weight
    
    return rules


def save_results(rules: list[dict], output_path: Path):
    """Save rules to CSV and JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # CSV
    csv_path = output_path.with_suffix(".csv")
    fieldnames = ["source_sku", "recommend_sku", "weight", "confidence", "lift", "count", "support"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rules)
    print(f"Saved: {csv_path}")
    
    # JSON
    json_path = output_path.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(rules, f, indent=2)
    print(f"Saved: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="Calculate association rules")
    parser.add_argument("--input", default="data/cooccurrence.json", help="Input co-occurrence file")
    parser.add_argument("--output", default="data/associations", help="Output path (without extension)")
    parser.add_argument("--min-confidence", type=float, default=0.1, help="Minimum confidence threshold")
    parser.add_argument("--min-lift", type=float, default=1.5, help="Minimum lift threshold")
    parser.add_argument("--total-orders", type=int, default=10000, help="Total orders for support calculation")
    args = parser.parse_args()
    
    print("Association Rules Calculator")
    print("=" * 50)
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        print("Run analyze_cooccurrence.py first.")
        return 1
    
    # Load data
    cooccurrence = load_cooccurrence(input_path)
    print(f"Loaded {len(cooccurrence)} product pairs\n")
    
    # Calculate frequencies
    product_freq = calculate_product_frequencies(cooccurrence)
    print(f"Found {len(product_freq)} unique products")
    
    # Calculate rules
    rules = calculate_associations(
        cooccurrence,
        product_freq,
        total_orders=args.total_orders,
        min_confidence=args.min_confidence,
        min_lift=args.min_lift,
    )
    print(f"Generated {len(rules)} association rules\n")
    
    # Assign weights
    rules = assign_weights(rules)
    
    if rules:
        print("Top 10 recommendations by lift:")
        for r in rules[:10]:
            print(f"  {r['source_sku']} → {r['recommend_sku']}")
            print(f"    Weight: {r['weight']}, Confidence: {r['confidence']:.1%}, Lift: {r['lift']:.2f}")
        print()
    
    # Save
    save_results(rules, Path(args.output))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
