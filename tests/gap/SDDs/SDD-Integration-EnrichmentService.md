# SDD: Integration - Enrichment Service

## 1. Gap Description
The `EnrichmentService` (in `src/enrichment.py`) is fully implemented and tested, and `scripts/fetch_bq_enrichment.py` correctly generates the required `data/enrichment_data.json`. However, the main application logic in `easyupsell/core/analyzer.py` does **not** use this service. It currently relies on basic sales metrics directly from BigQuery, ignoring the sophisticated co-purchase and margin data available in the enrichment artifact.

## 2. Target Location
- `easyupsell/core/analyzer.py`

## 3. Test Strategy
- **Unit Test**: Mock `EnrichmentService` in `tests/test_analyzer.py` (if exists, or create it).
- **Integration Test**: Run a partial analysis where `data/enrichment_data.json` exists and verify that recommendation objects contain enrichment data (e.g., `copurchase_count`, `margin`).
- **Verify**: Ensure the "Enrichment" step is logged in the console output during analysis.

## 4. Implementation Details
1.  **Import**: Import `EnrichmentService` in `easyupsell/core/analyzer.py`.
2.  **Initialize**: In `run_analysis`, initialize `enrichment_service = EnrichmentService()`.
    -   *Note*: Handle the case where the JSON file is missing (Service already does this, but Analyzer should verify).
3.  **Utilize**:
    -   Pass `enrichment_service` to `find_recommendations_for_category`.
    -   In `find_recommendations_for_category`, when constructing the recommendation dict:
        -   Call `enrichment_service.get_enrichment_for_pair(item["sku"], rec_sku)`.
        -   Add new fields to the output CSV/Dict:
            -   `enrichment_copurchase_count`
            -   `enrichment_margin`
            -   `enrichment_velocity`
4.  **Update CSV Headers**: Update `save_recommendations` to include these new fields.
