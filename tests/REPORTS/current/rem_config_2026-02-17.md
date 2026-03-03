# Config Demon Report - 2026-02-17

**Status:** 🔴 **FAILED** (Critical Drift Detected)
**Agent:** Config Demon (Antigravity)
**Time:** 2026-02-17

## Executive Summary
Configuration management has degraded significantly. While `config.toml` remains syntactically valid, it has drifted from the codebase's actual defaults and logic. Critical integrations (NetSuite) completely bypass the central configuration system, reading environment variables directly and ignoring potential config file overrides.

## 1. Critical Issues (P0)

### 🚨 Invalid LLM Deployment
**Location:** `config.toml` vs `src/config.py`
- **Config:** `llm.azure.deployment = "gpt-5.2"`
- **Code Default:** `gpt-4o`
- **Impact:** `gpt-5.2` is likely a hallucinated or non-existent model version. Using this configuration will cause LLM pipeline failures immediately upon deployment.

## 2. High Severity Issues (P1)

### ⚠️ NetSuite Auth Bypasses Config System
**Location:** `src/netsuite/auth.py`
- **Issue:** The `NetSuiteCredentials.from_env()` method reads `os.environ["NETSUITE_..."]` directly.
- **Violation:** Bypasses `src/config.Settings` and `config.toml`.
- **Impact:** Configuration is fragmented. Centralized validation in `Settings` is rendered useless for NetSuite integration.

### ⚠️ CLI Ignores Config Defaults
**Location:** `easyupsell/cli.py`
- **Issue:** The `sync_netsuite` command uses hardcoded `typer.Option` defaults (`max_rpm=40`, `batch_size=50`) instead of reading from `settings`.
- **Impact:** Changing values in `config.toml` (e.g., `analysis.max_batch_size`) has **no effect** on the CLI command unless flags are explicitly provided.

## 3. Medium Severity Issues (P2)

### ⚠️ Missing NetSuite Config Section
**Location:** `config.toml`
- **Issue:** No `[netsuite]` section exists, despite the feature being active.
- **Impact:** Operational parameters like `max_rpm` cannot be configured via file, forcing CLI flag usage.

### ⚠️ Host Configuration Drift
**Location:** `config.toml` vs `src/config.py`
- **Athena Host:** `http://athena:8081` (config) vs `http://100.64.0.3:8081` (code).
- **Impact:** Inconsistent behavior between local dev and other environments.

### ⚠️ Missing LLMC Config
**Location:** Root
- **Issue:** `llmc.toml` validation was requested but the file does not exist.
- **Impact:** Potential missing tooling configuration if LLMC is used.

## 4. Remediation Plan

1.  **Fix `config.toml`**:
    - Change `gpt-5.2` to `gpt-4o`.
    - Add `[netsuite]` section with `max_rpm` and `batch_size`.

2.  **Refactor `src/config.py`**:
    - Add `NetSuiteSettings` class or fields to `Settings`.
    - Map `config.toml` `[netsuite]` section to these settings.

3.  **Refactor `src/netsuite/auth.py`**:
    - Inject `Settings` instead of reading `os.environ`.

4.  **Refactor CLI**:
    - Use `settings.MAX_RPM` and `settings.MAX_BATCH_SIZE` as defaults for `typer.Option`.

## Appendix: Validation Log
- `config.toml` Syntax: ✅ Valid
- `config.toml` Required Keys: ✅ Present
- Path Validation: ⚠️ URL connectivity not verified
- Type Validation: ✅ Correct types (int, bool, string)
