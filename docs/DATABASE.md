# Database Design — PostgreSQL

Status: **proposal derived from the audit**. Implemented as Alembic migrations;
no manual production schema changes allowed outside migrations.

The model is based on the mapping files and the WordPress data model — it is
**not** a 1:1 copy of `wp_posts`/`wp_postmeta`.

---

## 1. Catalog entities

### categories
- id (identity), legacy_id (WC term_id, nullable), parent_id (self FK),
  name, slug (unique), description, seo_title, seo_description,
  seo_focus_keyphrase, image, is_active, sort_order, created_at, updated_at.
- `legacy_id` links `CategoriesSEO_Final.json` (187 rows) by WC id.
- `slug` preserved byte-for-byte (incl. percent-encoded Cyrillic orphans — the
  canonical uniqueness handled via `url_aliases`).

### category_closure
- ancestor_id, descendant_id, path_length — transitive closure for fast tree
  queries (category + children filters).

### attributes
- slug (unique, e.g. `diagonal-ekranu`), name («Діагональ екрану»), type
  (`select`/`text`/`number`), is_global, is_filterable, legacy_value_set json,
  created_at.

### attribute_values
- attribute_id, value (uk), slug, sort, is_active. UNIQUE(attribute_id, value).

### products
- id, legacy_id (WC post ID), supplier_id (nullable), supplier_sku (nullable),
  sku (nullable, unique), name, slug (unique), description, short_description,
  brand_id (nullable FK), price, old_price, currency (UAH), stock_status,
  stock_qty, is_active, is_visible, status (import-sourced/manual/archived),
  meta_json (raw JSON from import), search_vector (tsvector), created_at,
  updated_at, imported_at.
- UNIQUE(supplier_id, supplier_sku) — idempotency back-match for imports.

### product_images
- product_id, url, path, alt, sort_order, is_primary, checksum.

### product_categories
- product_id, category_id (M2M).

### product_attributes
- product_id, attribute_id, attribute_value_id (nullable), value_text (fallback).
  UNIQUE(product_id, attribute_id).

### product_related
- product_id, related_product_id.

## 2. Suppliers & mappings

- **suppliers** — code (`itlink`,`dclink`,`manual`), name, config_json, enabled.
- **supplier_categories** — supplier_id, external_id (nullable), supplier_name
  (verbatim), is_removed. UNIQUE(supplier_id, supplier_name).
- **category_mappings** — supplier_category_id → category_id, is_active,
  created_by_user_id, created_at, updated_at.
- **supplier_attributes** — supplier_id, supplier_name (verbatim), is_removed.
  UNIQUE(supplier_id, supplier_name).
- **attribute_mappings** — supplier_attribute_id → attribute_id, is_active.
- **supplier_attribute_values** — supplier_attribute_id, supplier_value
  (verbatim), is_removed. UNIQUE(supplier_attribute_id, supplier_value).
- **attribute_value_mappings** — supplier_attribute_value_id → attribute_value_id
  (NULL = drop), is_active. Preserves the legacy allowlist semantics.
- **supplier_products** — supplier_id, supplier_sku, product_id, raw_json,
  last_price, last_stock, last_seen_at, is_removed_from_feed.
  UNIQUE(supplier_id, supplier_sku).
- **mapping_sources** — file_name, sha256, content (json), archived_at
  (the reference JSON files, one row per file — audit trail).

## 3. Cart & orders

### carts / cart_items
- carts (UUID id, user_id nullable, session_token); cart_items (cart_id,
  product_id, qty). UNIQUE(cart_id, product_id).

### orders
- id, number (display), user_id (nullable for guests), buyer_name, email, phone,
  status (new/processing/paid/shipped/completed/cancelled), currency, subtotal,
  shipping_cost, discount, total, payment_method, shipping_method,
  customer_note, created_at, updated_at.
- order_items (order_id, product_id, product_snapshot_json, qty, price, total).
- shipping_addresses (order_id, city_name, city_ref, warehouse_name,
  warehouse_ref, warehouse_number, area_name, address, recipient_name, phone) —
  NovaPosta references snapshotted for historical validity.
- payments (order_id, payment_id, liqpay_order_id, status, amount, currency,
  card_mask, card_type, raw_callback_json, created_at, updated_at).
- order_events (order_id, event, actor, payload, created_at).
## 4. Users / auth / filters / jobs

- **users** — id, email (unique), password_hash, full_name, phone, role
  (admin/staff/customer), status, email_verified_at, created_at, updated_at.
- **sessions** — token_hash, user_id, expires_at, ip, user_agent.
- **password_reset_tokens / email_verifications** — token_hash, expires_at, used_at.
- **category_filters** — category_id (NULL = global default), attribute_id,
  position, enabled. UNIQUE(category_id, attribute_id).
  (Legacy `woof_by_category_settings` global filters `[product_brand,
  product_cat]` become the NULL-category default set.)
- **import_jobs** — id, supplier_id, import_type, status
  (queued/running/succeeded/failed/aborted), started_at, finished_at,
  stats_json (created/updated/skipped/failed), error_details_json,
  triggered_by_user_id, created_at.
- **import_logs** — job_id, level, message, item_ref (sku/name/category),
  created_at.
- **settings** — key, value, is_secret.
- **url_aliases** — old_url, new_url, http_status, created_at (301 plan).

## 5. Key design decisions (audit-derived)

1. **Supplier-scoped mapping rows** — legacy JSON carries no supplier provenance,
   so each source string becomes a per-supplier verbatim row; the admin edits DB
   rows, never JSON files.
2. **NULL-target value mapping = "remove"** — preserves the allowlist semantics of
   `attribute_value_mapping_final.json`; `is_removed` flags implement
   `attribute_remove.json` / `attribute_value_to_remove.json`.
3. **Idempotency** — `UNIQUE(supplier_id, supplier_sku)`; per-supplier raw ledger
   (`supplier_products.raw_json`) keeps a snapshot per feed run.
4. **URL safety** — unique product slugs, plus a `url_aliases` table for WC URL
   redirects (`/shop/{slug}/`, `/product-category/{cat}/`).
5. **Images** — `product_images` with URL + local path; media physically moved from
   `wp-content/uploads/{2025,2026}`.
6. **NP references snapshotted** into orders (`city_ref`/`warehouse_ref`), so
   historical orders remain valid even if NP data changes.

## 6. Indexing & search

- `products`: btree(id), unique(slug), unique(sku), unique(supplier_id,
  supplier_sku), gin(search_vector), gin(lower(name) gist_trgm_ops),
  btree(brand_id), btree(is_active), btree(price).
- `product_categories`: PK(product_id, category_id); index category_id.
- `product_attributes`: PK(product_id, attribute_id); index attribute_value_id.
- FTS: `search_vector` filled at import/migration time (name, brand, sku,
  supplier_sku, short description) with `simple` config; uk/ru text via
  `simple` + substring (pg_trgm) since the catalog is polyglot.

## 7. Migration notes

- All migrations idempotent; `alembic upgrade head` from an empty DB must work
  cleanly (release gate).
- `mapping_sources` archived at bootstrap with sha256 as a reversible audit trail.

## 8. Open items (finalize during implementation)

- `slug` uniqueness strategy for duplicate product names (WC suffixes with `-2`;
  the importer never produced collisions — verify at migration).
- Whether `products.sku` should allow NULL for the ~20 legacy products without SKU —
  yes, keep nullable.
- `import_jobs` stats as columns vs a separate counters table.
- FKs from `products.supplier_id` nullable but enforced when set.