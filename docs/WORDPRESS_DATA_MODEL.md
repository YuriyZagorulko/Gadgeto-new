# WordPress / WooCommerce Data Model (from the backup)

Source: `/home/yuri/Desktop/my/temp/tempFiles/myWPAdmin.2026-08-21_20-56-42.tar`
→ `db/myWPAdmin_84048/myWPAdmin_84048.mysql.sql.zst` (MariaDB 11.4.9 dump, `wp_` prefix)
and `web/gadgeto.com.ua/domain_data.tar.zst` (public_html).

This document describes the **actual schema/data** as read from the dump so the
migration can be planned without guessing. All numbers were obtained by parsing the
dump directly (2026-08-22).

---

## 1. Versions

| Component | Version | Evidence |
|---|---|---|
| WordPress | 7.1 | `public_html/wp-includes/version.php` → `$wp_version = '7.1'` |
| WooCommerce | 10.9.1 | `wp_options.woocommerce_version` / `woocommerce_db_version` |
| MariaDB | 11.4.9 | dump header |
| Theme | Astra + `astra-custom` child | `wp-content/themes/` |

## 2. Table inventory (prefix `wp_`)

Core WP: `posts`, `postmeta`, `comments`, `commentmeta`, `terms`, `term_taxonomy`,
`term_relationships`, `termmeta`, `users`, `usermeta`, `options`, `links`.

WooCommerce classic: `woocommerce_sessions`, `woocommerce_api_keys`,
`woocommerce_attribute_taxonomies`, `woocommerce_downloadable_product_permissions`,
`woocommerce_order_items`, `woocommerce_order_itemmeta`, `woocommerce_tax_rates*`,
`woocommerce_shipping_zones*`, `woocommerce_payment_token(s|meta)`, `woocommerce_log`.

WooCommerce HPOS/analytics: `wc_orders`, `wc_orders_meta`, `wc_order_addresses`,
`wc_order_operational_data`, `wc_order_stats`, `wc_order_product_lookup`,
`wc_order_tax_lookup`, `wc_order_coupon_lookup`, `wc_customer_lookup`,
`wc_category_lookup`, `wc_product_meta_lookup`, `wc_product_attributes_lookup`,
`wc_product_download_directories`, `wc_reserved_stock`, `wc_rate_limits`,
`wc_webhooks`, `wc_admin_notes*`, `wc_admin_note_actions`.

Plugins:
- `actionscheduler_*` (Action Scheduler)
- `gla_*` (Google Listings & Ads)
- `woof*` (`woof_sd`, `woof_sd_presets`, `woof_query_cache` — HUSKY/WOOF)
- `yoast_*` (`yoast_indexable`, `yoast_indexable_hierarchy`, `yoast_migrations`,
  `yoast_primary_term`, `yoast_seo_links`, `yoast_expiring_store`)
- `pmxi_*` (WP All Import)
- `woobe_*` (WOOBE bulk editor), `tinvwl_*` (wishlist), `wpmailsmtp_*` (mail)
- `eb_*`, `e_events` (blocks / Elementor), `user_registration_sessions`,
  `wpforms_*`, `sm_*`

## 3. Key core tables (verified `CREATE TABLE`)

`wp_posts`: `ID, post_author, post_date, post_date_gmt, post_content, post_title,
post_excerpt, post_status, comment_status, ping_status, post_password, post_name,
to_ping, pinged, post_modified, post_modified_gmt, post_content_filtered,
post_parent, guid, menu_order, post_type, post_mime_type, comment_count`.

`wp_postmeta`: `meta_id, post_id, meta_key, meta_value` (LONGTEXT).

`wp_terms`: `term_id, name, slug, term_group`.
`wp_term_taxonomy`: `term_taxonomy_id, term_id, taxonomy, description, parent, count`.
`wp_term_relationships`: `object_id, term_taxonomy_id, term_order`.
`wp_termmeta`: `meta_id, term_id, meta_key, meta_value`.

`wp_woocommerce_attribute_taxonomies`: `attribute_id, attribute_name,
attribute_label, attribute_type, attribute_orderby, attribute_public`
(type=`select` in all observed rows; `public=1`).

### HPOS orders

`wc_orders`: `id, status, currency, type, tax_amount, total_amount, customer_id,
billing_email, date_created_gmt, date_updated_gmt, parent_order_id, payment_method,
payment_method_title, transaction_id, ip_address, user_agent, customer_note`.

`wc_order_addresses`: `id, order_id, address_type(billing|shipping), first_name,
last_name, company, address_1, address_2, city, state, postcode, country, email, phone`.

`wc_order_operational_data`: `order_id, created_via, woocommerce_version,
prices_include_tax, coupon_usages_are_counted, download_permission_granted,
cart_hash, new_order_email_sent, order_key, order_stock_reduced, date_paid_gmt,
date_completed_gmt, shipping_tax_amount, shipping_total_amount,
discount_tax_amount, discount_total_amount, recorded_sales`.

`wc_orders_meta`: `id, order_id, meta_key, meta_value` (attribution, NP and LiqPay
details — see below).

`woocommerce_order_items`: `order_item_id, order_item_name, order_item_type
(line_item|shipping|fee|coupon|tax), order_id`. `woocommerce_order_itemmeta`:
`order_item_id, meta_key, meta_value` (product_id, qty, subtotal, total,
`_method_id` etc. for shipping).

## 4. Category model

Categories: `taxonomy='product_cat'` (188 terms) with `parent` FK within the same
taxonomy, `description` (SEO text), `count` (cached product count). Category-meta
stores images. The canonical JSON used by the importer is `woocommerce_categories.json`
(id, parent_id, name, slug, count, path).

There are ~9-10 categories existing both in-tree and as orphans at root
(parent=0 + same name deeper) — a known legacy artifact (see `CURRENT_SYSTEM.md §7`).
The category-filter plugin config references both variants (URL-encoded slugs).
## 5. Attribute model

- `wp_woocommerce_attribute_taxonomies` — the declarative attribute list
  (196 used; AUTO_INCREMENT=215, ~19 deleted later).
- Each `pa_*` taxonomy holds its values as terms (≈4,000+ values total).
- Product→attribute assignments: (a) `_product_attributes` serialized meta AND
  (b) `term_relationships` to `pa_*` terms.
- `product_visibility` taxonomy (featured, exclude-from-catalog, …).
- `product_brand` (51 terms) — brand taxonomy used by WOOF filters and by the import
  CSV column `Бренди`.
- `product_type` (simple, grouped, variable, external).

## 6. Product fields observed in meta

Typical `_` meta seen: `_sku`, `_regular_price`, `_sale_price`, `_price`,
`_stock_status`, `_stock`, `_manage_stock`, `_tax_status`, `_tax_class`, `_weight`,
`_length`, `_width`, `_height`, `_thumbnail_id`, `_product_image_gallery`,
`_product_attributes` (serialized), `_visibility`, `supplier_slug`,
`supplier_sku`, `_wp_desired_post_slug`, Yoast (`_yoast_wpseo_title`,
`_yoast_wpseo_metadesc`, `_yoast_wpseo_focuskw`), `wc_gla_*` (Google), plus
Woolentor/ShopEngine/Astra cosmetic meta.

Images: attachments (`post_type=attachment`, 16,300), featured image via
`_thumbnail_id`, gallery via `_product_image_gallery`; CSV `Зображення` column
carries full URLs (wp-upload or supplier origin).

## 7. Users & accounts

`wp_users` (6): admin `GadgetoMaster`, a few `customer` test accounts.
`wp_usermeta` stores `wp_capabilities`; `user-registration` plugin tables exist.
→ Migration: create fresh accounts (no hash migration).

## 8. Order/checkout data (what the new store must reproduce)

- Per-order NP meta (in `wc_orders_meta`): `mrkv_ua_shipping_nova-poshta_city`,
  `_city_ref`, `_warehouse`, `_warehouse_ref`, `_warehouse_number`,
  `_mrkv_ua_shipping_nova-poshta_area_name`, … plus billing/shipping address rows
  (branch text + branch number in postcode).
- **Payment data**: `payment_method` = `morkva-liqpay` | `morkva-monopay` | `cod` |
  `bacs` … LiqPay plugin writes `_mrkv_liqpay_*` meta (order id, amount, card mask,
  commission).
- `cod`/`bacs` orders are stored the same way (no tokens).

## 9. Shipping & payments configuration

(in `wp_options`; sensitive values redacted)
- `woocommerce_morkva-liqpay_settings` — enabled=yes, test_mode=yes
- `woocommerce_morkva-monopay_settings` — enabled=no
- One shipping zone "Ukraine"; methods `mrkv_ua_shipping_nova-poshta(-address,-poshtamat)`;
  free/fixed-rate config (`enable_fix_cost=yes`, `fix_cost_total=0`).
- `woocommerce_attribute_lookup_enabled=yes`, `woocommerce_hpos_fts_index_enabled=no`.

## 10. Search / SEO / filter plugin data (to be replaced)

- HUSKY/WOOF options group (`woof*`).
- `woof_by_category_settings` — the 187 category-filter assignments
  (see `DATA_MAPPING.md §4`).
- Yoast: `wp_yoast_indexable` (27,603 rows), `wpseo_*` options,
  `wpseo_taxonomy_meta` (per-category SEO).
- `filter_export/` JSON trio produced by `export_filters_data.php`.

## 11. Mapping → new PostgreSQL schema (summary)

`wp_posts(product)` → `products`; `_sku` → `sku`; `_regular_price` → `price`;
`_sale_price` → `old_price`; `_stock_status` → stock; `post_title` → `title`;
`post_content`/`post_excerpt` → description / short_description;
`_thumbnail_id`+gallery → `product_images`; `term_relationships(product_cat)` →
`product_categories`; `pa_*` → `product_attributes`; `product_brand` → brand link;
`supplier_slug` + `supplier_sku` → supplier references; `_yoast_*` → SEO columns;
`wp_woocommerce_attribute_taxonomies` → `attributes`; `wc_orders` → `orders`.
Everything else (legacy plugin data, lookups, sessions) is ignored.

## 12. Known unknowns

- Attribute-term URL base — **UNKNOWN — REQUIRES VERIFICATION**.
- Whether `wp_woocommerce_sessions` contains meaningful cart data — assumed not.
- Whether category duplicates carry other references — **UNKNOWN — REQUIRES
  VERIFICATION**.
- Active plugin list at runtime (in `wp_options.active_plugins`; not parsed yet).