# Database Design — PostgreSQL

For the complete audit-derived schema, see `docs/DATABASE.md`.

## Major Entities

### Catalog

| Table | Description |
|-------|-------------|
| `categories` | Hierarchical product categories with SEO fields, `legacy_id` linking to WooCommerce |
| `category_closure` | Transitive closure for fast tree queries (ancestor/descendant) |
| `attributes` | Product attributes (slug, name, type, is_filterable) |
| `attribute_values` | Predefined attribute values (allowlist model) |
| `products` | Core product entity; unique `sku`, `(supplier_id, supplier_sku)` for import idempotency |
| `product_images` | Product images with URL, path, checksum, sort order |
| `product_categories` | M2M: product ↔ category |
| `product_attributes` | M2M: product ↔ attribute + value (or text fallback) |
| `product_related` | Related products |

### Suppliers & Mappings

| Table | Description |
|-------|-------------|
| `suppliers` | System suppliers (itlink, dclink, manual) |
| `supplier_categories` | Supplier category names (verbatim) |
| `category_mappings` | Maps supplier category → internal category |
| `supplier_attributes` | Supplier attribute names (verbatim) |
| `attribute_mappings` | Maps supplier attribute → internal attribute |
| `supplier_attribute_values` | Supplier attribute values (verbatim) |
| `attribute_value_mappings` | Maps supplier value → internal value (NULL = drop) |
| `supplier_products` | Per-supplier product ledger with raw JSON snapshots |
| `mapping_sources` | Archived reference JSON mapping files (audit trail) |

### Cart & Orders

| Table | Description |
|-------|-------------|
| `carts` / `cart_items` | Session-based and user-based carts |
| `orders` | Order with buyer details, status, totals |
| `order_items` | Line items within an order |
| `order_addresses` | Shipping addresses (Nova Poshta snapshots) |
| `payments` | Payment transactions (LiqPay callbacks) |
| `order_events` | Order state change log |

### Users & Auth

| Table | Description |
|-------|-------------|
| `users` | Users with role (admin/staff/customer), email verification |
| `sessions` | Session tokens (hashed) with expiry |
| `password_reset_tokens` / `email_verifications` | Hashed tokens with expiry |

### Other

| Table | Description |
|-------|-------------|
| `category_filters` | Per-category filter configuration (attribute_id, position) |
| `import_jobs` | Import run tracking with status, stats, error details |
| `import_logs` | Per-import log messages |
| `settings` | Key-value configuration (with is_secret flag) |
| `url_aliases` | Legacy URL redirects (301 plan) |

## Key Design Decisions

1. **Supplier-scoped mapping rows** — each source string becomes a per-supplier verbatim row.
2. **NULL-target value mapping = "remove"** — allows dropping specific values.
3. **Idempotency** — `UNIQUE(supplier_id, supplier_sku)` for safe re-imports.
4. **URL safety** — unique product slugs + `url_aliases` table for WC redirects.
5. **NP references snapshotted** into orders for historical validity.
6. **No global filter list** — filters are per-category via `category_filters` join table.

## Indexing

- GIN indexes on `products.search_vector` (FTS) and `lower(name)` (pg_trgm)
- Unique constraints on slugs, SKU, and `(supplier_id, supplier_sku)`
- B-tree indexes on foreign keys and commonly filtered columns (brand, price, is_active, category)

## Migration Notes

- All migrations idempotent; `alembic upgrade head` from an empty DB must work cleanly.
- `mapping_sources` archived at bootstrap with sha256 as audit trail.

## Related Documentation

- `docs/DATABASE.md` — complete audit-driven schema with detailed column descriptions
- `docs/DATA_MAPPING.md` — mapping data audit and migration plan
- `docs/WORDPRESS_DATA_MODEL.md` — legacy WordPress data model reference