# UPGRADE DEMON REPORT
**Date:** 2026-02-15  
**Repository:** /home/vmlinux/srcwpsg/pim/easyupsell  
**Branch:** master  
**Demon:** upgrade  
**Focus:** Version migration paths, config compatibility, breaking changes

---

## EXECUTIVE SUMMARY

**CRITICAL FINDINGS:** 2 P0, 2 P1, 1 P2  
**Status:** ⚠️ BLOCKING ISSUES FOUND

The codebase has **NO migration infrastructure** and contains **breaking configuration incompatibilities** that will cause silent failures for users upgrading from earlier configurations or attempting to use documented config patterns.

---

## P0 — BLOCKING ISSUES

### BUG_UPGRADE_001: Environment Variable Naming Drift (Config vs Template)
**Severity:** P0  
**Impact:** Silent configuration failure, broken API connections

**Evidence:**
- `.env.template` documents: `AZURE_OPENAI_API_BASE` (line 31)
- `config.py` expects: `AZURE_OPENAI_API_BASE` (line 92) ✓
- `config.py` test command reads: `AZURE_OPENAI_ENDPOINT` (config.py:43, 87)
- Two different variable names for the same value!

**Reproduction:**
```bash
# User follows .env.template:
AZURE_OPENAI_API_BASE=https://your-instance.openai.azure.com/

# Then runs:
easyupsell config test

# Result: Fails silently because config.py:87 reads AZURE_OPENAI_ENDPOINT (None)
```

**Files:**
- `easyupsell/commands/config.py:43` (reads `AZURE_OPENAI_ENDPOINT`)
- `easyupsell/commands/config.py:87` (reads `AZURE_OPENAI_ENDPOINT`)
- `src/config.py:92` (defines `AZURE_OPENAI_API_BASE`)
- `.env.template:31` (documents `AZURE_OPENAI_API_BASE`)

**Breaking Change Type:** Variable naming inconsistency across codebase modules

---

### BUG_UPGRADE_002: BigCommerce Environment Variable Alias Mismatch
**Severity:** P0  
**Impact:** Config validation shows "missing" even when correctly configured

**Evidence:**
- `.env.template` documents: `BC_STORE_HASH`, `BC_ACCESS_TOKEN` (lines 23-24)
- `src/config.py:78-79` defines fields with aliases:
  ```python
  BC_STORE_HASH: Optional[str] = Field(None, alias="BIGCOMMERCE_STORE_HASH")
  BC_ACCESS_TOKEN: Optional[str] = Field(None, alias="BIGCOMMERCE_ACCESS_TOKEN")
  ```
- `easyupsell/commands/config.py:36-37` reads different names:
  ```python
  bc_hash = env.get("BIGCOMMERCE_STORE_HASH", "")
  bc_token = env.get("BIGCOMMERCE_ACCESS_TOKEN", "")
  ```

**Reproduction:**
```bash
# User follows .env.template:
BC_STORE_HASH=abc123
BC_ACCESS_TOKEN=xyz789

# Then runs:
easyupsell config show

# Result: Shows "✗ Missing" because config.py reads BIGCOMMERCE_* not BC_*
```

**Files:**
- `easyupsell/commands/config.py:36-37` (expects `BIGCOMMERCE_*`)
- `src/config.py:78-79` (expects `BC_*` with alias fallback)
- `.env.template:23-24` (documents `BC_*`)

**Breaking Change Type:** Config validation reads wrong variable names

---

## P1 — HIGH SEVERITY

### BUG_UPGRADE_003: No Version Migration Infrastructure
**Severity:** P1  
**Impact:** Users cannot safely upgrade; no rollback mechanism

**Evidence:**
- Current version: `0.1.0` (pyproject.toml:3, easyupsell/__init__.py:7)
- No migration scripts found
- No `migrations/` directory
- No version compatibility checking in CLI
- No data schema versioning

**Missing Capabilities:**
1. **Data format migration** — CSV schema could change (approved_category_pairings.csv has specific columns)
2. **Config migration** — No tool to migrate old `.env` → new format
3. **Database schema versioning** — SQL query assumes specific BigQuery schema (sql/category_ranking.sql)
4. **Rollback safety** — No way to downgrade data/config

**Risk:**
- Future schema changes will break existing data files
- Users who upgrade cannot roll back
- No detection of incompatible data formats

**Recommendation:**
- Add `easyupsell migrate` command
- Version data files with schema markers
- Create migration scripts in `migrations/` directory
- Add version compatibility check on startup

---

### BUG_UPGRADE_004: SQL Schema Assumes Fixed BigQuery Table Structure
**Severity:** P1  
**Impact:** Query breaks if upstream BigQuery schema changes

**Evidence:**
- `sql/category_ranking.sql` hardcodes table references:
  - `bc_native.bc_order_line_items` (lines 19, 20, 52)
  - `bc_native.bc_product_category` (lines 21, 50)
  - `bc_native.bc_category` (line 22)
  - `bc_native.bc_product` (line 51)
- No schema version checking
- No fallback for missing columns
- Assumes column names: `product_id`, `order_id`, `quantity`, `total_inc_tax`, `bin_picking_number`, `inventory_level`

**Risk:**
- If BigQuery team renames tables/columns, queries silently fail
- No version pinning or compatibility layer
- No graceful degradation

**Recommendation:**
- Add schema version metadata query
- Implement column existence checks
- Create compatibility layer for column name changes
- Document required BigQuery schema version

---

## P2 — MODERATE SEVERITY

### BUG_UPGRADE_005: CSV Output Schema Drift Risk
**Severity:** P2  
**Impact:** Old data files may be incompatible with newer code

**Evidence:**
Current CSV schemas are hardcoded in `easyupsell/core/output.py`:

**Dark Horse Pairings (lines 13-22):**
```python
fieldnames = [
    "source_category", "target_category", "suggested_weight",
    "relationship_type", "reason", "llm_model_used",
    "concept_matched", "match_confidence"
]
```

**Catalog Gaps (lines 51-56):**
```python
fieldnames = [
    "source_category", "missing_product_type",
    "suggested_weight", "reason"
]
```

**Risk:**
- If field names change, old CSV files won't load
- No schema version marker in CSV files
- `easyupsell review` and `easyupsell export` assume current schema

**Existing Data:**
```
data/approved_category_pairings.csv (5 columns)
data/dark_horse_pairings.csv (8 columns)
data/pairing_analysis.csv
```

**Recommendation:**
- Add schema version as CSV comment or metadata row
- Implement backwards-compatible CSV reader
- Add `easyupsell validate-data` command to check file compatibility

---

## UPGRADE PATH ANALYSIS

### Current State
- **Version:** 0.1.0 (initial release)
- **No Prior Versions:** First version, so no upgrade path needed YET
- **Breaking Changes:** None documented (but system unprepared for future)

### Future Risk (when 0.2.0 ships)
Without migration infrastructure:
1. ❌ Config changes → users must manually edit `.env`
2. ❌ CSV schema changes → old data files break
3. ❌ SQL changes → queries fail silently
4. ❌ No rollback → stuck on broken version

---

## BACKWARDS COMPATIBILITY ASSESSMENT

### Config Files (`.env`)
**Status:** ⚠️ BROKEN (P0 bugs prevent even current version from working)

**Test Case:**
```bash
# Following documented .env.template:
BC_STORE_HASH=test123
AZURE_OPENAI_API_BASE=https://test.openai.azure.com/
AZURE_OPENAI_API_KEY=testkey

# Running validation:
easyupsell config show
# EXPECTED: ✓ Configured
# ACTUAL: ✗ Missing (reads wrong variable names)
```

### Data Files (CSV/JSON)
**Status:** ⚠️ NO VERSIONING

- No schema version markers
- No compatibility checking
- Will break on first schema change

### Database Queries (SQL)
**Status:** ⚠️ BRITTLE

- Hardcoded table/column names
- No schema version pinning
- No error handling for missing columns

---

## ROLLBACK SAFETY

**Current State:** ❌ NO ROLLBACK MECHANISM

**What's Missing:**
1. No data backup before upgrade
2. No config backup/restore
3. No version downgrade support
4. No "undo migration" capability

**Recommendation:**
Add `easyupsell backup` and `easyupsell restore` commands

---

## DEPRECATION ANALYSIS

**Current:** None (version 0.1.0)

**Future Deprecations to Plan:**
1. When adding migration system, deprecate direct CSV writes without versioning
2. When standardizing config, deprecate old variable names with warnings
3. Document deprecation timeline in CHANGELOG.md (currently missing)

---

## RECOMMENDATIONS

### Immediate (Fix P0 Bugs)
1. ✅ Fix environment variable naming inconsistencies
2. ✅ Align config.py test command with src/config.py definitions
3. ✅ Update .env.template if needed for clarity

### Short-Term (Add Migration Infrastructure)
1. Create `migrations/` directory
2. Add `easyupsell migrate` command
3. Version CSV files with schema metadata
4. Add startup version compatibility check

### Long-Term (Robust Upgrade System)
1. Implement config migration tool
2. Add data backup/restore commands
3. Create SQL schema compatibility layer
4. Add CHANGELOG.md with deprecation notices
5. Implement automated upgrade testing

---

## FILES REQUIRING MIGRATION SUPPORT

### Configuration
- `.env` (no migration script)
- `config.toml` (optional, not documented in README)

### Data Files
- `data/approved_category_pairings.csv`
- `data/dark_horse_pairings.csv`
- `data/pairing_analysis.csv`
- `data/*.json` (validation results, categories, test pairings)

### Database Queries
- `sql/category_ranking.sql` (BigQuery schema dependency)

---

## TESTING GAPS

**Missing Tests:**
1. ❌ No upgrade path tests
2. ❌ No config migration tests
3. ❌ No backwards compatibility tests
4. ❌ No rollback tests
5. ❌ No old data format loading tests

**Recommendation:**
Add `tests/test_upgrade.py` with:
- Config migration test suite
- Old CSV format compatibility tests
- Version detection tests

---

## CONCLUSION

**Overall Grade:** ⚠️ D (NEEDS IMMEDIATE ATTENTION)

**Summary:**
- **2 P0 bugs** prevent even CURRENT version from working correctly with documented config
- **No migration infrastructure** means first schema change will break users
- **No rollback safety** means users stuck on broken upgrades
- **First version (0.1.0)** so no immediate upgrade risk, but system unprepared for 0.2.0

**Action Required:**
1. **URGENT:** Fix P0 config variable naming bugs
2. **Before 0.2.0:** Implement migration infrastructure
3. **Before Production:** Add backwards compatibility tests

---

**Report Generated:** 2026-02-15  
**Demon:** upgrade  
**Runtime:** Manual audit (automated script incomplete)
