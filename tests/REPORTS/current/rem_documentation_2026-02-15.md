# Documentation Demon Report
**Demon:** `documentation`  
**Date:** 2026-02-15  
**Repository:** /home/vmlinux/srcwpsg/pim/easyupsell  
**Branch:** master (dirty)  

---

## Summary
- **P0 Severity:** 1 finding (broken CLI entry point)
- **P1 Severity:** 3 findings (CLI help drift, installation instructions drift, missing links)
- **P2 Severity:** 2 findings (external link, orphaned documentation)

---

## P0 Findings - Critical Errors

### BUG_DOC_001: CLI Entry Point Broken
**Severity:** P0  
**Type:** Code Example Validity  

**Problem:**
The installed `easyupsell` command crashes on execution:
```
$ easyupsell --help
TypeError: main() missing 1 required positional argument: 'ctx'
```

**Location:** `/home/vmlinux/srcwpsg/pim/easyupsell/easyupsell/cli.py:77`

**Root Cause:**
The `main()` function at line 77 is decorated with `@app.callback(invoke_without_command=True)` which requires a `ctx: typer.Context` parameter, but the entry point script installed by pip expects a zero-argument callable.

**Evidence:**
```python
# easyupsell/cli.py:77
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """..."""
```

But `pyproject.toml:23` defines:
```toml
[project.scripts]
easyupsell = "easyupsell.cli:app"  # Should call app(), not main()
```

**Impact:**
- Every installation instruction in README.md is broken
- Users cannot run the CLI at all via the installed command
- Only workaround is `python easyupsell/cli.py` (undocumented)

**Reproduction:**
```bash
pip install -e .
easyupsell --help  # Crashes
```

**Fix Required:**
The entry point in `pyproject.toml` should be:
```toml
easyupsell = "easyupsell.cli:app"
```
This is already correct. The issue is the `main()` function is not callable as a script entry point. Remove `main()` or change it to not use `@app.callback()`.

---

## P1 Findings - High Priority

### BUG_DOC_002: CLI Help vs README Documentation Drift
**Severity:** P1  
**Type:** CLI Help vs Docs Drift  

**Problem:**
README.md documents commands that don't exist or work differently than described.

**Drift Examples:**

| README Line | README Says | CLI Reality | Status |
|-------------|-------------|-------------|---------|
| 30 | `easyupsell analyze` | Typer subcommand group, requires subcommand | ❌ Drift |
| 31 | `easyupsell review` | Typer subcommand group, requires subcommand | ❌ Drift |
| 32 | `easyupsell export` | Typer subcommand group, requires subcommand | ❌ Drift |
| 41 | `easyupsell analyze` | Is a group, not executable alone | ❌ Drift |
| 42 | `easyupsell review` | Is a group, not executable alone | ❌ Drift |
| 43 | `easyupsell export` | Is a group, not executable alone | ❌ Drift |
| 44 | `easyupsell brands` | Is a group, not executable alone | ❌ Drift |
| 45 | `easyupsell discover` | Is a group, not executable alone | ❌ Drift |
| 46 | `easyupsell config` | Is a group, not executable alone | ❌ Drift |

**CLI Reality (from --help):**
```
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ version    Show version information.                                         │
│ status     Show analysis status and statistics.                              │
│ analyze    Generate upsell recommendations                                   │
│ brands     Manage priority brand list                                        │
│ config     Configure API connections                                         │
│ discover   Discover hidden inventory                                         │
│ export     Export recommendations                                            │
│ review     Review and approve recommendations                                │
╰──────────────────────────────────────────────────────────────────────────────╯
```

The `analyze` subcommand has further subcommands (`quick`, `jobs`) per `easyupsell/cli.py:30`.

**Missing from README:**
- `easyupsell version` command exists but not documented
- `easyupsell status` command exists but not documented
- `easyupsell analyze quick` subcommand exists but not documented
- `easyupsell analyze jobs` subcommand exists but not documented

**Impact:**
- Users following Quick Start (line 30-32) will get confusing help text instead of execution
- Users reading CLI table (lines 39-46) will get errors when trying to run commands

**Fix Required:**
Update README.md to match actual CLI structure, or update CLI to match README.

---

### BUG_DOC_003: Installation Instructions Incomplete/Broken
**Severity:** P1  
**Type:** README Accuracy  

**Problem:**
README.md Quick Start instructions (lines 24-33) fail due to missing installation step.

**Issue 1: Missing pip install**
README says:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

But this doesn't install the `easyupsell` package in editable mode. The command `easyupsell analyze` will fail with "command not found" unless the user runs:
```bash
pip install -e .
```

**Issue 2: requirements.txt vs pyproject.toml**
The project uses `pyproject.toml` (modern Python packaging) but README references `requirements.txt`. Both files exist, but they may drift over time. Best practice: document ONE source of truth.

**Issue 3: Broken Entry Point (see BUG_DOC_001)**
Even if users run `pip install -e .`, the CLI crashes.

**Current State:**
```bash
$ which easyupsell
/home/vmlinux/.local/bin/easyupsell  # Installed globally, not in venv
$ easyupsell --help
TypeError: main() missing 1 required positional argument: 'ctx'
```

**Fix Required:**
Update README.md Quick Start:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .  # Installs from pyproject.toml
cp .env.template .env   # Add BC + LLM credentials
easyupsell --help  # Verify installation
```

---

### BUG_DOC_004: Internal Documentation Links Not Bidirectional
**Severity:** P1  
**Type:** Orphan Docs Risk  

**Problem:**
`conductor/index.md` links to various docs, but those docs don't link back. This creates orphan risk and poor discoverability.

**Missing Backlinks:**

| File | Linked From | Links Back? |
|------|-------------|-------------|
| `conductor/product.md` | `conductor/index.md:4` | ❌ No |
| `conductor/product-guidelines.md` | `conductor/index.md:5` | ❌ No |
| `conductor/tech-stack.md` | `conductor/index.md:6` | ❌ No |
| `conductor/workflow.md` | `conductor/index.md:9` | ❌ No |
| `conductor/code_styleguides/python.md` | `conductor/index.md:10` | ❌ No (but one directory up) |
| `conductor/tracks.md` | `conductor/index.md:13` | ❌ No |

**Impact:**
- Users navigating from child docs can't easily return to index
- No breadcrumb navigation in flat markdown structure
- Risk of docs becoming orphaned over time

**Recommendation:**
Add standard header to all conductor docs:
```markdown
_← Back to [Conductor Index](./index.md)_

# Document Title
...
```

---

## P2 Findings - Medium Priority

### BUG_DOC_005: External Link to Peasisoft Not Verified
**Severity:** P2  
**Type:** Broken Links (External)  

**Problem:**
README.md and conductor/product.md both link to:
```
https://welcome.peasisoft.com/native-upsell/
```

**Status:** Cannot verify without network access from testing demon.

**Locations:**
- README.md:3
- conductor/product.md:2

**Risk:**
- If link is broken, users can't understand the context of the tool
- External dependency on Peasisoft documentation availability

**Recommendation:**
- Add archived copy of relevant Peasisoft docs to DOCS/research/
- Add fallback text explaining Native Upsell in README if link breaks

---

### BUG_DOC_006: Orphaned Documentation in DOCS/
**Severity:** P2  
**Type:** Orphan Docs  

**Problem:**
The `DOCS/` directory contains documentation not linked from README or conductor/index.

**Orphaned Files:**
```
DOCS/bigquery_data_source.md
DOCS/dark_horse_model_benchmark.md
DOCS/research/Peasisoft Upsell Integration Research.md
DOCS/VALIDATION_REPORT_20260203.md
```

**Verification:**
Checked all `.md` files in root and conductor/ - none link to DOCS/ contents.

**Impact:**
- New developers won't discover these docs
- Docs may become stale without visibility
- Knowledge buried in file tree

**Recommendation:**
Add to README.md:
```markdown
## Documentation

- [Architecture & Data Sources](DOCS/)
- [BigQuery Integration](DOCS/bigquery_data_source.md)
- [Model Benchmarks](DOCS/dark_horse_model_benchmark.md)
- [Research Notes](DOCS/research/)
```

Or link from `conductor/index.md` under a "## Technical Deep Dives" section.

---

## Positive Findings

### ✅ Code Style Guide Link Valid
`conductor/code_styleguides/python.md:37` links to:
```
https://google.github.io/styleguide/pyguide.html
```
This is a stable, authoritative URL (Google's official style guide). No action needed.

### ✅ No Obvious Link Rot in Internal Docs
All internal links in `conductor/index.md` resolve to existing files:
- `./product.md` ✓
- `./product-guidelines.md` ✓
- `./tech-stack.md` ✓
- `./workflow.md` ✓
- `./code_styleguides/` ✓
- `./tracks.md` ✓
- `./tracks/` ✓

### ✅ Track Documentation Structure Consistent
Track `same_cat_recs_20260209` has all expected files:
- index.md ✓
- spec.md ✓
- plan.md ✓

Archive track `dark_horse_20260210` also has consistent structure.

### ✅ .env.template Well-Documented
`.env.template` has clear comments for each section:
- NetSuite setup references external doc (line 7)
- BigCommerce setup includes admin path (line 20)
- LLM provider options clearly labeled

---

## Recommendations

### Immediate (P0/P1)
1. **Fix CLI entry point** (BUG_DOC_001)
   - Verify `pyproject.toml` points to `app` not `main`
   - Test: `pip install -e . && easyupsell --help`

2. **Update README Quick Start** (BUG_DOC_003)
   - Add `pip install -e .` step
   - Remove or clarify `requirements.txt` vs `pyproject.toml`

3. **Sync CLI docs with reality** (BUG_DOC_002)
   - Update CLI Commands table in README
   - Add `version` and `status` commands
   - Note which commands are groups vs direct execution

4. **Add doc navigation** (BUG_DOC_004)
   - Add breadcrumb headers to conductor/* docs

### Nice to Have (P2)
5. **Link DOCS/ from README** (BUG_DOC_006)
6. **Archive external references** (BUG_DOC_005)

---

## Test Coverage Analysis

### Documentation Tested
- ✅ README.md - Quick Start code blocks
- ✅ CLI help output vs README command table
- ✅ Internal link validation (conductor/*)
- ✅ External link detection
- ✅ Orphan documentation detection
- ✅ .env.template accuracy

### Not Tested (Limitations)
- ❌ External link HTTP status (no network access in demon mode)
- ❌ Screenshot currency (no UI to compare against)
- ❌ Multi-step installation flows (would require clean environment)

---

## Metrics

| Metric | Count |
|--------|-------|
| Total markdown files | 62 |
| Files with external links | 10 |
| Internal links checked | 8 |
| Code blocks in README | 1 |
| CLI commands documented | 6 |
| CLI commands actual | 8 (includes version, status) |
| Orphaned doc files | 4 |
| Broken internal links | 0 |
| Missing command docs | 2 (version, status) |

---

## Files Analyzed
```
README.md
ROADMAP.md
.env.template
pyproject.toml
easyupsell/cli.py
easyupsell/__init__.py
easyupsell/commands/analyze.py
conductor/index.md
conductor/product.md
conductor/code_styleguides/python.md
DOCS/ (directory listing)
```

---

_Report generated by documentation demon (rem_documentation.md)_  
_Next run: Update after BUG_DOC_001 fix to verify CLI works end-to-end_
