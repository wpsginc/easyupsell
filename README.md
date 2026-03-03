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
cp .env.template .env   # Add BC + LLM + PRE credentials

# Analysis pipeline
easyupsell discover --all           # Build catalog gap candidates
easyupsell opportunities            # Generate Phase 3 opportunities report
easyupsell opportunities --skip-llm  # Skip LLM enrichment for quick preview
easyupsell analyze              # Generate upsell recommendations
easyupsell review               # Review and approve recommendations
easyupsell export               # Export recommendations to formats

# Phase 4 service layer
easyupsell serve                 # Start FastAPI recommendation API on port 8090
easyupsell sync netsuite         # Push approved recommendations to NetSuite
```

For legacy artifacts, continue using existing CSV/XLSX outputs.
Phase 4 also writes canonical data to `data/recommendations.db`.

Phase 3 flow note: `easyupsell discover --all` writes `data/catalog_gaps.csv`.
`easyupsell opportunities` consumes that file by default to build
`data/new_product_opportunities.xlsx`.

If you already have historical CSVs, migrate them with:

```bash
python scripts/migrate_csv_to_db.py \
  --csv data/full_recommendations_v2.csv \
  --xlsx data/dark_horse_discovery_glm_q8_reviewed.xlsx \
  --db data/recommendations.db
```

## CLI Commands

Run `easyupsell --help` to see all available commands.

| Command | Purpose |
|---------|---------|
| `easyupsell analyze` | Generate upsell recommendations with LLM validation |
| `easyupsell review` | Review and approve recommendations |
| `easyupsell export` | Export recommendations to various formats |
| `easyupsell opportunities` | Build sourcing opportunities from catalog gaps |
| `easyupsell serve` | Start read-only recommendation API (`/v1/...`) |
| `easyupsell sync netsuite` | Push approved recommendations into NetSuite |
| `easyupsell brands` | Manage priority brand list |
| `easyupsell discover` | Discover hidden inventory |
| `easyupsell opportunities --skip-llm` | Skip LLM enrichment while writing report |
| `easyupsell config` | Configure API connections |

## Recommendation API

The Phase 4 API is a read-only service for downstream systems.

Default endpoint host/port are `0.0.0.0:8090` and can be overridden with
`--host` / `--port` or config variables in `config.toml`.

Endpoints:

- `GET /v1/health`
- `GET /v1/recommendations/category/{category_name}`
- `GET /v1/recommendations/sku/{sku}`
- `GET /v1/recommendations/netsuite/{netsuite_id}`

API auth:

- Provide `PRE_API_KEYS` in `.env` as a comma-separated list.
- Send `X-API-Key` header on all endpoints except `/v1/health`.
- Example:
  - `curl http://localhost:8090/v1/health`
  - `curl -H "X-API-Key: my-key" "http://localhost:8090/v1/recommendations/category/Tactical%20Boots"`

## NetSuite Sync

After review (`status=active`) run:

```bash
easyupsell sync netsuite --max-rpm 40
```

Useful flags:

- `--dry-run` build payloads and validate mappings with zero API calls
- `--force` include already-synced records

## LLM Providers

- **OpenAI** — `OPENAI_API_KEY` (gpt-4o-mini)
- **Ollama** — `OLLAMA_HOST` (local llama3.2)
- **LiteLLM** — `LITELLM_HOST` (Moltbot/Athena proxy)

## Data & API Runtime

- `PRE_DB_PATH` (optional): override DB path (defaults to `data/recommendations.db`)
- `PRE_API_KEYS`: comma-separated API keys required by `easyupsell serve`
- `PRE_API_KEY_REQUIRED=false` to disable key checks for local testing

## Customizing

### Category Validation Prompt
The LLM prompt in validation understands:
- Safety/tactical/industrial supplies context
- Filters unrelated pairings (helmet + magazine = reject)
- Suggests weights based on relationship type
