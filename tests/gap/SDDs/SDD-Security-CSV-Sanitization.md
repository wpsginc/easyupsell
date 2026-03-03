# SDD: Security - CSV Injection Sanitization

## 1. Gap Description
The migration script (`scripts/migrate_csv_to_db.py`) ingests CSV/XLSX data directly into the database without sanitization. If the source data contains malicious formulas (e.g., starting with `=`, `@`, `+`, `-`), these payloads are stored as-is. This creates a Stored CSV Injection vulnerability if the data is ever exported back to CSV/Excel for review.

## 2. Target Location
- **Script:** `scripts/migrate_csv_to_db.py`
- **Test:** `tests/security/test_csv_injection.py` (update to assert sanitization)

## 3. Test Strategy
1.  **Test Case:** Use `test_csv_injection_persistence` in `tests/security/test_csv_injection.py`.
2.  **Modification:** Update the test to assert that the stored value is **safe**.
    -   Input: `=cmd|' /C calc'!A0`
    -   Expected Stored: `'=cmd|' /C calc'!A0` (escaped with single quote) OR stripped.
    -   *Decision:* Prepend `'` (single quote) to any field starting with injection characters, effectively neutralizing the formula in Excel.
3.  **New Test:** Create `tests/gap/test_security_sanitization.py` to verify sanitization across all text fields (`source_category`, `target_sku`, `reasoning`, etc.).

## 4. Implementation Details
1.  **Helper Function:** Add `_sanitize_text(text: str) -> str` to `scripts/migrate_csv_to_db.py`.
    ```python
    def _sanitize_text(text: str) -> str:
        if text and text.startswith(('=', '+', '-', '@')):
            return "'" + text
        return text
    ```
2.  **Apply Sanitization:**
    -   In `_migrate_csv`, wrap all text field extractions with `_sanitize_text()`.
    -   In `_migrate_xlsx`, do the same (even though XLSX is binary, if we export to CSV later, the vulnerability re-emerges).

## 5. Recommended Executor
**Demon:** rem_security
**Reason:** Involves security best practices and updating security tests.
