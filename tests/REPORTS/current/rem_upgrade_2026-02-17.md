# Upgrade Demon Report - 2026-02-17

**Status:** 🟡 WARNING
**Version:** Phase 4 (SQLite Transition)

## Executive Summary
The migration infrastructure for moving from CSV/XLSX to SQLite is in place and functional for the primary data path. However, a significant workflow disconnect exists where the `export` command reads stale legacy data instead of the new canonical database, potentially leading to the export of unreviewed or rejected recommendations.

## 1. DB Migration (CSV/XLSX → SQLite)
**Status:** ✅ PASS (with caveats)

*   **Mechanism:** `scripts/migrate_csv_to_db.py` handles the import.
*   **Idempotency:** Verified. The script uses `INSERT ... ON CONFLICT DO UPDATE`, allowing re-runs without data duplication.
*   **Coverage:**
    *   ✅ CSV Import: Tested in `tests/test_migration.py`.
    *   ⚠️ XLSX Import: **NOT TESTED**. The migration script supports it, but no test case covers the Excel import path.
*   **Data Integrity:**
    *   Status mapping (`active` vs `pending_review`) is logic-based.
    *   Score clamping (`0.0-1.0`) prevents invalid data.
    *   Foreign keys enabled (`PRAGMA foreign_keys=ON`), though schema only has one table so far.

## 2. Config Migration
**Status:** ✅ PASS

*   **Strategy:** No major config schema changes.
*   **New Variables:** `PRE_DB_PATH` introduced (defaulting to `data/recommendations.db`), backward compatible.

## 3. Breaking Changes & Regressions
**Status:** 🔴 FAIL (High Severity)

### 🚨 Critical Workflow Disconnect
The system is currently in a "Dual Write" state (writing to both CSV and DB), but **Read** operations are inconsistent.

*   **The Issue:**
    1.  `analyze` writes to `recommendations.csv` AND `recommendations.db`.
    2.  `review` updates `recommendations.db` (and creates a new `.xlsx`), but **does NOT update** `recommendations.csv`.
    3.  `export` (e.g., to Peasisoft) **reads from `recommendations.csv`**.
*   **Consequence:** Any decisions made during `review` (approvals, rejections, score changes) are **ignored** by the `export` command. The export will contain the raw, unreviewed analysis output.
*   **Recommendation:** `easyupsell export` MUST be updated to read from `data/recommendations.db` (the new source of truth).

## 4. Backwards Compatibility
**Status:** ✅ PASS

*   **Dual Write:** The `analyze` command preserves the legacy `data/recommendations.csv` artifact while populating the DB.
*   **API:** The new API (`easyupsell serve`) is additive and does not replace existing CLI functionality yet.

## 5. Rollback Safety
**Status:** 🟡 PARTIAL

*   **Forward:** CSV/XLSX → DB (Supported via `migrate_csv_to_db.py`).
*   **Backward:** DB → CSV (Not explicitly supported).
    *   If the DB is corrupted, it can be rebuilt from the source CSV/XLSX files (assuming they are preserved).
    *   However, if work is done solely in the DB (via API or future tools), there is no mechanism to dump it back to the legacy CSV format.
*   **Recommendation:** Update `easyupsell export` to act as the "DB Dump" tool.

## Action Items

| Severity | Task | Owner |
|----------|------|-------|
| **P0** | **Fix Export Command:** Update `easyupsell export` to read from SQLite DB instead of CSV. | Engineering |
| **P1** | **Add XLSX Test:** Add a test case to `tests/test_migration.py` covering the Excel import path. | QA/Eng |
| **P2** | **Deprecate CSV Read:** Add warnings to any tool still reading from CSV (except the migration script). | Engineering |
| **P3** | **Schema Versioning:** Establish a `scripts/migrations/` folder for future schema changes (currently raw DDL in `src/db.py`). | Architecture |
