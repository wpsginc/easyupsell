# Fixer Output: README vs CLI Documentation Drift

## Turn: 1

## Changes Made

1. `README.md:29-32` — Replaced legacy script calls with modern CLI commands:
   - `python scripts/export_categories.py` → `easyupsell analyze`
   - `python scripts/validate_category_pairings.py` → `easyupsell review`
   - `python scripts/product_accessories.py --validate` → `easyupsell export`

2. `README.md:35-42` — Replaced "Scripts" table with "CLI Commands" table showing all modern Typer CLI subcommands from cli.py (analyze, review, export, brands, discover, config) with guidance to run `easyupsell --help`

3. `README.md:51-60` — Removed outdated "Product Accessories" customization section that referenced non-existent scripts/product_accessories.py, kept only relevant LLM validation prompt section

## Diagnostics

- README.md is markdown (no LSP diagnostics available)

## Verification

- Verified cli.py defines subcommands: analyze, review, export, brands, discover, config
- Updated README now references actual CLI interface instead of legacy scripts
- All documented commands match cli.py implementation

## Notes

- The CLI entry point has a type signature issue (main() requires ctx argument) but that's unrelated to this documentation fix
- Focused only on aligning README with actual CLI interface per plan
