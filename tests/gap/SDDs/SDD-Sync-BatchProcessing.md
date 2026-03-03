# SDD: NetSuite Sync Batch Processing

## 1. Gap Description
The `NetSuiteSyncJob` class initializes with a `batch_size` parameter, but the `run()` method calls `self.db.get_pending_sync(force_all=force)` without passing this limit. This causes the job to load **all** pending records into memory and attempt to process them all in a single run.

**Risks:**
- **Memory OOM**: If there are 100k pending records, they are all loaded into a list.
- **Execution Time**: The job cannot be time-boxed. If `max_rpm` is low, the job could run for hours, potentially overlapping with the next scheduled cron job.

## 2. Target Location
`tests/gap/test_sync_batching.py`

## 3. Test Strategy
1.  **Seed DB**: Insert `N` pending records (where `N > batch_size`).
2.  **Run Job**: Configure job with `batch_size=K` (where `K < N`).
3.  **Verify**:
    - Only `K` records are processed (synced or failed).
    - `N - K` records remain in `pending` state.
    - The `db.get_pending_sync` method was called with `limit=K`.

## 4. Implementation Details
- Use `unittest.mock` to mock `NetSuiteClient`.
- Use a temporary SQLite DB.
- Ensure the test fails with the current implementation (proving the gap).
