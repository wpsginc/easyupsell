# SDD: Robustness - Malformed CSV Handling

## 1. Gap Description
The migration script assumes well-formed CSVs. If `csv.DictReader` encounters a malformed line (e.g., unclosed quote, different delimiter), it might raise a `csv.Error` or `StopIteration` in a way that halts the entire migration.

## 2. Target Location
- **Script:** `scripts/migrate_csv_to_db.py`
- **Test:** `tests/gap/test_robustness_malformed_csv.py`

## 3. Test Strategy
1.  **Fixture:** Create `malformed.csv` with:
    -   Row 1: Valid.
    -   Row 2: `Tactical Boots,"Unclosed Quote...`
    -   Row 3: Valid.
2.  **Execution:** Run `migrate_csv_to_db`.
3.  **Expectation:**
    -   Script handles `csv.Error`.
    -   Valid rows are imported.
    -   Error count increments.

## 4. Implementation Details
1.  **Code Change:**
    -   Wrap the `for row in reader:` loop in a `try...except csv.Error` block?
    -   *Problem:* `csv.DictReader` is an iterator. If it raises, the iterator might be broken.
    -   *Alternative:* Pre-validate or read line-by-line and sniff?
    -   *Better:* Use `pandas`? No, heavy dependency.
    -   *Standard:* Accept that `csv` module might raise. Wrap the iteration.
    ```python
    try:
        for row in reader:
            # ... process
    except csv.Error as e:
        print(f"Critical CSV error: {e}")
    ```
    -   Ideally, we want to *skip* the bad line and continue. `csv` module doesn't easily support resuming after syntax error.
    -   *Compromise:* If critical CSV error occurs, log fatal error and exit gracefully (not traceback).

## 5. Recommended Executor
**Demon:** rem_bedilia
