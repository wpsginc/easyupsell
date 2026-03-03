# SDD: Migration Robustness & Error Handling

## 1. Gap Description
The current `migrate_csv_to_db.py` script iterates through CSV rows and calls `db.upsert_recommendation`. If a row is missing required fields (e.g., `source_category`), `upsert_recommendation` raises a `ValueError`, causing the entire migration process to crash. This is brittle, especially for large datasets where one malformed row should not stop the pipeline.

## 2. Target Location
`tests/gap/test_migration_robustness.py`

## 3. Test Strategy
1.  **Partial Failure Test**: Create a CSV with 3 rows:
    *   Row 1: Valid.
    *   Row 2: Invalid (missing `source_category`).
    *   Row 3: Valid.
2.  **Execution**: Run `migrate_csv_to_db`.
3.  **Expectation**:
    *   The script should **not** raise an unhandled exception.
    *   The script should print/log an error for Row 2.
    *   Row 1 and Row 3 should be successfully inserted into the DB.
    *   The returned summary counts should reflect the skipped row (or at least not count it as success).

## 4. Implementation Details
*   Modify `scripts/migrate_csv_to_db.py` to wrap the `db.upsert_recommendation` call in a `try...except ValueError` block.
*   Log the error to stderr or print a warning.
*   Update the `counts` dictionary to track "skipped" or "errors".
*   The test should assert that `migrate_csv_to_db` completes and the valid rows exist in the DB.
