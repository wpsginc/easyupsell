# Hygiene Audit Report - EasyUpsell

**Generated:** 2026-02-15 00:00:00  
**Repository:** /home/vmlinux/srcwpsg/pim/easyupsell  
**Demon:** Rem the Hygiene Demon  
**Branch:** master (dirty)

## Executive Summary
- **Overall Hygiene Score:** C
- **Total Issues:** 39
- **P0 (Fix Now):** 0
- **P1 (Fix Soon):** 9
- **P2 (Backlog):** 30

**Key Findings:**
- 27 dead imports detected across production and test code
- 9 hardcoded API URLs (mix of localhost and production)
- 6 magic sleep values (0.1 seconds) with no named constants
- 6 hardcoded timeout values in validation script
- No debug artifacts, no TODOs, no deprecated APIs
- No commented-out code blocks

## Findings by Category

### 1. Dead Imports (P2)

**Impact:** Clutters codebase, confuses readers, slows imports  
**Count:** 27 violations

| File | Line | Import | Severity |
|------|------|--------|----------|
| `easyupsell/commands/analyze.py` | 8 | `rich.progress.Progress` | P2 |
| `easyupsell/commands/analyze.py` | 8 | `rich.progress.SpinnerColumn` | P2 |
| `easyupsell/commands/analyze.py` | 8 | `rich.progress.TextColumn` | P2 |
| `easyupsell/commands/analyze.py` | 206 | `signal` | P2 |
| `easyupsell/commands/export.py` | 8 | `typing.Optional` | P2 |
| `easyupsell/core/analyzer.py` | 9 | `collections.defaultdict` | P2 |
| `easyupsell/core/analyzer.py` | 10 | `datetime.datetime` | P2 |
| `easyupsell/core/analyzer.py` | 10 | `datetime.timedelta` | P2 |
| `easyupsell/core/analyzer.py` | 45 | `validate_category_pairings.get_llm_validation` | P2 |
| `easyupsell/core/discovery.py` | 3 | `typing.Any` | P2 |
| `easyupsell/core/discovery.py` | 3 | `typing.Optional` | P2 |
| `easyupsell/core/review.py` | 12 | `json` | P2 |
| `easyupsell/core/review.py` | 14 | `typing.Optional` | P2 |
| `scripts/analyze_pairings.py` | 20 | `json` | P2 |
| `scripts/fetch_bq_enrichment.py` | 17 | `typing.Dict` | P2 |
| `scripts/fetch_bq_enrichment.py` | 17 | `typing.Any` | P2 |
| `scripts/recommend_for_item.py` | 14 | `json` | P2 |
| `scripts/recommend_items.py` | 26 | `collections.defaultdict` | P2 |
| `scripts/recommend_items.py` | 36 | `netsuite.NetSuiteClient` | P2 |
| `scripts/recommend_items_full.py` | 38 | `validate_category_pairings.get_llm_validation` | P2 |
| `scripts/review_tui.py` | 6 | `textual.widgets.Label` | P2 |
| `scripts/review_tui.py` | 7 | `textual.containers.Container` | P2 |
| `scripts/review_tui.py` | 7 | `textual.containers.Horizontal` | P2 |
| `scripts/review_tui.py` | 7 | `textual.containers.Vertical` | P2 |
| `tests/security/test_csv_injection.py` | 2 | `csv` | P2 |
| `tests/test_discovery.py` | 2 | `unittest.mock.MagicMock` | P2 |
| `tests/test_output.py` | 3 | `pathlib.Path` | P2 |

**Test Files (P2 - Lower Priority):**
- 8 test files with unused pytest imports
- 2 test files with other unused imports (json, config.settings)

**Remediation:**
```bash
# Automated fix available via ruff
python -m ruff check --select F401 --fix .
```

---

### 2. Hardcoded Configuration Values (P1/P2)

**Impact:** Makes testing/deployment difficult, violates 12-factor app principles  
**Count:** 9 violations

| File | Line | Value | Context | Severity | Suggested Fix |
|------|------|-------|---------|----------|---------------|
| `src/config.py` | 88 | `"http://100.64.0.3:8081"` | ATHENA_HOST default | P1 | Document in .env.template, remove hardcoded IP |
| `src/config.py` | 100 | `"http://localhost:11434"` | OLLAMA_HOST default | P2 | Already configurable via TOML |
| `src/config.py` | 103 | `"http://localhost:4000"` | LITELLM_HOST default | P2 | Already configurable via TOML |
| `src/config.py` | 108 | `"http://localhost:1234/v1"` | LOCAL_LLM_HOST default | P2 | Already configurable via TOML |
| `scripts/validate_category_pairings.py` | - | `"https://api.openai.com/v1/chat/completions"` | OpenAI endpoint | P2 | Use OpenAI SDK constant |
| `src/bigcommerce/client.py` | 15 | `"https://api.bigcommerce.com/stores/{store_hash}/v3"` | BC API base | P2 | Library constant (acceptable) |
| `src/bigcommerce/client.py` | 35 | `"https://api.bigcommerce.com/stores/{store_hash}/v2/orders"` | BC orders endpoint | P2 | Library constant (acceptable) |
| `src/bigcommerce/client.py` | 55 | `"https://api.bigcommerce.com/stores/{store_hash}/v2/orders/{order_id}/products"` | BC order products | P2 | Library constant (acceptable) |
| `src/netsuite/auth.py` | 25 | `"https://{account}.suitetalk.api.netsuite.com/services/rest"` | NetSuite API base | P2 | Library constant (acceptable) |

**Analysis:**
- **P1 Issue:** `100.64.0.3:8081` is a hardcoded private IP for Athena. This is fragile and environment-specific.
- **P2 Localhost defaults:** Acceptable for local development, but should be clearly documented
- **P2 API URLs:** These are library constants for external APIs (BigCommerce, NetSuite, OpenAI). Acceptable as they're vendor-defined.

**Remediation for P1:**
```python
# src/config.py line 88
ATHENA_HOST: str = _toml_defaults.get("ATHENA_HOST", os.getenv("ATHENA_HOST", "http://localhost:8081"))
```

And update `.env.template`:
```bash
# Athena (Local GPT-OSS)
# ATHENA_HOST=http://100.64.0.3:8081  # Production
# ATHENA_HOST=http://localhost:8081   # Local
```

---

### 3. Magic Numbers (P2)

**Impact:** Reduces code readability, makes changes error-prone  
**Count:** 12 violations

#### Sleep/Rate Limit Magic (P2)

| File | Line | Value | Context | Suggested Constant |
|------|------|-------|---------|-------------------|
| `scripts/recommend_items.py` | ~28 | `0.1` | `sleep(0.1)` | `RATE_LIMIT_DELAY = 0.1` |
| `scripts/analyze_bc_orders.py` | - | `0.1` | `sleep(0.1)  # Rate limit courtesy` | `API_RATE_LIMIT_DELAY = 0.1` |
| `easyupsell/core/analyzer.py` | - | `0.1` | `sleep(0.1)` | `API_CALL_DELAY = 0.1` |
| `scripts/analyze_pairings.py` | - | `0.1` | `sleep(0.1)` (2 occurrences) | `RATE_LIMIT_DELAY = 0.1` |
| `scripts/recommend_items_full.py` | - | `0.1` | `sleep(0.1)` | `RATE_LIMIT_DELAY = 0.1` |

**Total:** 6 files with magic sleep value `0.1`

#### Timeout Magic (P2)

| File | Line | Value | Context | Suggested Constant |
|------|------|-------|---------|-------------------|
| `scripts/validate_category_pairings.py` | ~60 | `60` | `timeout=60` | `LLM_TIMEOUT_SECONDS = 60` |
| `scripts/validate_category_pairings.py` | ~90 | `30` | `timeout=30` | `LLM_QUICK_TIMEOUT = 30` |
| `scripts/validate_category_pairings.py` | Multiple | `60` | `timeout=60` (3 more) | Same constant |
| `scripts/validate_category_pairings.py` | ~180 | `180` | `timeout=180` | `LLM_BATCH_TIMEOUT = 180` |

**Total:** 6 timeout values, should be 3 named constants

**Remediation:**
```python
# scripts/validate_category_pairings.py (top of file)
# LLM API Timeouts
LLM_TIMEOUT_SECONDS = 60        # Standard single-item call
LLM_QUICK_TIMEOUT = 30          # Quick validation
LLM_BATCH_TIMEOUT = 180         # Batch processing

# Rate limiting
API_RATE_LIMIT_DELAY = 0.1      # Seconds between API calls
```

---

### 4. Stale TODOs/FIXMEs (P0/P1/P2)

**Impact:** Technical debt tracking  
**Count:** 0 violations

✅ **EXCELLENT:** No TODOs, FIXMEs, or HACK comments found in the codebase.

---

### 5. Debug Artifacts (P0)

**Impact:** Leaks internal state, slows production  
**Count:** 0 violations

✅ **CLEAN:** No debug prints, breakpoints, or console.log statements in production code.

---

### 6. Commented-Out Code Blocks (P2)

**Impact:** Code archaeology, confusion  
**Count:** 0 violations

✅ **CLEAN:** No commented-out code blocks found.

---

### 7. Deprecated API Usage (P1)

**Impact:** Future breakage risk  
**Count:** 0 violations

✅ **CLEAN:** No deprecated API calls or markers found.

---

## Hygiene Score Calculation

| Category | Weight | Issues | Deduction |
|----------|--------|--------|-----------|
| Dead Imports | 1x | 27 | -27 |
| Hardcoded Config (non-localhost) | 2x | 1 | -2 |
| Hardcoded Config (localhost) | 1x | 3 | -3 |
| Magic Sleep Values | 1x | 6 | -6 |
| Magic Timeout Values | 1x | 6 | -6 |
| Debug Artifacts | 3x | 0 | 0 |
| Stale TODOs | 2x | 0 | 0 |
| Commented Code | 1x | 0 | 0 |
| Deprecated APIs | 2x | 0 | 0 |

**Score:** 100 - 44 = **56 (C)**

**Grade Explanation:**
- **Strengths:** No debug artifacts, no stale TODOs, no commented code
- **Weaknesses:** Many dead imports (27), some hardcoded config values
- **Overall:** Functional but needs cleanup. Code works well but has accumulated technical debt.

---

## Prioritized Remediation

### P1 - Fix This Sprint (9 issues)

1. **Hardcoded Private IP in ATHENA_HOST** - `src/config.py:88`
   - **Risk:** Breaks in different environments, hard to override
   - **Fix:** Use environment variable with fallback to localhost
   - **Effort:** 5 minutes

2. **Dead imports in core modules** (8 files)
   - `easyupsell/commands/analyze.py` - 4 unused rich.progress imports + signal
   - `easyupsell/core/analyzer.py` - 4 unused imports (defaultdict, datetime, get_llm_validation)
   - `easyupsell/core/discovery.py` - 2 unused typing imports
   - `easyupsell/core/review.py` - 2 unused imports (json, Optional)
   - `scripts/analyze_pairings.py` - json
   - `scripts/recommend_items.py` - defaultdict, NetSuiteClient
   - `scripts/recommend_items_full.py` - get_llm_validation
   - `scripts/review_tui.py` - 4 unused textual imports
   - **Risk:** Confuses code readers, suggests incomplete refactoring
   - **Fix:** `ruff check --select F401 --fix .`
   - **Effort:** 1 minute (automated)

### P2 - Backlog (30 issues)

1. **Magic sleep values** (6 files)
   - **Risk:** Hard to change rate limiting globally
   - **Fix:** Extract to named constants at module level
   - **Effort:** 10 minutes

2. **Magic timeout values** (1 file, 6 occurrences)
   - **Risk:** Inconsistent timeout handling
   - **Fix:** Extract 3 named constants (standard, quick, batch)
   - **Effort:** 5 minutes

3. **Dead imports in test files** (10 files)
   - **Risk:** Minimal (tests still pass)
   - **Fix:** `ruff check --select F401 --fix tests/`
   - **Effort:** 1 minute

4. **Localhost hardcoded URLs** (3 occurrences in config.py)
   - **Risk:** Low (already configurable via TOML)
   - **Fix:** Document in .env.template
   - **Effort:** Already acceptable

5. **API URL hardcoding** (5 occurrences)
   - **Risk:** None (vendor-defined constants)
   - **Fix:** None needed (acceptable pattern)

---

## Recommendations

### Immediate Actions (Next PR)
1. ✅ **Run automated import cleanup:** `ruff check --select F401 --fix .`
2. ✅ **Fix ATHENA_HOST:** Make it environment-variable driven
3. ✅ **Extract sleep constants:** Create `RATE_LIMIT_DELAY = 0.1` in relevant modules

### Next Sprint
1. Extract timeout constants in `validate_category_pairings.py`
2. Add `.env.template` documentation for all hardcoded defaults

### Process Improvements
1. ✅ **Pre-commit hook:** Add `ruff check --select F401` to catch dead imports
2. ✅ **Linting CI:** Enforce in GitHub Actions
3. Consider `ruff format` for consistent style

---

## Positive Hygiene Patterns Observed

1. ✅ **No debug prints in production code** - Shows good discipline
2. ✅ **No TODOs** - Team either completes work or deletes comments
3. ✅ **Config abstraction exists** - `config.py` pattern is good, just needs refinement
4. ✅ **Clear comments on rate limiting** - `sleep(0.1)  # Rate limit courtesy`
5. ✅ **Type hints used throughout** - Even if some are unused

---

*Report generated by Rem the Hygiene Demon*  
*"Your code may work, but it smells like a dorm room."*

**Final Verdict:** This is a **working codebase with moderate hygiene debt**. The lack of debug artifacts and TODOs shows good engineering discipline. The main issues (dead imports, magic numbers) are easy to fix and don't affect functionality. **Grade: C** - Clean up imports and extract constants to reach a B.
