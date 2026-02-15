# Fix Plan: Dependency Mismatch in requirements.txt

## Root Cause

The project uses `typer` for CLI functionality and `rich` for console output formatting across multiple modules (easyupsell/cli.py, commands/, scripts/), but these dependencies are not declared in requirements.txt. This causes ModuleNotFoundError when running the application in a fresh environment.

## Fix Strategy

Add the missing `typer` and `rich` package dependencies to requirements.txt with appropriate version constraints.

## Steps

1. In `requirements.txt` after line 5 (after pydantic-settings): Add `typer>=0.9.0` and `rich>=13.0.0` under a new "# CLI" comment section

## Verification

- Run `pip install -r requirements.txt` in a fresh virtual environment
- Execute `python -m easyupsell.cli --help` to verify typer imports work
- Run any script using rich (e.g., `python scripts/analyze_batch_results.py`) to verify rich imports work
- Check that all 12 files importing typer/rich can be imported without ModuleNotFoundError

## Files Affected

- `requirements.txt`
