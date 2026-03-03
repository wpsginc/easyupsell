# Dependency Demon Report - 2026-02-17

**Date:** 2026-02-17
**Type:** Manual Audit (Script `rem_dependency_demon.sh` missing)
**Scope:** `pip-audit`, `pip list --outdated`, `requirements.txt` drift check.

## Summary

| Category | Count | Status |
|----------|-------|--------|
| **Critical CVEs (P0)** | ~5 | 🚨 ACTION REQUIRED |
| **High CVEs (P1)** | ~15 | ⚠️ URGENT |
| **Total Vulnerabilities** | 47 | |
| **Outdated Packages** | 50+ | |
| **Missing Packages** | 5 | ❌ DRIFT DETECTED |

---

## 1. Drift Detection (requirements.txt vs Installed)

The following packages are listed in `requirements.txt` but are **NOT INSTALLED** in the current environment. This indicates a broken or incomplete environment setup.

*   `pandas` (Required: `>=2.0.0`)
*   `python-json-logger` (Required: `>=2.0.7`)
*   `google-cloud-bigquery` (Required: `>=3.0.0`)
*   `db-dtypes` (Required: `>=1.0.0`)
*   `openpyxl` (Required: `>=3.1.0`)

**Recommendation:** Run `pip install -r requirements.txt` immediately.

---

## 2. Security Vulnerabilities (CVEs)

Found **47 known vulnerabilities** in 23 packages.

### Critical / High Priority (P0/P1)

| Package | Version | CVE | Severity (Est.) | Description | Fix Version |
|---------|---------|-----|----------------|-------------|-------------|
| **langchain-core** | 1.1.0 | **CVE-2025-68664** | **P0 (Critical)** | **Serialization Injection:** Remote code execution risk via `dumps`/`load`. | 1.2.5, 0.3.81 |
| **mitmproxy** | 8.1.1 | **CVE-2025-23217** | **P0 (Critical)** | **RCE via SSRF:** Malicious client can access internal API to execute code. | 11.1.2 |
| **cryptography** | 46.0.3 | **CVE-2026-26007** | **P0 (Critical)** | **Key Leak:** Weak public key validation allows private key recovery. | 46.0.5 |
| **aiohttp** | 3.13.2 | CVE-2025-69223 | P1 (High) | DoS via zip bomb. | 3.13.3 |
| **aiohttp** | 3.13.2 | CVE-2025-69224 | P1 (High) | Request Smuggling. | 3.13.3 |
| **tornado** | 6.4 | GHSA-753j-mpmx-qq6g | P1 (High) | Request Smuggling via chunked headers. | 6.4.1 |
| **paramiko** | 2.12.0 | CVE-2023-48795 | P1 (High) | **Terrapin Attack:** SSH protocol integrity break. | 3.4.0 |
| **pillow** | 12.0.0 | CVE-2026-25990 | P1 (High) | Out-of-bounds write in PSD loading. | 12.1.1 |
| **pip** | 24.0 | CVE-2025-8869 | P1 (High) | Path traversal during tar extraction. | 25.3 |
| **protobuf** | 6.33.1 | CVE-2026-0994 | P1 (High) | DoS via deep recursion in `ParseDict`. | 5.29.6 |

### Other Vulnerabilities (P2/P3)

*   **ansible** (9.2.0): Info exposure in logs (CVE-2025-14010).
*   **ansible-core** (2.16.3): Arbitrary file write via `user` module (CVE-2024-9902).
*   **brotli** (1.1.0): DoS via decompression bomb.
*   **filelock** (3.20.1): TOCTOU race condition.
*   **h2** (4.1.0): HTTP/2 Request Splitting.
*   **pynacl** (1.5.0): Validation bypass.
*   **python-multipart** (0.0.21): Path traversal (requires non-default config).
*   **twisted** (24.3.0): HTML injection (XSS).
*   **werkzeug** (3.0.1): Multiple DoS/Info disclosure issues.
*   **urllib3** (2.3.0): Multiple issues.

---

## 3. Outdated Packages

Significant outdated packages found. Upgrading is recommended to fix vulnerabilities and ensure compatibility.

| Package | Current | Latest |
|---------|---------|--------|
| **fastapi** | 0.121.3 | 0.129.0 |
| **uvicorn** | 0.38.0 | 0.41.0 |
| **pydantic** | 2.12.5 | 2.13.0 |
| **ansible** | 9.2.0 | 13.3.0 |
| **rich** | 14.2.0 | 14.3.2 |
| **ruff** | 0.14.6 | 0.15.1 |
| **typer** | 0.20.0 | 0.24.0 |
| **openai** | 2.15.0 | 2.21.0 |
| **langchain** | 1.0.8 | 1.2.10 |

## Recommendations

1.  **Immediate Fix:** Install missing dependencies.
    ```bash
    pip install -r requirements.txt
    ```
2.  **Security Update:** Upgrade critical packages.
    ```bash
    pip install --upgrade "langchain-core>=1.2.5" "mitmproxy>=11.1.2" "cryptography>=46.0.5" "aiohttp>=3.13.3" "tornado>=6.4.1" "pillow>=12.1.1"
    ```
3.  **General Update:** Review and upgrade other outdated packages.
