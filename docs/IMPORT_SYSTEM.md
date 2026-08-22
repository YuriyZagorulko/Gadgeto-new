# Import System — Audit Report

Audited path: `/home/yuri/Desktop/my/projects/gedgeto/catalog/`
(`attributesManager/` is **excluded** from the new implementation; it was read only
to understand the dependency that `sync_itlink_final.py` imports).

Last audit date: 2026-08-22.

---

## 1. Directory inventory

```
catalog/
├── .env                     # supplier credentials — DO NOT commit/copy
├── requirements.txt         # python-slugify, playwright, requests, python-dotenv
├── woocommerce_export.csv   # current WooCommerce export (@22,505 products)
├── attributesManager/       # EXCLUDED from new implementation
├── helpers/
│   ├── woocommerce_category_resolver.py   # supplier→WC category path resolver
│   └── woocommerce_seo_generator.py       # deterministic product SEO generator
├── globalActions/
│   ├── run_pipeline.py                    # orchestrator + CSV merge
│   └── woocommerce_import_all.csv         # merged import file (27,456 rows)
├── IT-link/
│   ├── sync_itlink_final.py               # IT-Link entry point
│   ├── itlink.yml                         # downloaded price list XML (YML format)
│   ├── woocommerce_import_itlink_final.csv  # IT-Link import CSV (4,938 products)
│   ├── unknown_*.txt
│   └── itlink_downloader/                 # OAuth2 (Playwright) downloader package
├── DC-Link/
│   ├── getProducts.py                     # DC-Link downloader (REST)
│   ├── getCategoryID.py                   # helper
│   ├── dclink_products.json               # downloaded catalog (@14,962 items, 2 categories)
│   ├── dclink_categories.json/.csv
│   ├── build_dclink_final_import.py       # DC-Link entry point
│   ├── woocommerce_import_dclink_final.csv  # DC-Link import CSV (22,518 products)
│   ├── unknown_*.txt, dclink_duplicate_report.txt
└── final data mapping/                    # SOURCE OF TRUTH — see DATA_MAPPING.md
    ├── category_mapping.json              # 195 supplier→internal category entries
    ├── attributes_final.json              # 1,119 supplier→internal attr entries
    ├── attribute_value_mapping_final.json # 186 attrs: {supplier value → internal value}
    ├── attribute_remove.json              # 395 attrs to drop
    ├── attribute_value_to_remove.json     # 5 attrs: values to drop
    └── data_from_server/woocommerce_categories.json  # WC categories export (188)
```

## 2. Roles of each part

| Component | Role |
|---|---|
| `helpers/woocommerce_category_resolver.py` | **Reusable logic.** Resolves internal category name → verified WC category path (indexes by name/slug/path; fail-fast). |
| `helpers/woocommerce_seo_generator.py` | **Reusable logic.** Deterministic SEO title/description/focus keyphrase from the product name. |
| `IT-link/itlink_downloader/*` | Supplier communication (OAuth2 via headless Playwright, atomic XML download). Supplier-specific → rewrite/abstract. |
| `IT-link/sync_itlink_final.py` | Main IT-Link: download → validate categories → parse offers → map attrs → price → SEO → reconcile vs `woocommerce_export.csv` → final CSV + unknown logs. |
| `DC-Link/getProducts.py` | DC-Link REST downloader (MD5 auth; categories 1371/1379; products, options, images). |
| `DC-Link/build_dclink_final_import.py` | DC-Link: load JSON → validate categories → map attrs/values → price/markup → reconcile → final CSV + unknown logs. |
| `globalActions/run_pipeline.py` | Orchestrator: runs supplier scripts in order, then merges the final CSVs. |
| `Rozetka/generate_rozetka_xml.py` | Marketplace feed generator (NOT a supplier import). |
| `.env` | Supplier credentials + price API ids — must NOT be copied into the new repo. |

## 3. Supplier data formats

**IT-Link** — YML XML (`itlink.yml`): flat `<category id fenceid>` items under
`<categories>`, `<offer>`s with `<vendorCode>` (stable article), `<name>`,
`<vendor>` (brand), `<categoryId>`, `<price>`, `<rrp>`, `<picture>`, and `<param
name="…">value</param>` for description («Опис») and arbitrary attributes.

**DC-Link** — REST JSON: `articul` (SKU), `productID`, `categoryID`, `name`,
`price` (USD), `price_uah`, `full_image`, `brief_description`, `description`,
`vendorID`, `options` (list of `OptionName`/`ValueName`), `images`.

## 4. Pipeline flow (as executed today)

```
run_pipeline.py
 ├─ 1. IT-Link: sync_itlink_final.py
 │      authenticate → download price list XML (atomic write)
 │      load mappings (#categories + woocommerce_categories.json)
 │      validate ALL supplier categories (fail fast — abort on any error)
 │      parse offers → map attributes → price×1.3 → generate SEO
 │      read ./woocommerce_export.csv (WC snapshot)
 │      reconcile by SKU: absent-from-feed → hidden; new → appended
 │      write woocommerce_import_itlink_final.csv + unknown_*.txt
 ├─ 2. DC-Link: getProducts.py → dclink_products.json (new download)
 │ 3. DC-Link: build_dclink_final_import.py
 │      validate categories (fail fast) → parse JSON → map → markup → reconcile
 │      write woocommerce_import_dclink_final.csv + unknown logs
 └─ 4. merge the two final CSVs → globalActions/woocommerce_import_all.csv
```

**Result:** one WooCommerce "Product CSV Import" file (Ukrainian column headers:
`ID,Type,SKU,Name,Published,Is featured?,Visibility…,Regular price,Sale price,
Categories,Images,Brand,In stock?,Meta: supplier_slug, Meta: supplier_sku,
Meta: _yoast_wpseo_*, Назва N атрибуту/N значення атрибуту …`). The operator
uploads it into WooCommerce.

**Idempotency** today = SKU (prefix `ITL-` / `DCL-`) + WooCommerce SKU-unique
constraint; duplicate SKUs inside one feed are detected and skipped
(`dclink_duplicate_report.txt`, printed in IT-Link).
## 5. Attribute pipeline (exact order & semantics)

Implemented twice today (in `attributesManager/attribute_processor.py` for IT-Link and
inline in the DC-Link builder) with identical semantics:

1. **Remove whole attributes** if name ∈ `attribute_remove.json` (395 keys, e.g.
   `+12V1`, `Описание`, `CAS Latency (CL)`, `HDMI`, …).
2. **Map attribute name** via `attributes_final.json` (1,119 keys).
   - No mapping → attribute **dropped** + logged into `unknown_attributes*.txt`.
   - (IT-Link additionally validates the result against the WooCommerce global
     attributes list; DC-Link differs slightly and logs unknown values separately.)
3. **Drop unwanted values** (`attribute_value_to_remove.json`, 5 attrs, DC-Link only).
4. **Map values** via `attribute_value_mapping_final.json` (keyed by the **internal**
   attr name; 186 attributes). If a mapping table exists for the attribute but the
   supplier value is missing → the value is **dropped** and logged
   (`unknown_attribute_values*.txt`). If no table for the attribute → value kept as-is.
5. Merged duplicates: same internal attr on one product → values joined ` | ` (WC
   multi-value separator), sorted for deterministic output.

## 6. Category pipeline (exact semantics)

```
supplier category name (XML id lookup / DC-Link categoryID→dclink_categories.json)
  → category_mapping.json lookup (supplier name → internal WC category NAME)
  → find category object in woocommerce_categories.json by name
  → take its `path` (e.g. "Комп'ютери > …")
  → verify the path exists in the path index → return path
```
Any invalid category → **fail fast**: the whole import aborts with a printed report.
Mappings are keyed by supplier category name; the resolver is the single source of
truth and is reused by both validation and CSV generation.

## 7. Product SEO generation

`woocommerce_seo_generator.py` is deterministic and dependency-free:
- parses the product name into brand/model/capacity/interface/color/form-factor
  (about 90 known brands);
- `seo_title` → `"{Product Name} — купити в Україні | Gadgeto"`;
- `meta_description` → template text from the cleaned name;
## 8. Reuse / rewrite / deprecate summary

| Component | Decision | Rationale |
|---|---|---|
| Category resolution (name→path, fail-fast) | Reuse as SQL model | same semantics, DB-backed |
| Product SEO generator | Reuse as a backend service | same deterministic logic |
| Attribute processing semantics | Rewrite on DB mapping tables | same semantics, admin-editable |
| Category mapping semantics | Rewrite on DB mapping tables | same semantics, admin-editable |
| IT-Link downloader (OAuth2/Playwright) | Adapt/rewrite (env creds) | keep auth+download patterns |
| DC-Link `getProducts.py` | Adapt/rewrite | REST + JSON stream into staging table |
| `run_pipeline.py` orchestration | **Deprecate** → Celery jobs | imports escape HTTP requests |
| WC CSV generation / `woocommerce_export.csv` reconciliation | **Deprecate** → DB is the source | DB-native upserts |
| `unknown_*.txt` logs | Replace with `import_logs` + admin UI | observability |
| Rozetka XML export | Keep optional (later) | marketplace feed, non-core |

## 9. Pain points found (to fix)

1. Attribute/SEO logic duplicated between suppliers.
2. Reconciliation depends on a manually exported CSV snapshot → races with the live
   shop (items added directly to the shop get hidden by the next import).
3. No centralized state/logging — unknowns land in text files; no retry/queue.
4. Credentials in a committed `.env`.
5. WooCommerce-CSV-specific concepts (Ukrainian column names, ` | ` separator, Yoast
   meta keys) — eliminated by DB-first imports.

## 10. Target pipeline (new system)

```
POST /admin/imports → ImportJob (PostgreSQL) → Celery task (Redis)
  download (IT-Link XML / DC-Link JSON; credentials via env)
  → parse & normalize (per-supplier DTOs)
  → map category (DB) / map attribute (DB) / map values (DB)
  → validate (fail-fast; detailed per-row errors)
  → upsert products by UNIQUE (supplier_id, supplier_sku)
  → update price / stock / brand / images (idempotent)
  → statistics: created / updated / skipped / failed / errors
  → import_logs rows for the admin UI
```
- `focus_keyphrase` → brand + model (+ capacity if not already in model).
Category SEO lives in `CategoriesSEO_Final.json` (see `DATA_MAPPING.md`).