# EasyUpsell Optimization

Tools for optimizing [Peasisoft Native Upsell](https://welcome.peasisoft.com/native-upsell/) recommendations on WPSG BigCommerce storefronts.

## The Problem

1. **Sparse co-purchase data** — Customers rarely buy complementary items together
2. **Noise in data** — Random pairings (fire helmet + gun magazine) are not useful
3. **Need to CHANGE behavior** — Recommend what customers SHOULD buy together

## Solution: Hybrid Category-First Approach

| Level | Weight | Strategy |
|-------|--------|----------|
| Product Accessories | 85-90 | Explicit mappings (radio → radio strap) |
| Child Category | 51-70 | **LLM-validated** pairings (Tactical Pants → Tactical Belts) |
| Parent Category | 31-50 | Broad fallbacks |
| Global | 1-10 | Site-wide defaults |

**Key insight:** Work at **child category level** (Tactical Pants, not Pants) with LLM validation to filter nonsense.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env   # Add BC + LLM credentials

# Analysis pipeline
python scripts/export_categories.py                    # Get category tree
python scripts/validate_category_pairings.py          # LLM validates pairings
python scripts/product_accessories.py --validate      # Product-level overrides
```

## Scripts

| Script | Purpose |
|--------|---------|
| `validate_category_pairings.py` | LLM validates child category pairings |
| `product_accessories.py` | Explicit product→accessory mappings |
| `analyze_bc_orders.py` | Find cross-sell gaps (products bought alone) |
| `export_categories.py` | Export BC category structure |

## LLM Providers

Configure in `.env`:
- **OpenAI** — `OPENAI_API_KEY` (gpt-4o-mini)
- **Ollama** — `OLLAMA_HOST` (local llama3.2)
- **LiteLLM** — `LITELLM_HOST` (Moltbot/Athena proxy)

## Customizing

### Product Accessories
Edit `scripts/product_accessories.py`:
```python
PRODUCT_ACCESSORIES = [
    ("RADIO-*", "RADIO-STRAP-*", 90, "Radio requires strap"),
    ("HELMET-FIRE-*", "HELMET-SHIELD-*", 90, "Face shield"),
]
```

### Category Validation Prompt
The LLM prompt in `validate_category_pairings.py` understands:
- Safety/tactical/industrial supplies context
- Filters unrelated pairings (helmet + magazine = reject)
- Suggests weights based on relationship type
