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
easyupsell analyze              # Generate upsell recommendations
easyupsell review               # Review and approve recommendations
easyupsell export               # Export recommendations to formats
```

## CLI Commands

Run `easyupsell --help` to see all available commands.

| Command | Purpose |
|---------|---------|
| `easyupsell analyze` | Generate upsell recommendations with LLM validation |
| `easyupsell review` | Review and approve recommendations |
| `easyupsell export` | Export recommendations to various formats |
| `easyupsell brands` | Manage priority brand list |
| `easyupsell discover` | Discover hidden inventory |
| `easyupsell config` | Configure API connections |

## LLM Providers

Configure in `.env`:
- **OpenAI** — `OPENAI_API_KEY` (gpt-4o-mini)
- **Ollama** — `OLLAMA_HOST` (local llama3.2)
- **LiteLLM** — `LITELLM_HOST` (Moltbot/Athena proxy)

## Customizing

### Category Validation Prompt
The LLM prompt in validation understands:
- Safety/tactical/industrial supplies context
- Filters unrelated pairings (helmet + magazine = reject)
- Suggests weights based on relationship type
