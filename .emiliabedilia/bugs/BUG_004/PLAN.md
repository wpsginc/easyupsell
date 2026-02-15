# Fix Plan: README vs CLI Documentation Drift

## Root Cause

The README.md documents a legacy workflow using direct script invocation (`python scripts/export_categories.py`, etc.) but the codebase has evolved to use a modern Typer-based CLI with subcommands (`easyupsell analyze`, `easyupsell export`, etc.). The README Quick Start and Scripts sections reference the old pattern that no longer aligns with the actual CLI interface defined in `easyupsell/cli.py`.

## Fix Strategy

Update README.md to reflect the modern CLI commands instead of legacy script calls, ensuring documentation matches the actual Typer CLI interface.

## Steps

1. In `README.md` lines 29-32: Replace legacy script calls with modern CLI equivalents:
   - `python scripts/export_categories.py` → `easyupsell export`
   - `python scripts/validate_category_pairings.py` → `easyupsell analyze`
   - `python scripts/product_accessories.py --validate` → appropriate CLI command or note if still script-based

2. In `README.md` lines 35-42: Update Scripts table to reflect CLI subcommands instead of direct script paths, or clearly mark which operations are CLI vs legacy scripts

3. Add Quick Start section showing CLI help: `easyupsell --help` and `easyupsell analyze --help` to guide users to discoverable commands

## Verification

- Run `easyupsell --help` and verify documented commands exist
- Check that each command in updated README executes without errors
- Confirm no references to non-existent scripts remain

## Files Affected

- `README.md`
