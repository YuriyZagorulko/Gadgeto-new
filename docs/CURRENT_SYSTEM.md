# Current System — Audit Report

Based on **actual inspection** of:
- `/home/yuri/Desktop/my/projects/gedgeto/catalog/` (importer — see `IMPORT_SYSTEM.md`)
- `/home/yuri/Desktop/my/temp/tempFiles/myWPAdmin.2026-08-21_20-56-42.tar` (WordPress backup)
- `/home/yuri/Desktop/my/projects/gedgeto/wp-content/` (working copy of the live site's plugins/themes)
- Live checks of `gadgeto.com.ua` (robots.txt, sitemap)

Last audit date: 2026-08-22.

---

## 1. Overview

The production store runs **WordPress 7.1 + WooCommerce 10.9.1** on a **HestiaCP**
server. The domain is **gadgeto.com.ua** (currently served over HTTP — `siteurl`/`home`
are `http://gadgeto.com.ua`). It is a computer/electronics store selling in Ukraine
(UAH), shipping via Nova Poshta, paying via LiqPay (test mode) and cash-on-delivery.

Nothing in this section has been modified. All paths below are reference sources.

## 2. Environment & store settings (from `wp_options`)

| Key | Value |
|---|---|
| `siteurl` / `home` | `http://gadgeto.com.ua` |
| `permalink_structure` | `/%postname%/` |
| WooCommerce permalinks | product base `/shop`, category base `/product-category` |
| `woocommerce_version` / `woocommerce_db_version` | 10.9.1 (initial install 10.1.2, Dec 2025) |
| WordPress version (backup) | 7.1 |
| MariaDB (dump server) | 11.4.9 |
| Currency | UAH, `₴` with space, thousands `' '`, decimals `,`, 2 |
| Store address | вул. Лебедина 63, Дніпро, 49000, UA |
| Taxes | disabled (`woocommerce_calc_taxes=no`) |
| Coupons | disabled |
| Orders storage | **HPOS enabled** (`woocommerce_custom_orders_table_enabled=yes`) |
| Shop page | ID 125 |

## 3. Data volumes (inspected directly in the SQL dump)

| Entity | Count | Notes |
|---|---|---|
| Products (`post_type=product`) | **22,504** | publish 14,694 · private 7,809 · trash 1 |
| Product variations | 2 | ~99.99 % simple products |
| Attachments (images) | 16,300 | downloaded via WC import |
| Pages | 19 | incl. shop (125), account, checkout, cart |
| Product categories (`product_cat`) | 188 | incl. ~9 orphaned duplicates at root (see §7) |
| Brand taxonomy terms (`product_brand`) | 51 | custom taxonomy «Бренди» |
| Global WooCommerce attributes | 196 | `wp_woocommerce_attribute_taxonomies` (AUTO_INCREMENT=215 → ~19 deleted) |
| Terms total (`wp_terms`) | 5,188 | categories + attributes + attribute values + internal |
| Term relationships | 262,007 | incl. `pa_*` attribute assignments |
| Postmeta rows | 693,027 | incl. `_sku`, `_regular_price`, `_stock_status`, `supplier_slug`, `supplier_sku`, Yoast meta |
| `wp_wc_product_meta_lookup` | 22,508 | WC lookup table |
## 4. Products

Product model in WooCommerce: **`simple` products** (2 variations total). Each product
carries `_sku`, `_regular_price`, `_sale_price`, `_stock_status`, descriptions
(excerpt+content identical in the importer feed), `_thumbnail_id`/gallery, categories
via `product_cat`, attribute terms via `pa_*` taxonomies, and meta:

- `supplier_slug` — supplier identifier (`itlink` / `dclink` / `mine`)
- `supplier_sku` — the original supplier article (e.g. `FH-04` for SKU `ITL-FH-04`)
- `_yoast_wpseo_title`, `_yoast_wpseo_metadesc`, `_yoast_wpseo_focuskw` — generated SEO
- `_product_attributes` (serialized global attribute assignments for products)
- `_saleflash_text`, Woolentor stock meta, `ast-*` theme meta (add-ons, cosmetic)

Products are linked to categories via `term_relationships`; a product's category
assignment in the CSV is stored as a **full path string** (e.g.
`Комп'ютери > Комплектуючі > SSD-накопичувачі`).

Pricing (verified in code — see `IMPORT_SYSTEM.md` for details):
- **IT-Link:** feed price (UAH) × 1.30 (`USD_TO_UAH=1`, `MARKUP=1.3`); `rrp ≠ 0` becomes sale price.
- **DC-Link:** `price_uah` when present, else `price × 44.3`; tiered markup 1.20–1.50
  depending on price band. Final price is a whole UAH.

Stock: importer sets `В наявності?` = `1` for products present in the supplier feed
and `0` for products absent from the latest feed. There is no per-warehouse stock.

## 5. Categories

188 product categories in one hierarchical tree, with a handful of **orphaned
duplicate branches** (see §7). Slug examples (must be preserved for SEO):

```
Редакции (id 410, slug "computers")  → "Комп'ютери"           → 11,113 products
├── Комплектуючі (components)                                  → 2,618
├── Ноутбуки (laptops)                                        → 618
├── Периферія (peripherals)                                     → 3,293
│   ├── Миші (mice)                                            → 576
│   ├── Монітори (monitors)                                    → 249
│   └── Кабелі та перехідники (cables)                         → 1,053
├── Моноблоки (all-in-one-pcs)                                 → 44
└── Сервери (servers)                                          → 5
Мережеве обладнання (networking)   → 984    Телефонія (phones-tablets) → 4,001
Офісна техніка (printing-office)   → 1,000  Інше (other)             → 17
```

Slugs for Cyrillic category names are URL-encoded (e.g. `ssd-%d0%b…`), Latin slugs
are plain. Both must be handled in redirect planning.

## 6. Attributes

- **196 global attribute taxonomies** define the "internal" attribute names/labels
  (e.g. `pa_brand` / «Бренд», `pa_diagonal-ekranu` / «Діагональ екрану», `pa_kilkist` /
  «Кількість»). AUTO_INCREMENT=215 → ~19 attribute taxonomies were later deleted.
- Every attribute value is a `term` in its `pa_*` taxonomy (≈ 4,000+ values total).
- Imported attribute names are the **Ukrainian labels** produced by the mapping
  (e.g. «Діагональ екрану», «Тип накопичувача»); see `DATA_MAPPING.md`.
- Multi-valued products store values concatenated with ` | ` (WC CSV convention).

## 7. Data quality / integrity findings

1. **Orphaned duplicate categories.** Several categories exist twice — once in the
   canonical tree and once with `parent=0` (e.g. `3D-принтери` ids 5364/356,
   `IP-телефони` 5362/304, `PoE-інжектори` 5360/295, `Powerline` 5363/294,
   `USB-флеш-накопичувачі` 5361/74, `SSD-накопичувачі` 1890/…). Older importer
   versions created these. The category-filter plugin config references **both**
   variants (URL-encoded slugs for the orphans).
   → The new DB keeps ONE canonical tree; the orphan slugs remain as redirects.
2. **Small numeric skews** between `posts`, `lookup`, and the CSV export (see §3).
3. **Test/trash orders.** 11 of 12 HPOS orders are Trash (older tests incl. the
   "Shopengine preview product"), so the store has **no meaningful order history**
   to migrate (see `MIGRATION_PLAN.md`).
4. **Deleted attribute taxonomies** left residues in product metas.
5. **Brand data duplication**: `product_brand` taxonomy (51) vs the `Бренди`
   column in the CSV/feed — the two sources must be reconciled once.

## 8. Orders

Orders use **HPOS**: `wp_wc_orders`, `wp_wc_orders_meta`, `wp_wc_order_addresses`,
## 9. Users

6 rows in `wp_users`; roles: at least one `administrator` (`GadgetoMaster`) and
several `customer` test accounts. Passwords are WP phpass hashes — the new system
will NOT migrate password hashes; affected accounts are re-issued or re-created.

## 10. Payments (settings — sensitive values redacted)

- **LiqPay** (plugin `mrkv-liqpay-extended`, gateway id `morkva-liqpay`):
  `enabled: yes`, **`test_enabled: yes`** (test keys are configured; real values are
  **NOT** committed anywhere in this repo), `lang=uk`, paid-order status `processing`,
  `use_holds=no`, `hold_cancel_status=cancelled`, `national_cashback_*` (empty).
- **Monobank** (`mrkv-monobank-extended`, gateway `morkva-monopay`): `enabled: no`.
- Legacy gates: `cod` («Оплата при отриманні»), `bacs` («Банківський переказ»), `cheque`.

## 11. Shipping (NovaPosta)

One shipping zone "Ukraine" with methods in order:
`mrkv_ua_shipping_nova-poshta` (вівділення), `_address` (кур�єр на адресу),
`_poshtamat` (поштомат). Plugin settings include `enable_fix_cost=yes`,
`fix_cost_total=0` and a free-shipping notice text — i.e. the store configured
**no shipping charge** ("За тарифами перевезника"). Internal keys
`mrkv_api_fixed_np` / `mrkv_api_last_check_np` exist (values redacted).

## 12. Search & filtering

- **HUSKY Products Filter (WOOF)** — options group `woof*` present.
- **Custom plugin "Zagorulko Category Filters for HUSKY" v1.0.3**
  (source also at `/home/yuri/Desktop/my/projects/gedgeto/woof-by-category-custom/`):
  - option `woof_by_category_settings` — **187 entries**: `category` slug → list of
    filter taxonomies (the data source for category-specific filters).
  - option `woof_by_category_global_filters` — `["product_brand", "product_cat"]`
  - Example entry: `{ "category": "gps-trackers", "filters": ["pa_kolir","pa_radius-dii","pa_sumisnist"] }`.
    Most categories have an empty filter list (fallback to global filters).
- Server-side export `export_filters_data.php` → `filter_export/` (categories,
  attributes, `category_attribute_usage` — per-category attribute usage from products)

→ The new store will model **category ↔ filterable attribute** relationships directly
in PostgreSQL and let the admin edit them (see `DATABASE.md`).

## 13. SEO / URLs (current — must be preserved or 301’d)

- `robots.txt` (Yoast) → `https://gadgeto.com.ua/sitemap_index.xml`
- Sitemaps: 15× `product-sitemap*.xml` (~22k products), `product_cat-sitemap.xml`,
  `product_brand-sitemap.xml`, one `pa_*-sitemap.xml` per attribute, plus
  posts/pages/author.
- Product URL: `/shop/{slug}/`, slug is **percent-encoded Cyrillic** — keep 1:1.
- Category URL: `/product-category/{category_slug}/`.
- Attribute term URL: root `/{term-slug}/` — **UNKNOWN — REQUIRES VERIFICATION**.
- Product SEO meta (Yoast): title `… — купити в Україні | Gadgeto`, meta description,
  focus keyphrase — generated deterministically by `woocommerce_seo_generator.py`.
- Category SEO: `CategoriesSEO_Final.json` (187 cats: `seo_title`, `meta_description`,
  `focus_keyphrase`, `description` incl. FAQ block) imported via
  `import-category-seo.php` into `wpseo_taxonomy_meta`.

## 14. Admin / operational server tooling (legacy, not reused)

- `export_woocommerce_categories.php` — categories → JSON (used by both
  supplier importers to validate/resolve categories)
- `export_filters_data.php` — batched filter-usage export
- `import-category-seo.php` (WP-CLI `eval-file`) — imports CategoriesSEO_Final.json
- WP All Import plug-in present (currently the imports are done via built-in WC CSV importer)
- WP-CLI present in the backup

## 15. Risks identified for the new system

1. Slugs are URL-encoded Cyrillic — must be preserved byte-for-byte.
2. Category tree has orphan duplicates — the DB keeps ONE canonical tree + redirect map.
3. ~20 products have no stable SKU — they cannot be idempotently re-imported.
4. `supplier_slug=mine` (10 items) are hand-made products — migrate as-is, owned by "manual".
5. No meaningful order history — do not invest in mass order migration.
6. Legacy plugins/caches/transients (LiteSpeed, Jetpack, action-scheduler, $woocommerce_sessions) must NOT be migrated.

## 16. Next steps

- Finalize the PostgreSQL schema and mapping model (`DATABASE.md`).
- Design the import pipeline (FastAPI + Celery, `IMPORT_SYSTEM.md`).
- Define migration/re-import runs (`MIGRATION_PLAN.md`).
- Keep the WordPress site untouched until the new store is validated.
`wp_wc_order_operational_data` (+ legacy `wp_woocommerce_order_items/itemmeta`).
Confirmed order fields used by the store:

- status: `wc-processing`, `trash` (old tests)
- payment methods: `cod`, `bacs`, `morkva-liqpay`, `morkva-monopay`
- shipping method: `Нова Пошта, на відділення` (`mrkv_ua_shipping_nova-poshta`)
- NP data per order (in `wp_wc_order_addresses` + order meta):
  - `city` + `mrkv_ua_shipping_nova-poshta_city_ref`
  - `address_1` = full NP branch text («Відділення №9 … адреса»)
  - `postcode` = NP branch number (e.g. `9`)
  - `mrkv_ua_shipping_nova-poshta_warehouse_ref`, `_warehouse_number`,
    `_mrkv_ua_shipping_nova-poshta_area_name` (region)
- LiqPay payment metadata: `_mrkv_liqpay_*` (order id, amount, card mask, …)

No subscriptions, no memberships, no recurring payments.
| Users | 6 | 1 admin (`GadgetoMaster`), 5 test/legacy accounts |
| Orders (HPOS `wp_wc_orders`) | 12 | 2 non-trash (`wc-processing`), all test/small orders |
| Order items / item meta | 33 / 249 | line items + shipping items |
| Order addresses | 22 | billing + shipping per order |
| Yoast indexable | 27,603 | posts + terms SEO |
| Reviews/comments | 47 | e.g. product reviews |

> Cross-check: the most recent `woocommerce_export.csv` snapshot (2026-08) of the
> store contains **22,505 product rows**: SKU prefix `ITL-` = 739, `DCL-` = 21,746,
> no/other SKU = 20. Supplier meta `supplier_slug`: `itlink` 741 · `dclink` 21,746 ·
> `mine` 10. Published: 15,505 published / 7,000 unpublished (hidden).
> The three counts (22,504 / 22,508 / 22,505) differ slightly — expected because the
> export snapshot was taken earlier than the database dump.