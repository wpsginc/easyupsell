# PRE Data Source: BigQuery

## Overview

Replace slow BigCommerce API calls with fast BigQuery queries. Data is already synced (near real-time) to `bc_native` dataset.

**Current state:** ~123,607 orders, latest: 2026-02-04 (today)

---

## Connection

```python
from google.cloud import bigquery

client = bigquery.Client(project="aegi-switmer")  # or whatever the project ID is

def run_query(sql):
    """Execute BQ query and return DataFrame."""
    return client.query(sql).to_dataframe()
```

---

## Key Tables

| Table | Purpose |
|-------|---------|
| `bc_native.bc_order` | Order metadata, dates |
| `bc_native.bc_order_line_items` | Line items - copurchase analysis |
| `bc_native.bc_product` | Product details, SKU, **BPN (NetSuite ID)** |
| `bc_native.bc_product_category` | Category mappings |

---

## Critical: NetSuite ID Extraction

The NetSuite Internal ID is stored in `bc_product.bin_picking_number` (BPN field).
It's comma-delimited; **NS ID is always the first value**.

```python
def extract_netsuite_id(bpn: str) -> str:
    """Extract NetSuite Internal ID from BPN field."""
    if bpn:
        return bpn.split(",")[0].strip()
    return None
```

---

## Query 1: Copurchase Analysis

Products frequently bought together in the same order.

```sql
SELECT 
  a.product_id AS source_product_id,
  b.product_id AS copurchased_product_id,
  COUNT(DISTINCT a.order_id) AS copurchase_count
FROM `bc_native.bc_order_line_items` a
JOIN `bc_native.bc_order_line_items` b 
  ON a.order_id = b.order_id 
  AND a.product_id != b.product_id
GROUP BY 1, 2
HAVING copurchase_count >= 3
ORDER BY copurchase_count DESC
```

---

## Query 2: Product Sales Velocity (Last 90 Days)

```sql
SELECT 
  li.product_id,
  p.sku,
  p.product_name,
  SPLIT(p.bin_picking_number, ',')[OFFSET(0)] AS netsuite_id,
  COUNT(DISTINCT li.order_id) AS order_count,
  SUM(li.quantity) AS units_sold,
  SUM(li.price_ex_tax) AS revenue
FROM `bc_native.bc_order_line_items` li
JOIN `bc_native.bc_order` o ON li.order_id = o.order_id
JOIN `bc_native.bc_product` p ON li.product_id = p.product_id
WHERE o.order_created_date_time >= DATETIME_SUB(CURRENT_DATETIME(), INTERVAL 90 DAY)
GROUP BY 1, 2, 3, 4
ORDER BY units_sold DESC
```

---

## Query 3: Margin Data

`bc_order_line_items` has both `product_price` and `base_cost_price`.

```sql
SELECT 
  li.product_id,
  p.sku,
  AVG(li.product_price) AS avg_price,
  AVG(li.base_cost_price) AS avg_cost,
  AVG(SAFE_DIVIDE(li.product_price - li.base_cost_price, li.product_price)) AS avg_margin_pct
FROM `bc_native.bc_order_line_items` li
JOIN `bc_native.bc_product` p ON li.product_id = p.product_id
WHERE li.base_cost_price > 0  -- exclude items without cost data
GROUP BY 1, 2
```

---

## Query 4: Enriched Copurchase with Context

Combine copurchase + velocity + margin in one query:

```sql
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
  c.rec_id,
  c.copurchase_count,
  ps.units_90d AS rec_velocity,
  ps.margin_pct AS rec_margin,
  p.sku AS rec_sku,
  p.product_name AS rec_name,
  SPLIT(p.bin_picking_number, ',')[OFFSET(0)] AS rec_netsuite_id
FROM copurchase c
JOIN product_stats ps ON c.rec_id = ps.product_id
JOIN `bc_native.bc_product` p ON c.rec_id = p.product_id
ORDER BY c.copurchase_count DESC
LIMIT 5000
```

---

## Refactor Steps

1. Create `src/bigquery_client.py` with connection and query functions
2. Replace `BigCommerceClient.get_orders()` calls with BQ queries
3. Add `netsuite_id` to all output (extracted from BPN)
4. Include `copurchase_count`, `margin_pct`, `velocity` in candidate data
5. Pass enriched context to LLM validation

---

## Performance Comparison

| Method | Orders | Time |
|--------|--------|------|
| BC API | 8,000 | ~30+ minutes |
| BigQuery | 123,607 | ~5 seconds |

