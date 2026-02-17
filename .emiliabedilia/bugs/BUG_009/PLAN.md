# Fix Plan: Print Instead of Logging in fetch script

## Root Cause

The script `scripts/fetch_bq_enrichment.py` uses `print()` statements for status messages instead of the logging module. While scripts often use print for user output, the codebase already has a logger imported in bigquery_client.py, and this creates inconsistency.

## Fix Strategy

Replace print statements with logging calls for consistency with the rest of the codebase. Keep user-facing success/error emoji output but route through logging.

## Steps

1. In `scripts/fetch_bq_enrichment.py` at line 14: Add logging import:
   ```python
   import logging
   ```

2. In `scripts/fetch_bq_enrichment.py` after line 22: Add logger setup:
   ```python
   logging.basicConfig(level=logging.INFO, format='%(message)s')
   logger = logging.getLogger(__name__)
   ```

3. In `scripts/fetch_bq_enrichment.py` at line 71, 73, 77, 80, 87, 89, 108: Replace all `print()` calls with `logger.info()` or `logger.error()` as appropriate

## Verification

- Run `python scripts/fetch_bq_enrichment.py --help`
- Run the script and verify output still appears correctly
- Check that log levels can be controlled via logging config

## Files Affected

- `scripts/fetch_bq_enrichment.py`
