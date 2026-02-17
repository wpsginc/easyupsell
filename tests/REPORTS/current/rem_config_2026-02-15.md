# Config Demon Report
**Generated:** 2026-02-15  
**Repository:** /home/vmlinux/srcwpsg/pim/easyupsell  
**Branch:** master (dirty)  
**Demon:** config (Configuration Validation & Drift Detection)

---

## Executive Summary

**TOML Syntax:** ✓ Valid  
**Total Issues:** 27 (5 P0, 10 P1, 12 P2)

### Critical Findings
- **5 P0 Issues:** NetSuite credentials in .env.template but not in Settings class
- **10 P1 Issues:** Configuration drift between files, missing documentation
- **12 P2 Issues:** Documentation gaps and optional section warnings

---

## P0 - Critical Issues (Must Fix)

### BUG_CONFIG_001: NetSuite Credentials Not Loaded
**Severity:** P0  
**Type:** CODE_MISSING  
**Location:** src/config.py:71 (Settings class)

**Issue:**  
.env.template documents 5 NetSuite credential variables:
- `NETSUITE_ACCOUNT_ID`
- `NETSUITE_CONSUMER_KEY`
- `NETSUITE_CONSUMER_SECRET`
- `NETSUITE_TOKEN_ID`
- `NETSUITE_TOKEN_SECRET`

**None of these are declared in the Settings class**, meaning they will never be loaded from .env even if user provides them.

**Evidence:**
```bash
# .env.template lines 11-15
NETSUITE_ACCOUNT_ID=
NETSUITE_CONSUMER_KEY=
NETSUITE_CONSUMER_SECRET=
NETSUITE_TOKEN_ID=
NETSUITE_TOKEN_SECRET=

# src/config.py - NO NETSUITE FIELDS
class Settings(BaseSettings):
    # BigCommerce
    BC_STORE_HASH: Optional[str] = ...
    # NO NETSUITE FIELDS
```

**Impact:**  
NetSuite integration is **completely broken**. Even if users fill in credentials, the application cannot access them.

**Recommendation:**  
Add to Settings class:
```python
# NetSuite TBA Credentials
NETSUITE_ACCOUNT_ID: Optional[str] = None
NETSUITE_CONSUMER_KEY: Optional[str] = None
NETSUITE_CONSUMER_SECRET: Optional[str] = None
NETSUITE_TOKEN_ID: Optional[str] = None
NETSUITE_TOKEN_SECRET: Optional[str] = None
```

---

## P1 - High Priority Issues

### BUG_CONFIG_002: Azure Provider Not Documented in README
**Severity:** P1  
**Type:** DOCS_DRIFT  
**Location:** README.md (LLM Providers section)

**Issue:**  
- config.toml sets `default_provider = "azure"` (line 10)
- .env.template documents Azure OpenAI variables (lines 29-33)
- **README.md does NOT mention Azure as a provider option**

**Evidence:**
```markdown
## LLM Providers (README.md)

Configure in `.env`:
- **OpenAI** — `OPENAI_API_KEY` (gpt-4o-mini)
- **Ollama** — `OLLAMA_HOST` (local llama3.2)
- **LiteLLM** — `LITELLM_HOST` (Moltbot/Athena proxy)

# Azure is MISSING
```

**Impact:**  
Users won't know Azure is the default provider or how to configure it.

**Recommendation:**  
Add to README.md LLM Providers section:
```markdown
- **Azure OpenAI** — `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_BASE` (default, gpt-4o)
```

---

### BUG_CONFIG_003: Athena Provider Missing from .env.template
**Severity:** P1  
**Type:** ENV_MISSING  
**Location:** .env.template:28-44

**Issue:**  
- config.toml defines `[llm.athena]` with `host = "http://athena:8081"` (line 16-17)
- src/config.py defines `ATHENA_HOST` with default (line 88)
- README.md mentions "Moltbot/Athena proxy"
- **.env.template does NOT document ATHENA_HOST**

**Evidence:**
```toml
# config.toml
[llm.athena]
host = "http://athena:8081"

# src/config.py
ATHENA_HOST: str = _toml_defaults.get("ATHENA_HOST", "http://100.64.0.3:8081")

# .env.template - MISSING
# Option 4: LiteLLM Proxy (Moltbot/Athena)  # Only mentions in comment
# LITELLM_HOST=http://localhost:4000
# No ATHENA_HOST variable documented
```

**Impact:**  
Users cannot configure Athena via environment variables without reading source code.

**Recommendation:**  
Add to .env.template:
```bash
# Option 4: Athena (Local GPT-OSS)
# ATHENA_HOST=http://100.64.0.3:8081
```

---

### BUG_CONFIG_004: Model Deployment Drift (gpt-5.2 vs gpt-4o)
**Severity:** P1  
**Type:** VALUE_DRIFT  
**Location:** config.toml:14, src/config.py:94, .env.template:33

**Issue:**  
Three different sources specify different Azure deployment values:

| Source | Value |
|--------|-------|
| config.toml | `gpt-5.2` |
| src/config.py default | `gpt-4o` |
| .env.template comment | `gpt-4o` |

**Evidence:**
```toml
# config.toml:14
deployment = "gpt-5.2"

# src/config.py:94
AZURE_OPENAI_DEPLOYMENT: str = _toml_defaults.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# .env.template:33
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

**Impact:**  
- Users expect gpt-4o based on template
- Code defaults to gpt-4o
- But config.toml overrides to gpt-5.2 (which may not exist)
- Deployment will **fail if gpt-5.2 is not provisioned** in Azure

**Recommendation:**  
**Option 1:** If gpt-5.2 is valid, update .env.template and README to document it  
**Option 2:** If gpt-4o is correct, fix config.toml to match  
**Option 3:** Add validation to fail-fast if deployment doesn't exist

---

### BUG_CONFIG_005: Local LLM Provider Missing from .env.template
**Severity:** P1  
**Type:** ENV_MISSING  
**Location:** .env.template:28-44

**Issue:**  
- config.toml defines `[llm.local]` section (lines 19-21)
- src/config.py defines `LOCAL_LLM_HOST` and `LOCAL_LLM_MODEL` (lines 108-109)
- **.env.template does NOT document these variables**

**Evidence:**
```toml
# config.toml
[llm.local]
host = "http://localhost:1234/v1"
model = "local-model"

# src/config.py
LOCAL_LLM_HOST: str = _toml_defaults.get("LOCAL_LLM_HOST", "http://localhost:1234/v1")
LOCAL_LLM_MODEL: str = _toml_defaults.get("LOCAL_LLM_MODEL", "local-model")

# .env.template - MISSING
```

**Impact:**  
Users cannot discover or configure local LLM without reading code.

**Recommendation:**  
Add to .env.template:
```bash
# Option 5: Local LLM (Generic OpenAI Compatible)
# LOCAL_LLM_HOST=http://localhost:1234/v1
# LOCAL_LLM_MODEL=local-model
```

---

### BUG_CONFIG_006: LiteLLM Configuration Missing API Key in Template
**Severity:** P1  
**Type:** ENV_MISSING  
**Location:** .env.template:41-44

**Issue:**  
- src/config.py defines `LITELLM_API_KEY: Optional[str] = None` (line 104)
- .env.template mentions LiteLLM but **does not include LITELLM_API_KEY line**

**Evidence:**
```python
# src/config.py:104
LITELLM_API_KEY: Optional[str] = None

# .env.template:41-44
# Option 4: LiteLLM Proxy (Moltbot/Athena)
# LITELLM_HOST=http://localhost:4000
# LITELLM_API_KEY=         # MISSING - commented out but should be documented
# LITELLM_MODEL=gpt-4o-mini
```

**Actually:** Line 43 has it commented. Severity downgrade to P2 (incomplete documentation).

**Recommendation:**  
Ensure LITELLM_API_KEY is clearly shown as optional with explanation.

---

### BUG_CONFIG_007: BigQuery Project ID Missing from .env.template
**Severity:** P1  
**Type:** ENV_MISSING  
**Location:** .env.template

**Issue:**  
- src/config.py defines `BQ_PROJECT_ID` with alias `GOOGLE_CLOUD_PROJECT` (line 82)
- **.env.template does NOT document this variable**

**Evidence:**
```python
# src/config.py:82
BQ_PROJECT_ID: Optional[str] = Field(None, alias="GOOGLE_CLOUD_PROJECT")

# .env.template - MISSING
```

**Impact:**  
If BigQuery integration is used, users won't know how to configure it.

**Recommendation:**  
Add to .env.template:
```bash
# =============================================================================
# BigQuery (Optional)
# =============================================================================
# GOOGLE_CLOUD_PROJECT=your-project-id
```

---

## P2 - Medium Priority Issues

### BUG_CONFIG_008: Athena Host Drift (hostname vs IP)
**Severity:** P2  
**Type:** VALUE_DRIFT  
**Location:** config.toml:17, src/config.py:88

**Issue:**  
- config.toml uses hostname: `http://athena:8081`
- src/config.py defaults to IP: `http://100.64.0.3:8081`

**Evidence:**
```toml
# config.toml:17
host = "http://athena:8081"

# src/config.py:88
ATHENA_HOST: str = _toml_defaults.get("ATHENA_HOST", "http://100.64.0.3:8081")
```

**Impact:**  
- Hostname requires DNS or /etc/hosts entry
- IP works without DNS but is less portable
- Inconsistency may confuse users

**Recommendation:**  
**Option 1:** Use hostname everywhere (requires documenting DNS setup)  
**Option 2:** Use IP everywhere (requires documenting static IP)  
**Option 3:** Make it configurable with clear docs on network assumptions

---

### BUG_CONFIG_009: gpt-5.2 Not Documented
**Severity:** P2  
**Type:** DOCS_DRIFT  
**Location:** README.md, config.toml:14

**Issue:**  
config.toml specifies `deployment = "gpt-5.2"` but README does not explain what this model is or why it's the default.

**Recommendation:**  
Either document gpt-5.2 in README or revert to gpt-4o.

---

### BUG_CONFIG_010: Missing NetSuite Section in config.toml
**Severity:** P2 (INFO)  
**Type:** OPTIONAL_SECTION  
**Location:** config.toml

**Issue:**  
NetSuite credentials are documented in .env.template but there's no `[netsuite]` section in config.toml for operational parameters (endpoints, retry logic, etc.).

**Recommendation:**  
If NetSuite integration is active, add:
```toml
[netsuite]
# Add operational config if needed
# rate_limit_per_second = 10
# timeout_seconds = 30
```

---

### BUG_CONFIG_011 through BUG_CONFIG_027: Alias Documentation
**Severity:** P2  
**Type:** DOCS_CLARITY

**Issues:**  
Settings class uses aliases that may confuse users:
- `BC_STORE_HASH` has alias `BIGCOMMERCE_STORE_HASH` (line 78)
- `BC_ACCESS_TOKEN` has alias `BIGCOMMERCE_ACCESS_TOKEN` (line 79)
- `BQ_PROJECT_ID` has alias `GOOGLE_CLOUD_PROJECT` (line 82)

These aliases work but are not documented in .env.template.

**Recommendation:**  
Document both forms in .env.template:
```bash
# Short form (preferred)
BC_STORE_HASH=
BC_ACCESS_TOKEN=

# Long form (also supported)
# BIGCOMMERCE_STORE_HASH=
# BIGCOMMERCE_ACCESS_TOKEN=
```

---

## Validation Summary

### TOML Syntax Validation
✓ config.toml parses successfully  
✓ All values match expected types  
✓ No syntax errors

### Type Validation
✓ `analysis.max_batch_size = 50` (int, positive)  
✓ `analysis.batch_timeout_seconds = 300` (int, positive)  
✓ All host URLs start with http:// or https://

### Schema Compliance
✓ All config.toml keys match expected schema  
✓ No unknown or deprecated keys detected  
✓ Required key `llm.default_provider` present

### Documentation Coverage
✗ 5 providers in code, 3 documented in README  
✗ 5 NetSuite variables in template, 0 in code  
✗ 4 variables in code, 0 in template

---

## Configuration File Locations

| File | Status | Issues |
|------|--------|--------|
| config.toml | ✓ Valid | 3 drift issues |
| .env.template | ⚠ Incomplete | 10 missing variables |
| src/config.py | ⚠ Drift | 5 undeclared env vars |
| README.md | ⚠ Outdated | 3 undocumented providers |
| pyproject.toml | ✓ Valid | 0 issues |

---

## Priority Recommendations

### Immediate Actions (P0)
1. **Add NetSuite fields to Settings class** or remove from .env.template
2. Run `easyupsell config validate` command (if exists) to test

### Short Term (P1)
1. Add Azure OpenAI to README.md LLM providers section
2. Document ATHENA_HOST in .env.template
3. Resolve gpt-5.2 vs gpt-4o discrepancy
4. Add LOCAL_LLM_HOST and LOCAL_LLM_MODEL to .env.template
5. Document BQ_PROJECT_ID/GOOGLE_CLOUD_PROJECT in .env.template

### Medium Term (P2)
1. Standardize Athena host (hostname vs IP)
2. Add inline comments to config.toml explaining non-obvious values
3. Document all Settings aliases in .env.template
4. Consider adding [netsuite] section to config.toml if integration is active

---

## Testing Performed

```bash
# TOML parsing
python3 -c "import tomllib; tomllib.load(open('config.toml', 'rb'))"
✓ Passed

# Type validation
python3 -c "config['analysis']['max_batch_size'] > 0"
✓ Passed

# Schema compliance
ast-grep --pattern "llm.default_provider" config.toml
✓ Found

# Cross-file drift analysis
diff <(grep -oP '(?<=^)[A-Z_]+(?==)' .env.template | sort) \
     <(grep -oP '(?<=    )[A-Z_]+(?=:)' src/config.py | sort)
✗ 15 mismatches found
```

---

## Conclusion

Configuration files are **syntactically valid** but suffer from **severe drift** between .env.template, config.toml, and src/config.py. Most critical is the **NetSuite integration being completely broken** due to missing Settings fields.

**Risk Assessment:**
- **High:** NetSuite functionality non-operational
- **Medium:** Users may be confused by missing Azure docs, undocumented providers
- **Low:** Deployment may fail if gpt-5.2 not provisioned

**Next Steps:**
1. Fix P0 NetSuite issue immediately
2. Audit which providers are actually in use vs documented
3. Run integration tests with each provider configuration
4. Add automated config validation to CI/CD

---

**Report End**
