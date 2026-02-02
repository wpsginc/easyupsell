# EasyUpsell Optimization

Tools and analysis for optimizing [Peasisoft Native Upsell](https://welcome.peasisoft.com/native-upsell/) recommendations on WPSG BigCommerce storefronts.

## Overview

Peasisoft Native Upsell is integrated with our BigCommerce stores. This repo contains data analysis tools to find optimal product relationships for upsell/cross-sell recommendations using our order history and product data.

### Weight-Based Rollup System

Peasisoft supports a priority weight system (1-100) that rolls up when no recommendation exists at a given level:

| Weight Range | Level | Description |
|-------------|-------|-------------|
| 91-100 | Reserved | Global overrides (emergency/promotional) |
| 71-90 | Product | Direct product-to-product recommendations |
| 51-70 | Child Category | Recommendations within subcategory |
| 31-50 | Category | Category-level recommendations |
| 11-30 | Parent Category | Broad category fallbacks |
| 1-10 | Global | Site-wide default recommendations |

## Goal

Analyze order data, product attributes, and category structure to identify:
1. **Frequently bought together** — Products often in the same order
2. **Complementary products** — Items that logically pair (e.g., cleaner + applicator)
3. **Category affinity** — Which categories have strong cross-purchase patterns
4. **Attribute matching** — Products sharing key facets (brand, style, material)

## Data Sources

- **NetSuite** — Order history, product catalog, customer segments
- **BigCommerce** — Category structure, product metadata, current related products

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env   # Add credentials

# Test connectivity
python scripts/test_ns_auth.py
python scripts/test_bc_auth.py
```

## Related Projects

- **pim-sync** — NetSuite ↔ LibrePIM sync (auth patterns from here)
