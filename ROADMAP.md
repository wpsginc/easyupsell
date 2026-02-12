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

## Phase 2: Dark Horse Item Analysis ← **NEXT**

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
- [ ] **Restartable long-running processes** — checkpoint scored results every N pairings to disk (JSON or partial Excel) so interrupted runs can resume from last checkpoint instead of restarting from scratch
- [ ] Resume flag: `easyupsell review --resume` picks up from last checkpoint file

### 2.3 Output
- [x] Separate "Dark Horse" sheet/report in Excel (pairings + gaps + failures)
- [ ] Include SKU, current sales velocity, margin, and LLM reasoning for why it should pair
- [ ] Flag items with high margin + zero copurchase as highest-priority opportunities

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

## Phase 4: Integration — NetSuite Queryable API

Build PRE into a service that NetSuite can query for structured recommendation data.

### 4.1 Service API
- [ ] REST API endpoint: `GET /recommendations/{product_id}` or `GET /recommendations/{category_id}`
- [ ] Returns structured JSON: recommended SKUs, confidence, relationship type, margin
- [ ] Nightly/weekly batch job populates recommendation cache from BQ + LLM

### 4.2 NetSuite Integration
- [ ] Custom record type in NetSuite for recommendations
- [ ] Nightly push of approved recommendations via SuiteQL/REST
- [ ] Display in NS for users who live there (senior architect request)
- [ ] Push model preferred — secure, behind firewall, NS auth already solved

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
| APIs | BigCommerce V3, NetSuite SuiteQL |
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

## Current Status (2026-02-11)

**Full Production Run Complete:**
- 8,346 recommendations across 758 categories
- 4,179 valid (50%), 4,167 invalid (50%) — all kept with red/green highlighting
- 100% data quality: item sales, NetSuite ID, margin, velocity all populated
- Output: `data/full_historical_recommendations.xlsx` (1.1 MB, single workbook)
- Cost: ~$13.50 on GPT-5.2 for full catalog run

**Next Steps:**
1. Phase 2: Dark Horse item analysis (hidden inventory)
2. Phase 3: Opportunity add-on suggestions (new product sourcing)
3. Phase 4: NetSuite queryable API integration
