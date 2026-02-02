# EasyUpsell Optimization

Tools for optimizing [Peasisoft Native Upsell](https://welcome.peasisoft.com/native-upsell/) recommendations on WPSG BigCommerce storefronts.

## The Problem

Co-purchase data is **sparse** — customers rarely buy complementary items together (boots + socks). We need a **hybrid approach**:

1. **Attribute-based rules** — Define logical pairings (boots → socks, flooring → underlayment)
2. **Cross-sell gap analysis** — Identify products frequently bought alone
3. **Sparse co-occurrence** — Validate rules with what little data exists

## Weight-Based Rollup System

Peasisoft supports priority weights (1-100) with rollup:

| Weight | Level | Strategy |
|--------|-------|----------|
| 91-100 | Reserved | Global overrides (promotions) |
| 71-90 | Product | Attribute-based rules |
| 51-70 | Category | Category affinity mappings |
| 31-50 | Parent | Broad category fallbacks |
| 1-10 | Global | Site-wide defaults |

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env   # Add BC credentials

# Test connection
python scripts/test_bc_auth.py

# Analysis pipeline
python scripts/analyze_bc_orders.py       # Find cross-sell gaps
python scripts/export_categories.py       # Category structure
python scripts/generate_rule_recommendations.py  # Apply merchandising rules
```

## Output Files

| File | Description |
|------|-------------|
| `data/cross_sell_gaps.csv` | Products frequently bought alone (opportunities) |
| `data/bc_cooccurrence.json` | Actual co-purchase data (likely sparse) |
| `data/attribute_recommendations.json` | Rule-based recommendations with weights |

## Customizing Rules

Edit `scripts/generate_rule_recommendations.py` to define your merchandising rules:

```python
COMPLEMENTARY_RULES = [
    ("boots", "socks", 85, "Footwear + socks pairing"),
    ("flooring", "underlayment", 88, "Required accessory"),
    # Add your rules here...
]
```
