# Fix Plan: CLI Entry Point Failure

## Root Cause

The README instructs users to install via `pip install -r requirements.txt`, but requirements.txt only contains dependencies, not the package itself. The CLI entry point `easyupsell` is only registered when the package is installed via `pip install -e .` or `pip install .`, which reads pyproject.toml and registers the console script.

## Fix Strategy

Update README.md to include the package installation step after installing requirements.

## Steps

1. In `README.md` at line 40-44: Replace the Quick Start installation commands with:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   pip install -e .             # Install the package in editable mode
   cp .env.template .env        # Add BC + LLM credentials
   ```

## Verification

- Run the Quick Start commands from scratch in a new environment
- Verify `easyupsell --help` works after installation
- Confirm `which easyupsell` points to the venv bin

## Files Affected

- `README.md`
