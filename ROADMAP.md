# EasyUpsell Product Roadmap

**Status:** 🟢 Active Development

> ⚠️ **RENAME PENDING**: This project will be renamed to **PRE (Product Recommendation Engine)** - see Phase 5 below.

## Vision
A **merchandising intelligence tool** — not an IT tool. Built for merchandisers, category managers, and buyers to:
- **Research** previous sales patterns and co-purchase behavior
- **Discover** upsell opportunities on current products (including hidden inventory nobody knows about)
- **Source** new product ideas by identifying complementary items we don't carry yet
- **Decide** with confidence using AI-surfaced candidates + enriched business metrics, where humans always make the final call

---

## Phase 1: CLI Foundation ✅

### 1.1 Core Analysis Engine (Done)
- [x] BigCommerce V3 API integration
- [x] Category hierarchy parsing  
- [x] Order history analysis (sales velocity)
- [x] LLM validation via Azure OpenAI (GPT-5.2)
- [x] Priority brand boosting (Streamlight, Benchmade, etc.)
- [x] **Batched LLM calls** — 6 items per prompt (2026-02-03)
- [x] **Enterprise Hardening** — Config module, Pydantic, no hardcoded paths
- [x] **BigQuery integration** — category + item sales from BQ (fast mode)
- [x] **NetSuite ID extraction** — from `bin_picking_number` + enrichment fallback
- [x] **Excel output** — single workbook, formatted headers, % formatting, red/green row coloring
- [x] **Full production run** — 8,346 recommendations across 758 categories (2026-02-10)
- [x] Allow same-category recommendations (helmet→helmet light)
- [x] Resume capability for interrupted runs
- [x] Progress bar for large batches

---

## Phase 2: Dark Horse Item Analysis ✅

"Steak and potato" items we already carry but aren't being bought together.

### 2.1 Hidden Inventory Detection
- [x] For each high-traffic category, ask LLM: "What complementary products SHOULD pair with this category?"
- [x] Cross-reference LLM suggestions against FULL catalog (not just the 300 candidate pool)
- [x] Surface existing SKUs with **zero copurchase data** — items we carry that nobody knows pair well
- [x] Full production run: 1,274 categories → 8,067 pairings, 4,314 gaps (GLM-4.5 Air Q8)
- [x] 2-pass brainstorm (knowledge pass + JSON format pass) for optimal MoE routing on local models

### 2.2 LLM Review Pass
- [x] Post-processing review command (`easyupsell review`) — batch-score pairings 1-5 with a second model
- [x] Separate keeps/rejects into green/red Excel sheets
- [x] **Restartable long-running processes** — checkpoint scored results every N pairings to disk (JSON) so interrupted runs can resume from last checkpoint instead of restarting from scratch
- [x] Resume flag: `easyupsell review --resume` picks up from last checkpoint file

### 2.3 Output
- [x] Separate "Dark Horse" sheet/report in Excel (pairings + gaps + failures)
- [x] Include SKU, current sales velocity, margin, copurchase count, and LLM reasoning for why it should pair
- [x] Flag items with high margin + zero copurchase as highest-priority opportunities (gold ★ rows)

---

## Phase 3: Opportunity Add-On Suggestions

Products we **don't carry at all** but would sell well as add-ons.

### 3.1 Gap Analysis
- [ ] LLM "what's missing?" analysis per category
  - Feed category name + current catalog → ask "what complementary products should we carry?"
- [ ] Suggestions that match NO existing SKU → flag as "New Product Opportunity"
- [ ] Examples: Boots → shoe trees, leather conditioner | Helmets → anti-fog wipes | Radios → speaker mics

### 3.2 Output
- [ ] Separate "New Product Opportunities" report
- [ ] Include suggested product description, estimated price range, target categories
- [ ] Actionable buying leads for the merchandising/purchasing team

---

## Phase 4: Integration — NetSuite Queryable API ✅

Build PRE into a service that NetSuite and other downstream systems can query for structured recommendation data.

### 4.1 Service API
- [x] REST endpoints: `/v1/recommendations/category/{category_name}`, `/v1/recommendations/sku/{sku}`, `/v1/recommendations/netsuite/{netsuite_id}`, `/v1/health`
- [x] Read-only API with structured status/error responses and request IDs
- [x] API auth via `PRE_API_KEYS` + `X-API-Key` header
- [x] `pre serve` entrypoint to run the API (`uvicorn src.api:app`)
- [x] Canonical SQLite store with upsert + sync-state tracking

### 4.2 NetSuite Integration
- [x] SQLite-backed read path for approved recommendations to sync
- [x] `pre sync netsuite` command with rate limiting, retries, orphan handling, and dead-letter logging
- [ ] Custom record type in NetSuite for recommendations (ops/NS setup)
- [ ] Nightly/periodic sync schedule and monitoring (infrastructure/config)
- [ ] NetSuite sandbox-to-production validation gate

### 4.3 BigCommerce / Peasisoft Sync
- [ ] BigCommerce Related Products API integration
- [ ] Peasisoft-compatible export format
- [ ] Category-level defaults + product-level overrides

---

## Technical Stack

| Layer | Technology |
|-------|-----------|
| CLI | Python + Click/Typer |
| Data | SQLite cache, CSV export |
| LLM | Azure OpenAI (GPT-4o) |
| APIs | FastAPI, NetSuite REST, BigCommerce V3 |
| TUI | Textual (Python) |
| Web | FastAPI + React |

---

## Phase 5: Rename & Service API (Future)

### 5.1 Project Rename
- [ ] Rename folder from `easyupsell/` → `pre/` (Product Recommendation Engine)
- [ ] Update all imports, CLI commands, docs
- [ ] New CLI: `pre analyze`, `pre review`, `pre export`

### 5.2 Service API for LibrePIM Integration
- [ ] REST API endpoint: `GET /recommendations/{product_id}`
- [ ] Nightly/weekly batch job populates recommendation cache
- [ ] LibrePIM queries PRE for upsell candidates
- [ ] Human-in-the-loop approval workflow in PIM UI

### 5.3 NetSuite Integration (Nightly Push)
- [ ] Create custom record type in NetSuite for recommendations
- [ ] Nightly job pushes approved recommendations to NS via SuiteQL/REST
- [ ] Push model preferred (secure, behind firewall, NS auth already solved)
- [ ] Display in NS for users who live there (senior architect request)

### 5.4 Critical Data Requirement: NetSuite ID ✅ (2026-02-05)
- [x] Extract NetSuite Internal ID from BigCommerce `bin_picking_number` field
- [x] BPN is comma-delimited; NS ID is always the **first value**
- [x] Include `netsuite_id` in all recommendation output
- [x] This is the **UID across all systems**: PIM, NS, CA, BC

### 5.5 Philosophy
PRE is a **decision-support tool**, not an autonomous agent. AI surfaces candidates + enriched data; humans make final calls based on business context.

---

## Phase 6: Historical Product-to-Product Recommendations (Future)

SKU-level "customers who bought X also bought Y" using real transaction data.

### 6.1 Data Foundation
- [ ] BQ query: co-purchase pairs from order history (orders containing ≥2 distinct SKUs)
- [ ] Frequency + recency weighting (recent co-purchases count more)
- [ ] Filter noise: exclude same-category duplicates, bundles, bulk reorders

### 6.2 Recommendation Engine
- [ ] For each SKU, rank top N co-purchased SKUs by weighted frequency
- [ ] Merge with margin/velocity enrichment data to prioritize high-value pairs
- [ ] LLM sanity check: batch-validate top pairs make merchandising sense (catch data artifacts)

### 6.3 Output
- [ ] Product-to-product recommendation report (SKU A → SKU B, co-purchase count, confidence)
- [ ] Complement existing category-level recommendations with SKU-level precision
- [ ] Feed into BigCommerce Related Products API for automated upsell widgets

### 6.4 How This Differs from Phases 1–3
Phases 1–3 are **concept-driven** (LLM brainstorms what *should* pair based on merchandising logic). Phase 6 is **data-driven** (what customers *actually* buy together). Best results come from combining both: concept-driven discovery surfaces novel pairings, historical data validates and ranks them.

---

## Current Status (2026-02-17)

**Phase 1 (CLI Foundation): ✅ Complete**
- 8,346 recommendations across 758 categories
- Output: `data/full_historical_recommendations.xlsx`

**Phase 2 (Dark Horse): ✅ Complete**
- 8,067 pairings with LLM review scoring
- Checkpoint/resume for interrupted runs
- Enriched output: SKU, margin, velocity, copurchase, high-priority flag
- Output: `data/dark_horse_discovery_glm_q8_reviewed.xlsx`

**Phase 3 (Opportunities): ✅ Pipeline Built**
- 1,647 unique product types from 4,314 catalog gaps
- CLI: `easyupsell opportunities` (with `--skip-llm` for instant output)
- Output: `data/new_product_opportunities.xlsx`

**Phase 4 (NetSuite Queryable API): ✅ Implemented**
- SQLite canonical recommendation DB: `data/recommendations.db`
- API service + CLI sync command live: `pre serve`, `pre sync netsuite`
- Remaining blockers are non-code: NetSuite custom record setup and deployment wrappers

**Next Steps:**
1. LLM-enrich the opportunities report (descriptions, prices, priority)
2. Deploy/monitor Phase 4 service and sync jobs
3. Phase 6: Historical product-to-product recommendations
