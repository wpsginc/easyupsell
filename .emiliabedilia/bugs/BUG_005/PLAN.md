# Fix Plan: BigQuery Client Missing Error Handling

## Root Cause

The `run_query()` method in `src/bigquery_client.py` at line 94-105 executes BigQuery queries without any try-except blocks. Network failures, authentication errors, or quota limits will crash the application instead of providing useful error messages.

## Fix Strategy

Wrap the query execution in try-except blocks to catch common BigQuery exceptions and provide helpful error messages. Import necessary Google Cloud exceptions.

## Steps

1. In `src/bigquery_client.py` at line 4: Add import for BigQuery exceptions:
   ```python
   from google.cloud.exceptions import NotFound, Forbidden, GoogleCloudError
   ```

2. In `src/bigquery_client.py` at lines 94-105: Replace the `run_query()` method with:
   ```python
   def run_query(self, sql: str) -> pd.DataFrame:
       """
       Execute a SQL query and return the results as a pandas DataFrame.
       
       Args:
           sql: The StandardSQL query to execute.
           
       Returns:
           pd.DataFrame containing the query results.
           
       Raises:
           RuntimeError: If query execution fails.
       """
       try:
           query_job = self.client.query(sql)
           return query_job.to_dataframe()
       except Forbidden as e:
           raise RuntimeError(f"BigQuery authentication failed: {e}")
       except NotFound as e:
           raise RuntimeError(f"BigQuery table/dataset not found: {e}")
       except GoogleCloudError as e:
           raise RuntimeError(f"BigQuery error: {e}")
       except Exception as e:
           raise RuntimeError(f"Unexpected error querying BigQuery: {e}")
   ```

## Verification

- Test with invalid credentials (should get auth error)
- Test with non-existent table (should get NotFound error)
- Test with valid query (should succeed)
- Check error messages are user-friendly

## Files Affected

- `src/bigquery_client.py`
