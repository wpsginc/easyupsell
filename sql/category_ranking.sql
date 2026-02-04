-- Category Ranking & Selection Query
--
-- Logic:
-- 1. Aggregate metrics (Revenue, Qty, Order Count) per Category per Source Item
-- 2. Rank categories by Revenue desc
-- 3. Select top categories (limit 5 per source)
-- 4. Within selected categories, aggregate co-purchase items
-- 5. Sort items by co-purchase count desc
-- 6. Extract NetSuite ID from bin_picking_number

WITH CategoryMetrics AS (
  SELECT
    oli_source.product_id AS source_item_id,
    pc.category_id,
    c.name AS category_name,
    COUNT(DISTINCT oli_rec.order_id) AS order_count,
    SUM(oli_rec.quantity) AS total_quantity,
    SUM(oli_rec.total_inc_tax) AS total_revenue
  FROM `bc_native.bc_order_line_items` oli_source
  JOIN `bc_native.bc_order_line_items` oli_rec ON oli_source.order_id = oli_rec.order_id
  JOIN `bc_native.bc_product_category` pc ON oli_rec.product_id = pc.product_id
  JOIN `bc_native.bc_category` c ON pc.category_id = c.id
  WHERE oli_source.product_id != oli_rec.product_id -- Exclude self
  GROUP BY 1, 2, 3
),

RankedCategories AS (
  SELECT
    *,
    RANK() OVER (PARTITION BY source_item_id ORDER BY total_revenue DESC) as category_rank
  FROM CategoryMetrics
),

TopCategories AS (
  SELECT * FROM RankedCategories WHERE category_rank <= 5
),

ItemRanking AS (
  SELECT
    tc.source_item_id,
    tc.category_id,
    tc.category_name,
    tc.total_revenue as category_revenue,
    p.product_id as rec_id,
    p.sku as rec_sku,
    p.product_name as rec_name,
    p.bin_picking_number as rec_bpn,
    COUNT(DISTINCT oli.order_id) as copurchase_count
  FROM TopCategories tc
  JOIN `bc_native.bc_product_category` pc ON tc.category_id = pc.category_id
  JOIN `bc_native.bc_product` p ON pc.product_id = p.product_id
  JOIN `bc_native.bc_order_line_items` oli ON p.product_id = oli.product_id
  WHERE p.inventory_level > 0 -- Basic availability check
  GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
)

SELECT
  source_item_id,
  category_id,
  category_name,
  category_revenue,
  rec_id,
  rec_sku,
  rec_name,
  rec_bpn,
  copurchase_count
FROM ItemRanking
ORDER BY source_item_id, category_revenue DESC, copurchase_count DESC