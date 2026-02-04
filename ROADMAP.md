# EasyUpsell Product Roadmap

**Status:** ⚠️ In Progress (BQ category query ✅ done, NS ID in output pending)

> ⚠️ **RENAME PENDING**: This project will be renamed to **PRE (Product Recommendation Engine)** - see Phase 5 below.

## Vision
A **decision-support tool** for product recommendations. Uses LLM validation + enriched business metrics (copurchase frequency, margins, velocity) to surface high-quality upsell candidates for **human review and approval**. The goal is to remove drudgery, not replace human judgment.

---

## Phase 1: CLI Foundation ✅ → 🚧

### 1.1 Core Analysis Engine (Done)
- [x] BigCommerce V3 API integration
- [x] Category hierarchy parsing  
- [x] Order history analysis (sales velocity)
- [x] LLM validation via Azure OpenAI
- [x] Priority brand boosting (Streamlight, Benchmade, etc.)
- [x] CSV output with full metrics
- [x] **Batched LLM calls** (Implemented 2026-02-03)
- [x] **Enterprise Hardening** (Config module, Pydantic, No hardcoded paths)

### 1.2 Production CLI (Current)
Build `easyupsell` CLI with progressive disclosure:

```bash
# Quick start - analyze top 50 categories
easyupsell analyze

# Full catalog analysis
easyupsell analyze --all

# Single category deep-dive
easyupsell analyze --category "Tactical Pants"

# Review/approve recommendations
easyupsell review data/recommendations.csv

# Export to Peasisoft format
easyupsell export --format peasisoft

# Manage priority brands
easyupsell brands --add "Safariland"
easyupsell brands --list
```

**CLI Subcommands:**
| Command | Description |
|---------|-------------|
| `analyze` | Generate recommendations |
| `review` | Interactive review/approve workflow |
| `export` | Export to various formats |
| `brands` | Manage priority brand list |
| `config` | Configure API keys, LLM provider |
| `status` | Show analysis progress/stats |

### 1.3 Fixes & Features Needed
- [ ] Allow same-category recommendations (helmet→helmet light)
- [ ] Resume capability for interrupted runs
- [ ] Progress bar for large batches
- [ ] Local caching of category/product data
- [ ] **Item-level analysis** (item→item, not just category→item)
  ```bash
  easyupsell analyze --item "STR-69140"  # Find upsells for a specific product
  easyupsell analyze --top-items 100     # Analyze top 100 products by sales
  ```
- [ ] **@Dave: Set up cheaper model** - DeepSeek V3 ($0.14/1M) or GPT-4o-mini
  - Current: gpt-5.2 (massive overkill for yes/no classification)
  - Add `--cheap` flag for bulk runs
- [ ] **Batched LLM calls** - 8-10 items per prompt (50-70% faster!)
  - Stay under 25k tokens (quant drops off after 32k)
  - Single category → batch all candidate items in one call
  - Return JSON array of results

---

## Phase 2: Data & Performance

### 2.1 Caching Layer
- SQLite cache for BC category/product data
- Skip re-fetching unchanged data
- Track last-modified timestamps

### 2.2 NetSuite Margin Integration
- [ ] Finish margin data enrichment
- [ ] Cost/margin columns in output
- [ ] Margin-based scoring boost

### 2.3 Batch Processing
- Process 1,252 categories efficiently
- Parallel LLM calls (rate-limited)
- Daily/weekly scheduled runs

---

## Phase 3: Review Workflow

### 3.1 TUI Review Mode
- Textual-based terminal UI
- Browse recommendations by category
- Approve/reject with keyboard
- Bulk operations

### 3.2 Feedback Loop
- Track approved vs rejected pairings
- Feed back into scoring algorithm
- Learn from human decisions

---

## Phase 4: Export & Integration

### 4.1 Peasisoft Native Upsell
- Generate Peasisoft-compatible format
- Direct API integration (if available)
- Sync approved recommendations

### 4.2 BigCommerce Native
- BigCommerce Related Products API
- Category-level defaults
- Product-level overrides

---

## Phase 5: Web Dashboard (Future)

### 5.1 FastAPI Backend
- REST API wrapping CLI logic
- WebSocket for progress updates
- Auth via BigCommerce OAuth

### 5.2 React Frontend
- Category recommendation browser
- Drag-drop reordering
- A/B test configuration
- Performance analytics

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

### 5.4 Critical Data Requirement: NetSuite ID
- [ ] Extract NetSuite Internal ID from BigCommerce `bin_picking_number` field
- [ ] BPN is comma-delimited; NS ID is always the **first value**
- [ ] Include `netsuite_id` in all recommendation output
- [ ] This is the **UID across all systems**: PIM, NS, CA, BC

### 5.5 Philosophy
PRE is a **decision-support tool**, not an autonomous agent. AI surfaces candidates + enriched data; humans make final calls based on business context.

---

## Current Status

**Prototype Complete:**
- 49 valid recommendations from 30 categories
- Streamlight, Channellock, etc. appearing correctly
- ~20% validation rate (LLM filtering noise)

**Next Steps:**
1. Build `easyupsell` CLI package structure
2. Fix same-category filter
3. Add resume/progress tracking
4. Run full 1,252 category analysis
