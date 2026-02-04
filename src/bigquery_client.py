from typing import Optional
import pandas as pd
from google.cloud import bigquery
from config import settings

class BigQueryClient:
    """
    Client for executing queries against BigQuery.
    Designed for fetching enrichment signals (Co-purchase, Margin, Velocity).
    """

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize the BigQuery client.
        
        Args:
            project_id: GCP Project ID. Defaults to settings.BQ_PROJECT_ID.
        """
        self.project_id = project_id or settings.BQ_PROJECT_ID
        if not self.project_id:
            raise ValueError("BQ_PROJECT_ID is not set in configuration.")
            
        self.client = bigquery.Client(project=self.project_id)

    def run_query(self, sql: str) -> pd.DataFrame:
        """
        Execute a SQL query and return the results as a pandas DataFrame.
        
        Args:
            sql: The StandardSQL query to execute.
            
        Returns:
            pd.DataFrame containing the query results.
        """
        query_job = self.client.query(sql)
        return query_job.to_dataframe()

    @staticmethod
    def extract_netsuite_id(bpn: Optional[str]) -> Optional[str]:
        """
        Extract NetSuite Internal ID from the Bin Picking Number (BPN) field.
        The BPN is often comma-separated; the ID is the first value.
        """
        if not bpn:
            return None
        return bpn.split(",")[0].strip()
