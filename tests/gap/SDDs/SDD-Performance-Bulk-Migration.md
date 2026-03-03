# SDD: Performance - Bulk Migration & Transactions

## 1. Gap Description
The migration script performs a database commit for every single row inserted (`src.db.RecommendationDB.upsert_recommendation` commits internally). This results in extremely poor performance for large datasets (O(N) fsyncs).

## 2. Target Location
- **Class:** `src.db.RecommendationDB`
- **Script:** `scripts/migrate_csv_to_db.py`
- **Test:** `tests/gap/test_performance_migration.py`

## 3. Test Strategy
1.  **Benchmark:** Measure time to insert 1,000 rows with current implementation.
2.  **Optimization:** Implement batch transaction support.
3.  **Verify:** Measure time again (expect >10x speedup).
4.  **Correctness:** Verify all 1,000 rows are present.

## 4. Implementation Details
1.  **Modify `src/db.py`**:
    -   Add `upsert_batch(self, recs: list[dict]) -> None`.
    -   Use `executemany` with the `UPSERT_SQL`.
    -   Wrap in a single `with self._connect() as conn: ... conn.commit()`.
2.  **Modify `scripts/migrate_csv_to_db.py`**:
    -   Accumulate rows in a buffer (e.g., list of size 1000).
    -   Call `db.upsert_batch(buffer)` when full or at end.
    -   *Note:* Error handling becomes coarser (batch fails). Need strategy: if batch fails, fallback to row-by-row? Or just log "Batch X failed"?
    -   *Refined Strategy:* For this gap, simple `executemany` is enough. If error handling is critical, keep row-by-row but wrap in `BEGIN TRANSACTION`... `COMMIT` at outer level.
    -   *Selected Approach:* Add `db.begin_transaction()` and `db.commit_transaction()` context manager to `RecommendationDB`, or just expose a method to insert list.
    -   *Simplest:* `upsert_many(self, recommendations: list[dict])`.

## 5. Recommended Executor
**Demon:** rem_performance
