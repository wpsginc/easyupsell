# SDD: Integration - End-to-End Migration Flow

## 1. Gap Description
While unit tests cover individual components, there is no test verifying the full lifecycle of a recommendation:
1.  Generation (`analyze`) -> 2. Review (human/simulation) -> 3. Export (CSV) -> 4. Migration (`migrate_csv_to_db`) -> 5. Serving (API).
This gap risks integration failures where formats drift between steps (e.g., Export format changes, Migration script expects old format).

## 2. Target Location
- **Test:** `tests/integration/test_e2e_migration_flow.py`

## 3. Test Strategy
1.  **Setup:**
    -   Create a dummy `RecommendationDB` with 1 seed recommendation.
    -   Run `easyupsell analyze` (mocked LLM) to generate suggestions.
    -   Run `easyupsell export` to generate `full_recommendations_v2.csv`.
2.  **Migration:**
    -   Run `migrate_csv_to_db` on the exported CSV.
3.  **Verification:**
    -   Query the API (or DB directly) to verify the migrated data matches the original analysis.
    -   Assert that fields like `score`, `reasoning`, and `source_category` are preserved exactly.

## 4. Implementation Details
1.  **Mocking:** Use `unittest.mock` to bypass actual LLM calls in step 1.
2.  **File Logic:** Use `tmp_path` for all intermediate artifacts.
3.  **Assertions:** Check data integrity at each hop (Analysis -> CSV -> DB).

## 5. Recommended Executor
**Demon:** rem_uat
