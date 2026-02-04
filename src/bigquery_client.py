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

    QUERY_TOP_CATEGORIES = """
    SELECT
        pc.category_id AS id,
        COUNT(DISTINCT li.order_id) AS order_count,
        SUM(li.quantity) AS total_quantity,
        ROUND(SUM(li.price_ex_tax), 2) AS revenue
    FROM `bc_native.bc_order_line_items` li
    JOIN `bc_native.bc_product_category` pc ON li.product_id = pc.product_id
    GROUP BY 1
    ORDER BY revenue DESC
    """

    QUERY_ITEM_SALES = """
    SELECT 
      li.product_id AS id,
      COUNT(DISTINCT li.order_id) AS order_count,
      SUM(li.quantity) AS units_sold,
      ROUND(SUM(li.price_ex_tax), 2) AS revenue
    FROM `bc_native.bc_order_line_items` li
    GROUP BY 1
    """

    QUERY_CATEGORY_ITEM_ENRICHED = """
    WITH category_item_stats AS (
      SELECT
        pc.category_id,
        li_target.product_id AS rec_id,
        COUNT(DISTINCT li_source.order_id) AS copurchase_count,
        SUM(li_target.quantity) AS total_quantity,
        SUM(li_target.price_ex_tax) AS total_revenue,
        COUNT(DISTINCT li_target.order_id) AS unique_order_count
      FROM `bc_native.bc_order_line_items` li_source
      JOIN `bc_native.bc_product_category` pc ON li_source.product_id = pc.product_id
      JOIN `bc_native.bc_order_line_items` li_target 
        ON li_source.order_id = li_target.order_id
        AND li_source.product_id != li_target.product_id
      GROUP BY 1, 2
      HAVING copurchase_count >= 3
    ),
    product_stats AS (
      SELECT 
        li.product_id,
        SUM(li.quantity) AS units_90d,
        AVG(SAFE_DIVIDE(li.product_price - li.base_cost_price, li.product_price)) AS margin_pct
      FROM `bc_native.bc_order_line_items` li
      JOIN `bc_native.bc_order` o ON li.order_id = o.order_id
      WHERE o.order_created_date_time >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 90 DAY)
      GROUP BY 1
    )
    SELECT 
      cis.*,
      COALESCE(ps.units_90d, 0) AS rec_velocity,
      COALESCE(ps.margin_pct, 0.0) AS rec_margin,
      p.sku AS rec_sku,
      p.product_name AS rec_name,
      p.bin_picking_number AS rec_bpn
    FROM category_item_stats cis
    LEFT JOIN product_stats ps ON cis.rec_id = ps.product_id
    JOIN `bc_native.bc_product` p ON cis.rec_id = p.product_id
    ORDER BY cis.category_id, cis.copurchase_count DESC
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

    def get_top_categories(self) -> pd.DataFrame:
        """Fetch top categories by revenue."""
        return self.run_query(self.QUERY_TOP_CATEGORIES)

    def get_item_sales(self) -> pd.DataFrame:
        """Fetch item sales metrics."""
        return self.run_query(self.QUERY_ITEM_SALES)

    def get_category_item_recommendations(self) -> pd.DataFrame:
        """Fetch enriched category-item recommendations."""
        df = self.run_query(self.QUERY_CATEGORY_ITEM_ENRICHED)
        df['rec_netsuite_id'] = df['rec_bpn'].apply(self.extract_netsuite_id)
        return df

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
