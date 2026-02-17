# Fix Plan: Print Instead of Logging

## Root Cause

In `src/enrichment.py` at lines 37 and 39, the code uses `print()` for warning messages instead of the standard logging module. This is inconsistent with the rest of the codebase and makes it harder to control log levels and output formatting.

## Fix Strategy

Replace print statements with proper logging calls using the logger already imported at the module level.

## Steps

1. In `src/enrichment.py` at line 37: Replace:
   ```python
   print(f"⚠️ Warning: Enrichment data not found at {self.data_path}. Running without enrichment.")
   ```
   with:
   ```python
   logger.warning(f"Enrichment data not found at {self.data_path}. Running without enrichment.")
   ```

2. In `src/enrichment.py` at line 39: Replace:
   ```python
   print(f"⚠️ Error: Enrichment data at {self.data_path} is invalid JSON.")
   ```
   with:
   ```python
   logger.error(f"Enrichment data at {self.data_path} is invalid JSON.")
   ```

## Verification

- Run the service without enrichment_data.json and verify warning appears in logs
- Run with malformed JSON and verify error appears in logs
- Check that log formatting matches rest of codebase

## Files Affected

- `src/enrichment.py`
