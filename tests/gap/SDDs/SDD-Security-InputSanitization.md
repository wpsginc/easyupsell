# SDD: Security Input Sanitization (CSV Injection)

## 1. Gap Description
As identified by `tests/security/test_csv_injection.py`, the system allows storing malicious formula payloads (starting with `=`, `@`, `+`, `-`) in the database. When these are exported back to CSV/Excel (a core feature of this "Easy Upsell" tool), they can execute arbitrary code on the user's machine.

## 2. Target Location
`tests/gap/test_security_sanitization.py` (and `src/db.py` implementation)

## 3. Test Strategy
1.  **Input**: A string starting with `=cmd|...`.
2.  **Action**: Call `db.upsert_recommendation` with this string in `source_category` or `target_sku`.
3.  **Expectation**:
    *   The stored value should be sanitized (e.g., prepended with `'` or tab, or stripped).
    *   Example: `=cmd` becomes `'=cmd`.
    *   The test asserts that the value in DB does *not* start with the dangerous characters directly.

## 4. Implementation Details
*   Modify `src/db.py` `upsert_recommendation` method.
*   Add a helper `_sanitize_text(value: str) -> str`.
*   If `value` starts with `=`, `@`, `+`, `-`, prepend a single quote `'`.
*   Apply this to all text fields before insertion.
