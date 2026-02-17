# Fix Plan: Hardcoded SQL Table Names

## Root Cause

The BigQuery table names like `bc_native.bc_order_line_items` are hardcoded in SQL query strings throughout `src/bigquery_client.py`. This makes it impossible to use the code with different BigQuery datasets or environments without modifying source code.

## Fix Strategy

Extract table names to configuration variables that can be set via environment variables or settings, then use string formatting to inject them into queries.

## Steps

1. In `src/config.py`: Add configuration fields for BigQuery dataset and table names (check if config.py exists first; if not, settings are in a different location)

2. In `src/bigquery_client.py` at line 15-75: Replace hardcoded table references with f-string formatting using config values. For example:
   - `bc_native.bc_order_line_items` → `{self.dataset}.bc_order_line_items`
   - Add dataset as instance variable from settings

3. Create a `.env.template` entry documenting the new BQ_DATASET variable

## Verification

- Verify queries still work with default values
- Test with BQ_DATASET env variable set to different dataset name
- Check that all 3 queries (TOP_CATEGORIES, ITEM_SALES, CATEGORY_ITEM_ENRICHED) use the configurable dataset

## Files Affected

- `src/bigquery_client.py`
- `src/config.py` (or equivalent settings file)
- `.env.template`
