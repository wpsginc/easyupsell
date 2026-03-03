# SDD: Migration Status Preservation

## 1. Gap Description
The current migration logic blindly updates the `status` of a recommendation based on the CSV input (`llm_valid` flag). This creates a data loss scenario:
1.  CSV is imported (Item A is "active").
2.  Human reviewer manually changes Item A to "rejected" in the application (DB).
3.  CSV is imported again (e.g., pipeline re-run).
4.  Item A is overwritten back to "active", losing the human rejection.

## 2. Target Location
`tests/gap/test_migration_preservation.py`

## 3. Test Strategy
1.  **Initial Import**: Import a CSV where Item A is "active".
2.  **Manual Modification**: Update Item A in DB to "rejected".
3.  **Re-Import**: Import the *same* CSV again (where Item A is still "active").
4.  **Assertion**:
    *   Item A should remain "rejected" in the DB.
    *   Other fields (e.g., score, price) *should* update if changed in CSV.
    *   Only `status` should be preserved if it differs from the default/calculated import status?
    *   *Refinement*: To support "Correction" flows, maybe we only preserve if DB is "rejected"?
    *   *Simplified Strategy for this Gap*: Assert that `status` is **not** overwritten if the DB status is "rejected" or "active" and the CSV status is "pending"?
    *   *Actually*: The safest approach for an Upsert is "Status Preservation Rule":
        *   If DB status is 'rejected', do not overwrite with 'active'/'pending_review'.
        *   If DB status is 'active', and CSV says 'active', fine.
        *   If DB status is 'active', and CSV says 'pending_review' (e.g. logic change), maybe downgrade?

    **Selected Logic for Test**:
    "If the record exists, do NOT update `status`." (Or, only update if CSV explicitly forces it? For now, let's just ensure we don't blindly overwrite 'rejected' with 'active').

## 4. Implementation Details
*   This likely requires modifying `src/db.py` `UPSERT_SQL`.
*   Change the `status = excluded.status` line to a CASE statement:
    ```sql
    status = CASE
        WHEN recommendations.status = 'rejected' THEN 'rejected'
        ELSE excluded.status
    END,
    ```
*   The test should verify this specific behavior.
