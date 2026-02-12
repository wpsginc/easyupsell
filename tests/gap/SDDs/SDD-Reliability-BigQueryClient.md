# SDD: Reliability - BigQuery Client Error Handling

## 1. Gap Description
The `BigQueryClient` (`src/bigquery_client.py`) performs network calls to Google Cloud Platform but lacks error handling. Any network failure, authentication issue, or SQL error will raise an unhandled exception, crashing the entire CLI application.

## 2. Target Location
- `src/bigquery_client.py`

## 3. Test Strategy
- **Unit Test**: Mock `bigquery.Client.query` to raise `google.api_core.exceptions.ServiceUnavailable` and verify retry logic.
- **Unit Test**: Mock `bigquery.Client.query` to raise `google.api_core.exceptions.Forbidden` (Auth error) and verify graceful failure (re-raise with helpful message).

## 4. Implementation Details
1.  **Retry Logic**: Implement a decorator or method wrapper for `run_query` that retries on transient errors (5xx, Network).
    -   Use `tenacity` or `backoff` library if available, or simple loop with `time.sleep`.
2.  **Error Catching**:
    -   Wrap `client.query()` calls in `try/except`.
    -   Catch `google.api_core.exceptions.GoogleAPICallError`.
    -   Log specific error details (Query Job ID, Error Message).
    -   Raise a custom `BigQueryError` that the CLI can catch and display nicely to the user (instead of a traceback).
