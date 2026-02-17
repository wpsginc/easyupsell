# Phase 4 SDD v1.1 — PRE Service (SQLite Canonical Store, Read‑Only API, NetSuite Upsert Sync)

**Status:** Superseded by v1.2

**Date:** 2026-02-16

**Author:** David Carroll + Copilot (rewrite)

**Based on:** Phase 4 SDD draft (Otto/Claude rewrite of Antigravity draft)
**Note:** This is historical documentation only. Implemented status and operational gaps are tracked in `phase4_sdd.md`.

---

## 0. Change Log (v1.1 vs v1.0)

This version **fixes production-breaking omissions** found in the v1.0 draft:

- Adds **authoritative SQL DDL** with `UNIQUE(source_category, target_sku)` so “upsert” is real (v1.0 implied upsert but had no uniqueness guarantee).  
- Defines **timestamp maintenance** (`updated_at`) explicitly (trigger or explicit UPDATE).
- Resolves **margin unit mismatch** by standardizing **margin as fraction** everywhere (0.42) and converting to percent only when required by NetSuite payload.
- Fixes **NetSuite rate limiting** design: throttle must be **per request**, not “batch of 50 then sleep”.
- Moves API key handling to **env-only**; `config.toml` must not contain secrets.
- Adds **error taxonomy**, structured logs, dead-letter reports, and day-2 ops guardrails.
- Breaks implementation into **small, deterministic steps** with explicit acceptance tests suitable for junior engineers and 128k-context LLM execution.

> Note: Package rename `easyupsell` → `pre` remains deferred to Phase 5 to avoid import churn. (Explicitly stated in v1.0.)

---

## 1. Executive Summary

Phase 4 transforms EasyUpsell from a CLI-only tool into **PRE (Product Recommendation Engine)**: a persistent service that downstream systems (NetSuite, LibrePIM, BigCommerce) can query for structured recommendation data.

**Deliverables** (unchanged intent from v1.0):

1. **Recommendation Database** — promote current CSV/Excel output into a proper SQLite database with a formal schema as the **single source of truth**.
2. **REST API** — lightweight FastAPI **read-only** service for external consumption.
3. **NetSuite Sync** — batch job that pushes **approved** recommendations into a NetSuite custom record type via REST API **upsert**.

**Design philosophy:**
- The CLI remains the **write interface** (analyze, review, approve).
- The API is **read-only**.
- NetSuite sync is a one-way **push** from SQLite → NetSuite.
- No bidirectional sync and no event-driven pipeline in Phase 4.

---

## 2. Architecture

### 2.1 System Context (logical)

```mermaid
graph TD
  User[Merchandiser] --> CLI[PRE CLI (easyupsell cli)]
  CLI -->|writes| DB[(SQLite: data/recommendations.db)]

  subgraph "PRE Service"
    API[FastAPI - read-only]
    Sync[pre sync netsuite]
  end

  API -->|reads| DB
  Sync -->|reads| DB

  subgraph "External Systems"
    NS[NetSuite ERP]
    BC[BigCommerce]
    LPM[LibrePIM]
  end

  BC -->|GET /v1/recommendations/...| API
  LPM -->|GET /v1/recommendations/...| API
  Sync -->|Upsert via REST| NS
```

### 2.2 Current Component Inventory (from v1.0, unchanged scope)

- CLI entry point: `easyupsell/cli.py` — add `serve` and `sync` commands.
- Analysis engine: `easyupsell/core/analyzer.py` — wire output to SQLite instead of CSV.
- Review engine: `easyupsell/core/review.py` — wire status updates to SQLite.
- BigQuery client: `src/bigquery_client.py` — no changes.
- Enrichment service: `src/enrichment.py` — no changes.
- NetSuite client: `src/netsuite/client.py` — extend with upsert/create.
- BigCommerce client: `src/bigcommerce/client.py` — defer wiring in Phase 4 (see Open Questions).
- TTL cache: `src/cache.py` — no changes.
- NEW: `src/db.py` (Recommendation DB access)
- NEW: `src/api.py` (FastAPI)
- NEW: `src/sync/netsuite.py` (NetSuite sync job)

### 2.3 What Does NOT Change (Phase 4 guardrail)

- **No package rename** (`easyupsell` → `pre`) in Phase 4.
- Keep existing CLI entry point stable.

---

## 3. Data Design

### 3.1 SQLite Recommendation Database

**DB file:** `data/recommendations.db` (alongside existing `data/cache.db`).

**Canonical store:** SQLite replaces CSV/Excel as the authoritative source.

#### 3.1.1 Connection Contract (required PRAGMAs)

Every SQLite connection **MUST** apply these PRAGMAs:

- `PRAGMA journal_mode=WAL;`
- `PRAGMA synchronous=NORMAL;`
- `PRAGMA foreign_keys=ON;`
- `PRAGMA busy_timeout=5000;`

**API connections SHOULD be read-only** by opening SQLite via URI mode `mode=ro` (prevents accidental writes).

#### 3.1.2 Authoritative Schema (SQL DDL)

> This is the source of truth for implementation and tests.

```sql
CREATE TABLE IF NOT EXISTS recommendations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- lookup keys
  source_category TEXT NOT NULL,
  source_sku TEXT NULL,

  target_sku TEXT NOT NULL,
  target_netsuite_id TEXT NULL,

  -- display / hydration fields (no live enrichment at API-time)
  target_name TEXT NOT NULL,
  target_price REAL NULL,

  -- model outputs
  score REAL NOT NULL CHECK(score >= 0.0 AND score <= 1.0),
  reasoning TEXT NULL,
  relationship_type TEXT NULL,

  -- human workflow
  status TEXT NOT NULL DEFAULT 'pending_review'
    CHECK(status IN ('pending_review','active','rejected')),

  -- enrichment snapshots (stored at write-time)
  copurchase_count INTEGER NOT NULL DEFAULT 0,

  -- IMPORTANT: margin is stored as FRACTION (0.42 = 42%)
  margin REAL NOT NULL DEFAULT 0.0,

  -- velocity semantics: numeric value (units depend on pipeline; treat as opaque)
  velocity REAL NOT NULL DEFAULT 0.0,

  -- NetSuite sync bookkeeping
  ns_sync_status TEXT NOT NULL DEFAULT 'pending'
    CHECK(ns_sync_status IN ('pending','synced','failed')),
  ns_sync_at TEXT NULL,

  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),

  -- REQUIRED for correct upsert behavior
  UNIQUE(source_category, target_sku)
);

CREATE INDEX IF NOT EXISTS idx_target_sku ON recommendations(target_sku);
CREATE INDEX IF NOT EXISTS idx_target_netsuite_id ON recommendations(target_netsuite_id);
CREATE INDEX IF NOT EXISTS idx_source_category ON recommendations(source_category);
CREATE INDEX IF NOT EXISTS idx_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_ns_sync ON recommendations(status, ns_sync_status);
```

#### 3.1.3 `updated_at` Maintenance (choose one)

SQLite does not auto-update `updated_at`. Implement one of the following and test it.

**Option A (preferred): Trigger**

```sql
CREATE TRIGGER IF NOT EXISTS trg_recommendations_updated_at
AFTER UPDATE ON recommendations
FOR EACH ROW
BEGIN
  UPDATE recommendations
  SET updated_at = CURRENT_TIMESTAMP
  WHERE id = OLD.id;
END;
```

**Option B:** Ensure every UPDATE statement sets `updated_at=CURRENT_TIMESTAMP`.

**Guardrail:** pick exactly one option and enforce via unit tests.

#### 3.1.4 Upsert Contract

All writes must use the unique constraint:

- Upsert key: `(source_category, target_sku)`
- Implementation requirement: `INSERT ... ON CONFLICT(source_category, target_sku) DO UPDATE ...`

#### 3.1.5 Query Contract

- API returns only `status='active'` records.
- Sync returns only `status='active'` and `ns_sync_status in ('pending','failed')` unless forced.

---

### 3.2 NetSuite Custom Record

**Record Type ID:** `customrecord_wpsg_pre_rec`

**External ID Field:** `custrecord_pre_external_id` (TEXT, unique)

**External ID value:** `{source_category}::{target_sku}`

#### 3.2.1 Field Mapping (required)

| NetSuite Field ID | Meaning | Source |
|---|---|---|
| `custrecord_pre_external_id` | unique id | `{source_category}::{target_sku}` |
| `custrecord_pre_source_cat` | category | `source_category` |
| `custrecord_pre_target_item` | item ref | `{"id": target_netsuite_id}` |
| `custrecord_pre_score` | confidence | `score` |
| `custrecord_pre_reason` | explanation | `reasoning` |
| `custrecord_pre_type` | relationship type | `relationship_type` |
| `custrecord_pre_active` | active flag | `status == 'active'` |
| `custrecord_pre_margin` | margin percent | `margin * 100` |
| `custrecord_pre_velocity` | velocity | `velocity` |
| `custrecord_pre_synced_at` | timestamp | sync timestamp |

#### 3.2.2 NetSuite Pre‑Reqs (manual, one-time)

1. Create custom record type `customrecord_wpsg_pre_rec`
2. Add fields above
3. Enable “Allow External ID” on record type
4. Grant integration role Create/Edit permissions

---

## 4. API Specification

**Stack:** FastAPI + Uvicorn

**Module:** `src/api.py`

**Entry:** `easyupsell serve` → `uvicorn src.api:app`

### 4.1 Authentication

- API key auth via `X-API-Key` header.
- **Secrets must be env-only**. Do not store secret keys in `config.toml`.

Environment variables:
- `PRE_API_KEYS` = comma-delimited valid keys (supports rotation)
- `PRE_DB_PATH` = optional override

Config (`config.toml`) **may** include:

```toml
[api]
host = "0.0.0.0"
port = 8090
api_key_required = true
```

### 4.2 Endpoints

#### `GET /v1/health`

No auth required. Returns:

```json
{
  "status": "ok",
  "db_path": "data/recommendations.db",
  "counts": {
    "total": 0,
    "active": 0,
    "pending_review": 0,
    "rejected": 0
  }
}
```

#### `GET /v1/recommendations/category/{category_name}`

Returns active recommendations for the category.

Query parameters:
- `min_score` float (default 0.7)
- `limit` int (default 20, max 100)
- `include_enrichment` bool (default true)

#### `GET /v1/recommendations/sku/{sku}`

Returns active recommendations where `target_sku` matches.

#### `GET /v1/recommendations/netsuite/{netsuite_id}`

Returns active recommendations where `target_netsuite_id` matches.

### 4.3 Response Contracts

**Success** responses must include:
- `request_id` (UUID)
- `count`
- `recommendations[]`

**Error** responses must be consistent:

```json
{
  "error": {
    "code": "not_found",
    "message": "No active recommendations for category",
    "details": {}
  },
  "request_id": "..."
}
```

### 4.4 Read‑Only Guardrail

- API DB connections MUST be read-only.
- Any attempt to write from API is a bug (add a test that asserts write fails).

---

## 5. NetSuite Sync Specification

### 5.1 NetSuite Client Extension

Extend `src/netsuite/client.py` with:

```python
def create_record(self, record_type: str, data: dict) -> dict:
    """POST /record/v1/{record_type}"""

def update_record(self, record_type: str, record_id: str, data: dict) -> dict:
    """PATCH /record/v1/{record_type}/{record_id}"""

def upsert_record(self, record_type: str, external_id: str, data: dict) -> dict:
    """PUT /record/v1/{record_type}/eid:{external_id}"""
```

### 5.2 Sync CLI

`easyupsell sync netsuite [--dry-run] [--max-rpm 40] [--batch-size 50] [--force]`

- `--dry-run`: build payloads, validate mapping, do not call NetSuite.
- `--max-rpm`: hard cap for requests/minute (default 40).
- `--batch-size`: how many records to pull from DB per loop iteration (does **not** control request pacing).
- `--force`: include already-synced records.

### 5.3 Correct Rate Limiting (required)

**Do not** rely on “send 50 quickly then sleep 2s”. That still bursts 50 requests.

**Requirement:** throttle **per request**:
- min interval seconds = `60 / max_rpm`

Example: `max_rpm=40` → interval = 1.5 seconds between requests.

### 5.4 Error Taxonomy + Retry Policy

- Retryable: 429, 5xx, network timeout
- Terminal: 400/422 validation errors, missing required fields

Retry schedule per record:
- attempt 1: immediately
- attempt 2: after 2s
- attempt 3: after 4s
- attempt 4: after 8s

Max attempts: 4 total (1 + 3 retries). Mark failed afterwards.

### 5.5 Orphan Handling

If `target_netsuite_id` is NULL:
- skip
- write JSONL to `logs/ns_sync_orphans.jsonl`:

```json
{"id":123,"source_category":"...","target_sku":"...","reason":"missing target_netsuite_id"}
```

### 5.6 Dead‑Letter Report

For any terminal failure, append JSONL to `logs/ns_sync_deadletter.jsonl`:

```json
{"id":123,"external_id":"A::B","http_status":422,"error":"...","payload_hash":"..."}
```

### 5.7 Payload Example

```json
PUT /services/rest/record/v1/customrecord_wpsg_pre_rec/eid:Tactical%20Boots::DANNER-15928
{
  "custrecord_pre_external_id": "Tactical Boots::DANNER-15928",
  "custrecord_pre_source_cat": "Tactical Boots",
  "custrecord_pre_target_item": {"id": "42891"},
  "custrecord_pre_score": 0.92,
  "custrecord_pre_reason": "Premium boot upgrade for duty use, same form factor.",
  "custrecord_pre_type": {"value": "up_sell"},
  "custrecord_pre_active": true,
  "custrecord_pre_margin": 42.0,
  "custrecord_pre_velocity": 128,
  "custrecord_pre_synced_at": "2026-02-16T22:00:00Z"
}
```

**Important:** `custrecord_pre_margin` is percent, derived from DB fraction: `margin * 100`.

---

## 6. Observability & Operations

### 6.1 Logging (hard requirement)

All components log **structured JSON** to stdout:

Fields:
- `timestamp` (UTC)
- `level`
- `component` (cli|api|sync|db)
- `request_id` (API)
- `job_id` (sync)
- `event`
- `details` (object)

### 6.2 Health Semantics

`/v1/health` returns:
- `status = ok` if DB is reachable and queries succeed
- `status = degraded` if DB reachable but integrity check fails or queries error

### 6.3 Backups (SQLite is canonical)

- Nightly copy of `data/recommendations.db` → `data/backups/recommendations-YYYYMMDD.db`
- Weekly `PRAGMA integrity_check;` and log result

### 6.4 Deployment (systemd)

- `deploy/pre-sync.service` runs `easyupsell sync netsuite --max-rpm 40`
- `deploy/pre-sync.timer` runs nightly 02:00 UTC
- `OnFailure=` optional hook

---

## 7. Testing Strategy (Enterprise Grade)

### 7.1 DB Tests

- schema creates successfully
- unique constraint prevents duplicates
- upsert updates same row (no second row)
- score bounds enforced
- updated_at changes on update

### 7.2 API Tests

- `/v1/health` no auth required
- auth rejects missing/invalid key
- category/sku/netsuite endpoints return only active recs
- error responses match standard schema

### 7.3 Sync Tests

- dry-run makes zero HTTP calls
- retry only for retryable codes
- per-request throttle respected (simulate time)
- updates DB sync fields on success
- writes orphan + deadletter JSONL with correct shape

---

## 8. Implementation Plan (Small Steps; Junior + LLM Friendly)

> Each step is designed to be completed and verified independently.

### 8.1 Task A — DB Module (src/db.py)

1. Create `RecommendationDB` class with:
   - `__init__(db_path: str)`
   - `_connect(read_only: bool) -> sqlite3.Connection`
   - `_apply_pragmas(conn)` (WAL, busy_timeout, etc.)
   - `init_db()` executes DDL + trigger (if using Option A)

2. Implement `upsert_recommendation(rec: dict)`
   - validate required fields: `source_category`, `target_sku`, `target_name`, `score`, `status`
   - normalize `margin` to fraction (float)
   - SQL upsert on unique constraint

3. Implement query methods:
   - `get_active_by_category(category: str, min_score: float, limit: int)`
   - `get_active_by_sku(sku: str)`
   - `get_active_by_netsuite_id(ns_id: str)`
   - `get_pending_sync(force_all: bool)`
   - `update_sync_status(row_id: int, status: str, synced_at: str | None, error: str | None)`
   - `get_stats()`

**Acceptance:** All DB unit tests pass.

### 8.2 Task B — Migration Script (scripts/migrate_csv_to_db.py)

4. Script takes file paths as args:
   - CSV path
   - XLSX path (optional)
   - output db path

5. Map known columns to DB schema.

6. Print summary counts.

**Acceptance:** Fixture migration produces correct counts.

### 8.3 Task C — Wire Analyzer + Review (writers)

7. Modify analyzer save logic to call `upsert_recommendation()` per row.

8. Modify review approvals/rejections to update `status` and `updated_at`.

**Acceptance:** Run `pre analyze` then approve/reject; DB reflects changes.

### 8.4 Task D — API (src/api.py)

9. FastAPI app with:
   - middleware that generates `request_id`
   - API key dependency (env-only)
   - endpoints per §4

10. API DB access is read-only.

**Acceptance:** API tests pass; read-only enforced.

### 8.5 Task E — NetSuite Sync (src/sync/netsuite.py)

11. Implement `NetSuiteSyncJob.run(dry_run, max_rpm, batch_size, force)`

12. Implement per-request throttle.

13. Implement retry taxonomy.

14. Update DB sync fields.

15. Emit orphan and deadletter JSONL.

**Acceptance:** Mocked sync tests pass.

### 8.6 Task F — Automation (deploy/)

16. Add systemd unit + timer + README.

**Acceptance:** `systemctl enable --now pre-sync.timer` works in staging.

---

## 9. Open Questions (Phase 4)

1. NetSuite custom record permissions — confirm integration role has Create/Edit.
2. BigCommerce push timing — defer `sync bigcommerce` to Phase 5 unless scope changes.
3. Enrichment refresh cadence — document cadence; optional CLI command later.
4. Category field type in NetSuite — free-form vs controlled list; recommend free-form for v1.

---

## 10. Appendix — Guardrails (Copy/Paste into PR template)

### Database
- [ ] `UNIQUE(source_category, target_sku)` exists
- [ ] `updated_at` maintained by trigger OR explicit UPDATEs
- [ ] PRAGMAs applied on every connection

### API
- [ ] Env-only API keys (no secrets in `config.toml`)
- [ ] Read-only DB connections
- [ ] Standard error schema everywhere

### NetSuite Sync
- [ ] Per-request throttle (max RPM)
- [ ] Retry only for 429/5xx/timeouts
- [ ] Dead-letter + orphan JSONL outputs
- [ ] Sync status updated in DB
