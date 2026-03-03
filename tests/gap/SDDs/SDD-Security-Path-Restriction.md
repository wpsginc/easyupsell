# SDD: Security - Database Path Restriction

## 1. Gap Description
The migration script accepts an arbitrary `--db` path. This allows a user (potentially with elevated privileges in a shared environment) to overwrite critical system files or create databases in unauthorized locations (Path Traversal / Arbitrary File Write).

## 2. Target Location
- **Script:** `scripts/migrate_csv_to_db.py`
- **Test:** `tests/gap/test_security_path_restriction.py`

## 3. Test Strategy
1.  **Test Case:** Attempt to run migration with `--db /tmp/malicious.db` or `../outside_project.db`.
2.  **Expectation:** The script should raise a `ValueError` or `SystemExit` before attempting to write.
3.  **Allowed Paths:** The DB path must be within the project's `data/` directory (or a configured safe directory).

## 4. Implementation Details
1.  **Validation Logic:**
    -   In `main()` or `migrate_csv_to_db()`, resolve the `db_path`.
    -   Check if `db_path` is relative to the current working directory's `data/` folder.
    -   Or, enforce that `db_path.parent` is exactly `data/`.
2.  **Code Snippet:**
    ```python
    def _validate_db_path(path: Path) -> None:
        # Resolve to absolute
        abs_path = path.resolve()
        # Define allowed root (e.g., project/data)
        allowed_root = Path.cwd() / "data"
        if not str(abs_path).startswith(str(allowed_root)):
            raise ValueError(f"Database path must be inside {allowed_root}")
    ```

## 5. Recommended Executor
**Demon:** rem_security
