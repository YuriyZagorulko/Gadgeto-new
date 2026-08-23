"""007: Product editor support - sale scheduling, extended inventory, reviews, variations.

Additive-only migration: new nullable/defaulted columns and two new tables.
No existing column is modified or dropped; existing product data stays intact.

Applied manually (psql) - see project convention: migrations are applied to the
host database; this file documents the schema for fresh environments.
"""
revision: str = '007_product_editor'
down_revision: str = '006_carts_imports'

UPGRADE_SQL = """
-- Extended pricing/inventory fields for the admin product editor
ALTER TABLE products
    ADD COLUMN IF NOT EXISTS sale_start_at TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS sale_end_at TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS barcode VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS low_stock_threshold INTEGER NULL,
    ADD COLUMN IF NOT EXISTS manage_stock BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS allow_backorders BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS purchase_cost INTEGER NULL,
    ADD COLUMN IF NOT EXISTS warehouse VARCHAR(255) NULL;

-- Customer reviews managed from the admin panel
CREATE TABLE IF NOT EXISTS product_reviews (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    author_name VARCHAR(255) NOT NULL,
    author_email VARCHAR(255) NULL,
    rating INTEGER NOT NULL DEFAULT 5 CHECK (rating BETWEEN 1 AND 5),
    content TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'published',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_product_reviews_product ON product_reviews(product_id);

-- Variable-product combinations (attribute_id -> value text map in attrs_json)
CREATE TABLE IF NOT EXISTS product_variations (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sku VARCHAR(255) NULL,
    attrs_json TEXT NOT NULL DEFAULT '{}',
    price INTEGER NULL,
    sale_price INTEGER NULL,
    stock_qty INTEGER NOT NULL DEFAULT 0,
    stock_status VARCHAR(50) NOT NULL DEFAULT 'in_stock',
    image_url VARCHAR(1000) NULL,
    barcode VARCHAR(64) NULL,
    supplier_sku VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_product_variations_product ON product_variations(product_id);
"""
