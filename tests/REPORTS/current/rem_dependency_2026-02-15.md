# Dependency Demon Report
**Date:** 2026-02-15  
**Repository:** /home/vmlinux/srcwpsg/pim/easyupsell  
**Branch:** master (dirty)  
**Demon Type:** Dependency CVE & Outdated Package Scanner

---

## Executive Summary

**Critical Findings:** 0 P0, 6 P1, 16 P2  
**Total CVEs Found:** 22 vulnerabilities across 18 packages  
**Outdated Packages:** 182 packages with newer versions available  
**Requirements Drift:** Detected - pyproject.toml missing several dependencies from requirements.txt

---

## P1 - High Severity CVEs (CVSS >= 7.0)

### BUG_DEP_001: aiohttp Multiple Critical Vulnerabilities
**Package:** aiohttp==3.13.2  
**Fixed In:** 3.13.3  
**Severity:** P1 (CVSS varies, multiple high-severity issues)

**CVEs:**
- **CVE-2025-69223** - Zip bomb DoS attack
- **CVE-2025-69224** - Request smuggling with non-ASCII characters (pure Python)
- **CVE-2025-69228** - Uncontrolled memory fill via Request.post()
- **CVE-2025-69229** - Chunked message DoS via blocking CPU usage
- **CVE-2025-69230** - Cookie header logging storm
- **CVE-2025-69226** - Path traversal information disclosure in web.static()
- **CVE-2025-69227** - Infinite loop DoS in optimized mode (-O flag)
- **CVE-2025-69225** - Non-ASCII Range header parsing issue

**Impact:** Multiple DoS vectors, request smuggling, information disclosure
**Recommendation:** Upgrade to aiohttp>=3.13.3

---

### BUG_DEP_002: cryptography Elliptic Curve Validation Bypass
**Package:** cryptography==46.0.3  
**Fixed In:** 46.0.5  
**CVE:** CVE-2026-26007  
**Severity:** P1

**Description:** Missing validation for elliptic curve point subgroup membership in `public_key_from_numbers()`, `load_der_public_key()`, and `load_pem_public_key()`. Allows attackers to provide small-order subgroup points, leaking private key information in ECDH and enabling signature forgery in ECDSA.

**Impact:** Private key leakage, signature forgery (SECT curves only)
**Recommendation:** Upgrade to cryptography>=46.0.5

---

### BUG_DEP_003: langchain-core Serialization Injection
**Package:** langchain-core==1.1.0  
**Fixed In:** 1.2.5  
**CVE:** CVE-2025-68664  
**Severity:** P1 (High)

**Description:** Serialization injection in `dumps()`/`dumpd()` functions allows attackers to inject malicious LangChain object structures via user-controlled data (e.g., LLM response metadata). Enables environment variable secret extraction and arbitrary class instantiation.

**Attack Surface:**
- `astream_events(version="v1")`
- `Runnable.astream_log()`
- `RunnableWithMessageHistory`
- LLM response fields like `additional_kwargs` and `response_metadata`

**Impact:** Secret extraction, arbitrary class instantiation with side effects
**Recommendation:** Upgrade to langchain-core>=1.2.5 and review serialization usage

---

### BUG_DEP_004: langchain-core SSRF in ChatOpenAI
**Package:** langchain-core==1.1.0  
**Fixed In:** 1.2.11  
**CVE:** CVE-2026-26013  
**Severity:** P1 (Low severity but still flagged)

**Description:** Server-Side Request Forgery in `ChatOpenAI.get_num_tokens_from_messages()` method. Fetches arbitrary `image_url` values without validation during token counting for vision models.

**Impact:** Blind SSRF to internal/external URLs, access to cloud metadata endpoints
**Recommendation:** Upgrade to langchain-core>=1.2.11

---

### BUG_DEP_005: mitmproxy SSRF to RCE
**Package:** mitmproxy==8.1.1  
**Fixed In:** 11.1.2  
**CVE:** CVE-2025-23217  
**Severity:** P1

**Description:** In mitmweb, malicious clients can use the proxy server (port 8080) to access the internal API (127.0.0.1:8081) via SSRF, potentially escalating to RCE. Requires local network access due to `block_global` default.

**Impact:** SSRF escalation to remote code execution (mitmweb only)
**Recommendation:** Upgrade to mitmproxy>=11.1.2 or avoid using mitmweb in untrusted networks

---

### BUG_DEP_006: paramiko Terrapin SSH Attack
**Package:** paramiko==2.12.0  
**Fixed In:** 3.4.0  
**CVE:** CVE-2023-48795  
**Severity:** P1

**Description:** Prefix truncation attack against SSH protocol (Terrapin attack). Affects ChaCha20-Poly1305 and Encrypt-then-MAC algorithms. Allows extension negotiation downgrade and security stripping.

**Impact:** SSH connection security downgrade, MitM attack enablement
**Recommendation:** Upgrade to paramiko>=3.4.0

---

## P2 - Medium Severity CVEs (CVSS >= 4.0)

### BUG_DEP_007: ansible Multiple Vulnerabilities
**Package:** ansible==9.2.0, ansible-core==2.16.3  
**Fixed In:** ansible>=12.2.0, ansible-core>=2.16.13  
**Severity:** P2

**CVEs:**
- **CVE-2025-14010** (ansible 9.2.0) - Keycloak plaintext password exposure in verbose logs
- **CVE-2024-9902** (ansible-core 2.16.3) - Unprivileged user file takeover via `user` module
- **CVE-2024-8775** (ansible-core 2.16.3) - Vault file plaintext exposure without no_log
- **CVE-2024-11079** (ansible-core 2.16.3) - hostvars template injection to arbitrary code execution

**Impact:** Credential exposure, privilege escalation, arbitrary code execution
**Recommendation:** Upgrade to ansible>=12.2.0 and ansible-core>=2.17.6

---

### BUG_DEP_008: brotli Decompression Bomb DoS
**Package:** brotli==1.1.0  
**Fixed In:** 1.2.0  
**CVE:** CVE-2025-6176  
**Severity:** P2

**Description:** Decompression bomb vulnerability allowing remote servers to crash clients with <80GB memory via extremely high compression ratios for zero-filled data.

**Impact:** Denial of Service via memory exhaustion
**Recommendation:** Upgrade to brotli>=1.2.0

---

### BUG_DEP_009: configobj ReDoS Vulnerability
**Package:** configobj==5.0.8  
**Fixed In:** 5.0.9  
**CVE:** CVE-2023-26112  
**Severity:** P2

**Description:** Regular Expression Denial of Service in `validate()` function via pattern `(.+?)\\((.*)\\)`. Only exploitable when developer puts malicious value in server-side config file.

**Impact:** DoS via ReDoS (limited attack surface)
**Recommendation:** Upgrade to configobj>=5.0.9

---

### BUG_DEP_010: filelock TOCTOU Symlink Vulnerability
**Package:** filelock==3.20.1  
**Fixed In:** 3.20.3  
**CVE:** CVE-2026-22701  
**Severity:** P2 (CVSS 5.6 Medium)

**Description:** Time-of-Check-Time-of-Use race condition in `SoftFileLock` allowing symlink attacks between permission validation and file creation.

**Impact:** Lock acquisition failure, DoS, unintended file operations
**Recommendation:** Upgrade to filelock>=3.20.3

---

### BUG_DEP_011: h2 HTTP/2 Request Smuggling
**Package:** h2==4.1.0  
**Fixed In:** 4.3.0  
**CVE:** CVE-2025-57804  
**Severity:** P2

**Description:** HTTP/2 request splitting via CRLF injection in headers. Exploitable when servers downgrade HTTP/2 to HTTP/1.1 without proper validation.

**Impact:** Request smuggling, security control bypass
**Recommendation:** Upgrade to h2>=4.3.0

---

### BUG_DEP_012: mitmproxy HTTP/2 Request Smuggling
**Package:** mitmproxy==8.1.1  
**Fixed In:** 12.1.2  
**Advisory:** GHSA-63cx-g855-hvv4  
**Severity:** P2

**Description:** Embeds vulnerable python-hyper/h2 ≤4.2.0 with HTTP/2 header validation gap. Affects reverse proxies to http:// backends (not regular mode).

**Impact:** Request smuggling when translating HTTP/2 to HTTP/1.1
**Recommendation:** Upgrade to mitmproxy>=12.1.2

---

### BUG_DEP_013: orjson Recursion DoS
**Package:** orjson==3.11.4  
**CVE:** CVE-2025-67221  
**Severity:** P2

**Description:** `orjson.dumps()` does not limit recursion for deeply nested JSON documents, leading to stack exhaustion.

**Impact:** Denial of Service via stack overflow
**Recommendation:** Monitor for patched version or implement input validation

---

### BUG_DEP_014: pillow Out-of-Bounds Write
**Package:** pillow==12.0.0  
**Fixed In:** 12.1.1  
**CVE:** CVE-2026-25990  
**Severity:** P2

**Description:** Out-of-bounds write when loading specially crafted PSD images (affects Pillow >=10.3.0).

**Impact:** Memory corruption, potential RCE
**Recommendation:** Upgrade to pillow>=12.1.1

---

### BUG_DEP_015: pip Tar Archive Path Traversal (Multiple)
**Package:** pip==24.0  
**Fixed In:** 25.3 (CVE-2025-8869), 26.0 (CVE-2026-1703)  
**Severity:** P2

**CVEs:**
- **CVE-2025-8869** - Symbolic link path traversal in fallback tar extraction (Python without PEP 706)
- **CVE-2026-1703** - Malicious wheel archive path traversal (limited to installation directory prefixes)

**Impact:** File extraction outside intended directory, code execution risk
**Recommendation:** Upgrade to pip>=26.0 or use Python >=3.9.17/3.10.12/3.11.4/3.12

---

### BUG_DEP_016: protobuf Recursion Limit Bypass
**Package:** protobuf==6.33.1  
**Fixed In:** 6.33.5  
**CVE:** CVE-2026-0994  
**Severity:** P2

**Description:** Recursion depth limit bypass in `json_format.ParseDict()` via nested `google.protobuf.Any` messages, causing stack exhaustion.

**Impact:** Denial of Service via RecursionError
**Recommendation:** Upgrade to protobuf>=6.33.5

---

### BUG_DEP_017: pyasn1 Memory Exhaustion DoS
**Package:** pyasn1==0.6.1  
**Fixed In:** 0.6.2  
**CVE:** CVE-2026-23490  
**Severity:** P2

**Description:** Malformed RELATIVE-OID with excessive continuation octets causes memory exhaustion via unbounded bit shifting in decoder.

**Impact:** DoS affecting LDAP servers, TLS/SSL endpoints, OCSP responders
**Recommendation:** Upgrade to pyasn1>=0.6.2

---

### BUG_DEP_018: pynacl Curve Point Validation
**Package:** pynacl==1.5.0  
**Fixed In:** 1.6.2  
**CVE:** CVE-2025-69277  
**Severity:** P2

**Description:** libsodium vulnerability - `crypto_core_ed25519_is_valid_point()` allows points outside the main cryptographic group.

**Impact:** Cryptographic weakness in atypical use cases
**Recommendation:** Upgrade to pynacl>=1.6.2

---

### BUG_DEP_019: python-multipart Path Traversal
**Package:** python-multipart==0.0.21  
**Fixed In:** 0.0.22  
**CVE:** CVE-2026-24486  
**Severity:** P2

**Description:** Path traversal when using non-default config `UPLOAD_DIR` + `UPLOAD_KEEP_FILENAME=True`. Filenames starting with `/` bypass directory restrictions via `os.path.join()` behavior.

**Impact:** Arbitrary file write (non-default configuration only)
**Recommendation:** Upgrade to python-multipart>=0.0.22

---

### BUG_DEP_020: tornado Duplicate Transfer-Encoding Headers
**Package:** tornado==6.4  
**Fixed In:** 6.4.1  
**Advisory:** GHSA-753j-mpmx-qq6g  
**Severity:** P2

**Description:** Tornado ignores duplicate `Transfer-Encoding: chunked` headers, enabling request smuggling when behind proxies (e.g., Pound) that emit such requests.

**Impact:** Request smuggling, ACL bypass, cache poisoning, connection desynchronization
**Recommendation:** Upgrade to tornado>=6.4.1

---

## P3 - Outdated Packages (Selection of Critical Updates)

### Major Version Updates Available
- **ansible:** 9.2.0 → 13.3.0 (major security updates)
- **ansible-core:** 2.16.3 → 2.20.2
- **duplicity:** 2.1.4 → 3.0.7
- **fastapi:** 0.121.3 → 0.129.0
- **httplib2:** 0.20.4 → 0.31.2
- **huggingface-hub:** 0.36.0 → 1.4.1
- **langchain:** 1.0.8 → 1.2.10
- **lxml:** 5.2.1 → 6.0.2
- **mitmproxy:** 8.1.1 → 12.2.1 ⚠️ (also has CVEs)
- **openai:** 2.15.0 → 2.21.0
- **pip:** 24.0 → 26.0.1 ⚠️ (also has CVEs)
- **setuptools:** 80.9.0 → 82.0.0
- **transformers:** 4.57.1 → 5.1.0
- **typer:** 0.20.0 → 0.23.1
- **urllib3:** 2.3.0 → 2.6.3
- **Werkzeug:** 3.0.1 → 3.1.5

**Total outdated packages:** 182

---

## BUG_DEP_021: Requirements Drift (pyproject.toml vs requirements.txt)
**Severity:** P2

### Missing from pyproject.toml
The following dependencies are in `requirements.txt` but NOT in `pyproject.toml`:
- requests>=2.28.0
- oauthlib>=3.2.0
- pandas>=2.0.0
- google-cloud-bigquery>=3.0.0
- db-dtypes>=1.0.0
- openpyxl>=3.1.0
- pytest>=7.0.0 (listed in dev, but also in main requirements.txt)
- ruff>=0.1.0
- rapidfuzz>=3.0.0

### Version Mismatches
- **httpx:** requirements.txt missing, but pyproject.toml has >=0.25.0 (installed: 0.28.1)
- **openai:** requirements.txt missing, but pyproject.toml has >=1.0.0 (installed: 2.15.0)
- **typer:** requirements.txt has >=0.9.0, pyproject.toml has [all]>=0.9.0

**Impact:** Build/deployment inconsistencies, potential dependency resolution conflicts  
**Recommendation:** Consolidate to single source of truth (pyproject.toml preferred for modern Python projects)

---

## Summary Statistics

| Severity | Count | Type |
|----------|-------|------|
| P0 (Critical) | 0 | CVE |
| P1 (High) | 6 | CVE |
| P2 (Medium) | 16 | CVE + Drift |
| P3 (Low) | 182 | Outdated |
| **Total** | **204** | **All** |

---

## Recommendations Priority

### Immediate (P1)
1. ✅ Upgrade **cryptography** to 46.0.5 (private key leakage)
2. ✅ Upgrade **langchain-core** to 1.2.11 (serialization injection + SSRF)
3. ✅ Upgrade **paramiko** to 3.4.0 (SSH Terrapin attack)
4. ⚠️ Review **aiohttp** usage - upgrade to 3.13.3 if used
5. ⚠️ Review **mitmproxy** usage - upgrade to 12.1.2 if used (multiple CVEs)

### High Priority (P2)
1. Upgrade **pip** to 26.0 (path traversal)
2. Upgrade **pillow** to 12.1.1 (OOB write)
3. Upgrade **protobuf** to 6.33.5 (DoS)
4. Upgrade **pyasn1** to 0.6.2 (DoS)
5. Consolidate **requirements.txt** and **pyproject.toml**

### Maintenance (P3)
1. Establish dependency update policy
2. Consider using `pip-audit` in CI/CD pipeline
3. Enable Dependabot or similar automated dependency scanning
4. Regularly update packages (especially security-sensitive ones)

---

## Verification Commands

```bash
# Re-run audit after fixes
pip-audit --desc

# Check for outdated packages
pip list --outdated

# Verify specific package versions
pip show cryptography langchain-core paramiko aiohttp mitmproxy
```

---

**Report Generated:** 2026-02-15  
**Demon:** dependency (Automated CVE Scanner)  
**Exit Code:** 6 (P1 vulnerabilities found)
