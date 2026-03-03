# SDD: Migration Status Logic & "Rejected" Support

## 1. Gap Description
The migration script `scripts/migrate_csv_to_db.py` includes a counter for `rejected` items, but the logic makes it impossible to reach this state.
Currently, `status` is derived solely from `llm_valid` (CSV) or `keep/score` (XLSX), defaulting to `pending_review` if false.
There is no mechanism to explicitly import a recommendation as `rejected`, even though the database supports it.

## 2. Target Location
- **Test File:** `tests/gap/test_migration_status.py`
- **Script to Modify:** `scripts/migrate_csv_to_db.py`

## 3. Test Strategy
1.  **Fixture:** Create a CSV file with a `status` column.
    -   Row 1: `status="rejected"`, `llm_valid=False`.
    -   Row 2: `status="active"`, `llm_valid=True`.
    -   Row 3: No status column (legacy behavior), `llm_valid=False` -> `pending_review`.
2.  **Execution:** Run `migrate_csv_to_db`.
3.  **Assertions:**
    -   Row 1 should be in DB with `status='rejected'`.
    -   Row 2 should be in DB with `status='active'`.
    -   Row 3 should be in DB with `status='pending_review'`.
    -   The `counts["rejected"]` should be 1.

## 4. Implementation Details
1.  **Modify `scripts/migrate_csv_to_db.py`**:
    -   Update `_migrate_csv` logic for `status`.
    -   Priority:
        1.  If `row.get("status")` is present and valid (in `{'active', 'pending_review', 'rejected'}`), use it.
        2.  Else, fall back to existing logic (`active` if `llm_valid` else `pending_review`).
    -   Ensure the `counts` dictionary is updated correctly based on the final status.
2.  **Create `tests/gap/test_migration_status.py`**:
    -   Implement the test strategy.
