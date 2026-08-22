# Migration Sources - Authoritative Data Sources

## Overview
This document defines which source is authoritative for each entity during migration from WordPress/WooCommerce to the new Gadgeto PostgreSQL schema.

## Source Files

| Source | Location | Format | Size |
|---|---|---|---|
| WooCommerce CSV | `gedgeto/catalog/woocommerce_export.csv` | CSV (168 cols) | 22,505 products |
| Final mapping files | `gedgeto/catalog/final data mapping/` | JSON | 5 files |
| WordPress DB dump | `tempFiles/myWPAdmin.../db_dump.sql` | MariaDB SQL | ~280 MB |
| WC categories | `final data mapping/data_from_server/woocommerce_categories.json` | JSON | 188 cats |
| SEO data | `tempFiles/CategoriesSEO_Final.json` | JSON | 187 cats |
| Archive (web files) | `tempFiles/myWPAdmin...tar` | tar.zst | 5.4 GB web data |

## Entity → Source Matrix

| Entity | Primary Source | Secondary Source | Reason |
|---|---|---|---|
| Products | WooCommerce CSV | WP DB (SEO meta) | CSV already denormalized, production snapshot |
| SKU | WooCommerce CSV | — | Column "Артикул" |
| Name | WooCommerce CSV | — | Column "Назва" |
| Slug | WP DB post_name | CSV (generate if missing) | CSV has no direct slug column |
| Price | WooCommerce CSV | — | Columns "Звичайна цна" / "Цна зі знижкою" |
| Stock | WooCommerce CSV | — | Columns "В наявності?" / "Запаси" |
| Category Path | WooCommerce CSV | — | Column "Категорі" (denormalized path) |
| Categories | WC categories JSON + final mapping | WooCommerce CSV | Hierarchy from WC cats JSON, mappings from final mapping |
| Images | WooCommerce CSV | WP DB uploads | CSV has URLs; blog file paths in web archive |
| Attributes | WooCommerce CSV | final mapping files | CSV has per-product attribute columns |
| Attribute Mapping | `attributes_final.json` | — | Authoritative mapping file |
| Attribute Values | `attribute_value_mapping_final.json` | — | Authoritative value mapping |
| Attribute Removal | `attribute_remove.json` | — | Authoritative remove rules |
| Brands | WooCommerce CSV | WP product_brand taxonomy | Column "Бренди" |
| Supplier | WooCommerce CSV | — | Column "Мета: supplier_slug" |
| SEO Titles | WooCommerce CSV | CategoriesSEO_Final.json | CSV has Yoast SEO columns |
| Users | WP DB | — | 5 users, migration optional |
| Orders | WP DB | — | 11 orders, mostly test data |
| URL Structure | WP DB | WooCommerce URL patterns | Preserve slugs for 301 redirects |

## Images

- 22,480 products have images (99.9%)
- All image URLs are WordPress-hosted (`wp-content/uploads/2025/`, `wp-content/uploads/2026/`)
- Images are stored in the `domain_data.tar.zst` archive (5.4 GB)- No imediate download required - preserve URLs for lazy migration

## Notes

- The WoCommerce CSV is the production snapshot and reflects the true catalog state
- The SQL dump is used selectively for slugs, SEO, and data missing from CSV
- Final mapping files are the AUTHORITATIVE source for all mapping/transformation rules
- Users and orders are NOT migrated automatically - requires explicit review
