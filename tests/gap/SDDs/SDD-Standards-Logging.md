# SDD: Standards - Logging Standardization

## 1. Gap Description
Several core modules and scripts (`src/enrichment.py`, `scripts/fetch_bq_enrichment.py`) use `print()` statements for status and error reporting. This violates the "Enterprise Hardening" goal. They should use the Python `logging` module to allow for log levels, file rotation, and cleaner CLI output (handled by the main CLI entry point).

## 2. Target Location
- `src/enrichment.py`
- `scripts/fetch_bq_enrichment.py`

## 3. Test Strategy
- **Static Analysis**: Verify no `print()` calls exist in `src/`.
- **Unit Test**: Use `caplog` fixture in pytest to verify that errors and warnings are logged correctly.

## 4. Implementation Details
1.  **Configure Logger**: Add `logger = logging.getLogger(__name__)` to affected files.
2.  **Replace Prints**:
    -   `print("Error: ...")` -> `logger.error("...")`
    -   `print("Warning: ...")` -> `logger.warning("...")`
    -   `print("Info...")` -> `logger.info("...")`
3.  **CLI Config**: Ensure `easyupsell/cli.py` configures the root logger (e.g., to stderr or a file) so these logs are visible when running in verbose mode.
