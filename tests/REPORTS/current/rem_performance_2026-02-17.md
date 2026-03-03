# Performance Demon Report - 2026-02-17

**Status:** ✅ PASS (with warnings)
**Version:** Phase 4 (SQLite + API + NetSuite Sync)

## Executive Summary
Performance is generally healthy for the Phase 4 rollout. Startup and import times are within targets. Memory usage is low. SQLite read performance is excellent, but write performance is suboptimal due to lack of batch processing. One test case is causing significant delay in the test suite.

## 1. Metrics Overview

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| **Import Time** | `~1.00s` | < 1.5s | ✅ PASS |
| **CLI Startup** | `1.07s` | < 2.0s | ✅ PASS |
| **Memory (Sync)**| `63.3 MB` | < 500 MB | ✅ PASS |
| **SQLite Read** | `75,670 ops/sec` | > 10k | ✅ PASS |
| **SQLite Write** | `894 ops/sec` | > 1k | ⚠️ WARN |
| **SQLite Update**| `1,890 ops/sec` | > 2k | ⚠️ WARN |

## 2. Benchmark Detail

### SQLite Performance (`src.db.RecommendationDB`)
Tests performed on 10,000 records.

- **Read Rate:** High throughput (75k/s) confirms the API will handle read traffic efficiently.
- **Write Rate:** Low throughput (~900/s) indicates that `upsert_recommendation` commits on every call.
    - **Impact:** Initial migration of CSVs or large NetSuite syncs will be slower than necessary.
    - **Recommendation:** Implement `upsert_batch` using a single transaction.

### Memory Usage
Measured during `easyupsell sync netsuite --dry-run`.
- **Peak RSS:** 63.30 MB
- **Analysis:** Well within the 500MB limit. No immediate leaks detected in the sync logic.

## 3. Findings & Regressions

### [P1] Slow Test Case: `test_retryable_error_retries_then_success`
- **Location:** `tests/test_sync.py::test_retryable_error_retries_then_success`
- **Duration:** **14.27s**
- **Root Cause:** The test triggers the real backoff logic in `NetSuiteSyncJob._sync_record` (0+2+4+8s) without mocking `time.sleep`.
- **Impact:** Slows down the feedback loop for developers.
- **Fix:** Patch `src.sync.netsuite.time.sleep` in the test case (similar to `test_per_request_throttle`).

### [P2] Inefficient Database Writes
- **Location:** `src/db.py`
- **Issue:** Missing bulk insert/update capability.
- **Impact:** Data ingestion is O(N) in transactions.
- **Fix:** Add `upsert_batch(records: list[dict])` method to `RecommendationDB` that wraps inserts in a single `conn.commit()`.

### [P2] API Connection Churn
- **Location:** `src/api.py` endpoints
- **Issue:** A new SQLite connection is opened and closed for every single API request.
- **Impact:** Unnecessary syscall overhead per request.
- **Fix:** While SQLite connections are cheap, a dependency injection pattern yielding a reused read-only connection (or pool) would be more scalable.

## 4. Recommendations
1.  **Immediate:** Fix the slow test in `tests/test_sync.py` to save ~14s per run.
2.  **High Priority:** Add `upsert_batch` to `src/db.py` before running the full migration script `scripts/migrate_csv_to_db.py`.
3.  **Low Priority:** Optimize API connection management if throughput requirements increase.
