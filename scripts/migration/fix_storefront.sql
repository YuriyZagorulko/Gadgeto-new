-- Set Uncategorized as inactive
UPDATE categories SET is_active = false WHERE slug = 'uncategorized';

-- Set primary image for first image of each product
WITH ranked AS (
  SELECT id, product_id, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY sort_order, id) as rn
  FROM product_images
)
UPDATE product_images pi
SET is_primary = true
FROM ranked r
WHERE pi.id = r.id AND r.rn = 1;
