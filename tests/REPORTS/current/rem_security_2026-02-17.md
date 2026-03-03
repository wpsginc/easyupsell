# Security Audit Report - Phase 4: Recommendation Engine

## 1. Executive Summary
- **Overall Risk:** **High**
- **Attack Surface:** CSV/XLSX Migration Script, REST API, Database Storage
- **Critical Vulnerabilities Found:** 3

The "EasyUpsell" Phase 4 implementation introduces significant security risks primarily through its data ingestion pipeline and subsequent data serving. The migration script blindly trusts input files, allowing for **CSV Injection** (formula injection) and **Arbitrary File Writes**. Furthermore, the API serves this potentially malicious data without sanitization, leading to **Stored XSS** if consumed by a web frontend.

## 2. Vulnerabilities Found

### VULN-001: Stored CSV Injection / Formula Injection
- **Severity:** **High**
- **CWE:** CWE-1236 (Improper Neutralization of Formula Elements in a CSV File)
- **Attack Vector:** An attacker provides a malicious CSV/XLSX file (e.g., from a compromised supplier or internal bad actor) containing formulas like `=cmd|' /C calc'!A0`.
- **Impact:** When an administrator or analyst later exports the database content to CSV/Excel (a standard business operation), the formula executes arbitrary commands on their machine.
- **Affected Code:** `scripts/migrate_csv_to_db.py` (Validation logic), `src/db.py` (Storage)
- **Proof of Concept:**
  ```python
  # See tests/security/test_csv_injection.py
  payload = "=cmd|' /C calc'!A0"
  # This payload is stored verbatim in the SQLite DB
  ```
- **Remediation:**
  Sanitize inputs starting with `=`, `+`, `-`, or `@` by prepending a single quote `'` before storage or during export.

### VULN-002: Arbitrary File Write via Migration Script
- **Severity:** **High**
- **CWE:** CWE-73 (External Control of File Name or Path)
- **Attack Vector:** The `migrate_csv_to_db.py` script accepts a `--db` argument without validating that it resides in a safe directory.
- **Impact:** If the script is run with elevated privileges (e.g., by a cron job or CI/CD pipeline), an attacker who can manipulate the arguments could overwrite critical system files (e.g., `/etc/cron.d/evil`) or application config files.
- **Affected Code:** `scripts/migrate_csv_to_db.py:118`
- **Proof of Concept:**
  ```bash
  python scripts/migrate_csv_to_db.py --csv data.csv --db /etc/cron.d/pwned.db
  ```
- **Remediation:**
  Restrict the `--db` output path to a specific allowlisted directory (e.g., `data/`) or reject absolute paths/traversal characters.

### VULN-003: Stored Cross-Site Scripting (XSS) via API
- **Severity:** **High**
- **CWE:** CWE-79 (Improper Neutralization of Input During Web Page Generation)
- **Attack Vector:** Malicious scripts (e.g., `<script>alert(1)</script>`) injected via the migration pipeline are stored in the DB. The API serves these strings as JSON without sanitization.
- **Impact:** Any frontend application consuming this API (e.g., the review UI) that renders `target_name` or `reasoning` without escaping will execute the malicious script in the user's browser.
- **Affected Code:** `src/api.py` (Response serialization)
- **Proof of Concept:**
  ```python
  # See tests/security/test_api_xss.py
  # API Response:
  {
    "target_name": "<script>alert(1)</script>",
    ...
  }
  ```
- **Remediation:**
  While output encoding is primarily the client's responsibility, the API should ideally sanitize HTML characters or explicitly document that the data is unsafe HTML.

## 3. Recommendations (Prioritized)

### P0 (Fix Before Production)
1.  **Sanitize CSV Inputs:** Modify `scripts/migrate_csv_to_db.py` to escape cell values starting with `=`, `+`, `-`, `@`.
2.  **Restrict DB Path:** Update `scripts/migrate_csv_to_db.py` to enforce that the output DB is created within the `data/` directory or a user-confirmed path.

### P1 (Fix Soon)
1.  **API Output Encoding:** Consider implementing a serialization layer in `src/api.py` that HTML-encodes text fields by default, or adds a flag to do so.
2.  **Input Validation:** Add stricter regex validation for `sku` and `category` names to reject characters like `<` `>` `=` `|`.

### P2 (Consider)
1.  **Secrets Management:** Ensure `PRE_API_KEYS` are managed via a secure vault in production, not just plain environment variables.

## 4. Rem's Security Verdict
**"The gates are wide open!"** The system is functionally competent but naively trusts all data. It assumes the "migration" phase is a trusted event, but in a supply chain attack scenario, that CSV is the weapon. **Lock it down.**
