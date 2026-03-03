# SDD: Migration Script Robustness

## 1. Gap Description
The `scripts/migrate_csv_to_db.py` script currently lacks error handling for individual row failures.
If `src.db.RecommendationDB.upsert_recommendation` raises a `ValueError` (e.g., due to missing required fields like `target_name`), the entire migration process crashes.
This prevents partial success where valid rows are imported and invalid ones are reported.

## 2. Target Location
- **Test File:** `tests/gap/test_migration_robustness.py`
- **Script to Modify:** `scripts/migrate_csv_to_db.py`

## 3. Test Strategy
1.  **Fixture:** Create a CSV file with:
    -   Row 1: Valid data.
    -   Row 2: Invalid data (missing `target_name` or `target_sku`).
    -   Row 3: Valid data.
2.  **Execution:** Run `migrate_csv_to_db` against this CSV.
3.  **Assertions:**
    -   The script should **not** raise an exception.
    -   Row 1 and Row 3 should be present in the database.
    -   Row 2 should be absent.
    -   The function return value (counts) should reflect the failures (e.g., added "errors" key).
    -   (Optional) specific error message printed to stderr (captured in test).

## 4. Implementation Details
1.  **Modify `scripts/migrate_csv_to_db.py`**:
    -   Wrap the `db.upsert_recommendation(payload)` call in a `try...except ValueError as e` block.
    -   In the `except` block:
        -   Print a warning/error message to stderr indicating the row number and the error.
        -   Increment a new key in the `counts` dictionary: `counts["errors"]`.
        -   `continue` to the next row.
    -   Update the return type hint and the final summary print to include error counts.
2.  **Create `tests/gap/test_migration_robustness.py`**:
    -   Implement the test strategy described above.
    -   Use `capsys` or `caplog` to verify the error message.
