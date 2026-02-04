from typing import Optional
import logging
import pandas as pd
from google.cloud import bigquery
from config import settings

logger = logging.getLogger(__name__)

class BigQueryClient:
    """
    Client for executing queries against BigQuery.
    Designed for fetching enrichment signals (Co-purchase, Margin, Velocity).
    """

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize the BigQuery client.
        
        Args:
            project_id: GCP Project ID. If None, tries settings.BQ_PROJECT_ID, 
                       then falls back to ADC default.
        """
        self.project_id = project_id or settings.BQ_PROJECT_ID
        
        # If project_id is still None, Client() will attempt to infer it from ADC
        self.client = bigquery.Client(project=self.project_id)
        
        # Update project_id with the resolved one
        if not self.project_id:
            self.project_id = self.client.project

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
        Logs a WARNING if missing or malformed.
        """
        if not bpn or not bpn.strip():
            logger.warning("NetSuite ID missing or empty in BPN field")
            return None
        
        try:
            ns_id = bpn.split(",")[0].strip()
            if not ns_id:
                logger.warning(f"NetSuite ID extraction failed for BPN: {bpn}")
                return None
            return ns_id
        except Exception as e:
            logger.warning(f"Error extracting NetSuite ID from BPN '{bpn}': {e}")
            return None
