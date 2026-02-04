#!/usr/bin/env python3
"""
Fetch Enrichment Data from BigQuery.

Executes queries to retrieve:
1. Item-Item Co-occurrence (with Margin & Velocity)
2. Category-Item Co-occurrence (with Margin & Velocity)

Outputs:
    data/enrichment_data.json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bigquery_client import BigQueryClient

QUERY_ITEM_ITEM = """
WITH copurchase AS (
  SELECT 
    a.product_id AS source_id,
    b.product_id AS rec_id,
    COUNT(DISTINCT a.order_id) AS copurchase_count
  FROM `bc_native.bc_order_line_items` a
  JOIN `bc_native.bc_order_line_items` b 
    ON a.order_id = b.order_id 
    AND a.product_id != b.product_id
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
  c.source_id,
  p_source.sku AS source_sku,
  c.rec_id,
  c.copurchase_count,
  COALESCE(ps.units_90d, 0) AS rec_velocity,
  COALESCE(ps.margin_pct, 0.0) AS rec_margin,
  p.sku AS rec_sku,
  p.product_name AS rec_name,
  SPLIT(p.bin_picking_number, ',')[OFFSET(0)] AS rec_netsuite_id
FROM copurchase c
JOIN `bc_native.bc_product` p_source ON c.source_id = p_source.product_id
LEFT JOIN product_stats ps ON c.rec_id = ps.product_id
JOIN `bc_native.bc_product` p ON c.rec_id = p.product_id
ORDER BY c.copurchase_count DESC
"""

QUERY_CATEGORY_ITEM = """
WITH category_copurchase AS (
  SELECT
    pc.category_id,
    li_target.product_id AS rec_id,
    COUNT(DISTINCT li_source.order_id) AS copurchase_count
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
  cc.category_id,
  cc.rec_id,
  cc.copurchase_count,
  COALESCE(ps.units_90d, 0) AS rec_velocity,
  COALESCE(ps.margin_pct, 0.0) AS rec_margin,
  p.sku AS rec_sku,
  p.product_name AS rec_name,
  SPLIT(p.bin_picking_number, ',')[OFFSET(0)] AS rec_netsuite_id
FROM category_copurchase cc
LEFT JOIN product_stats ps ON cc.rec_id = ps.product_id
JOIN `bc_native.bc_product` p ON cc.rec_id = p.product_id
ORDER BY cc.copurchase_count DESC
"""

def main():
    parser = argparse.ArgumentParser(description="Fetch enrichment data from BigQuery")
    parser.add_argument("--project", help="GCP Project ID", default=None)
    args = parser.parse_args()
    
    try:
        client = BigQueryClient(project_id=args.project)
        print(f"✅ Connected to BigQuery (Project: {client.project_id})")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return 1

    # 1. Fetch Item-Item
    print("\nFetching Item-Item Co-occurrence...")
    df_item = client.run_query(QUERY_ITEM_ITEM)
    print(f"  Rows: {len(df_item)}")
    
    # 2. Fetch Category-Item
    print("\nFetching Category-Item Co-occurrence...")
    df_cat = client.run_query(QUERY_CATEGORY_ITEM)
    print(f"  Rows: {len(df_cat)}")

    # 3. Structure Data
    output_data = {
        "metadata": {
            "generated_at": str(import_datetime().now()),
            "source": "BigQuery"
        },
        "item_cooccurrence": df_item.to_dict(orient="records"),
        "category_cooccurrence": df_cat.to_dict(orient="records")
    }

    # 4. Save
    output_path = Path("data/enrichment_data.json")
    output_path.parent.mkdir(exist_ok=True, parents=True)
    
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2, default=str)
        
    print(f"\n✅ Saved enrichment data to {output_path}")
    
    return 0

def import_datetime():
    from datetime import datetime
    return datetime

if __name__ == "__main__":
    sys.exit(main())