# Architecture — Gadgeto New Store

Status: **finalized** (based on comprehensive audit of legacy system).

References:
- `CURRENT_SYSTEM.md` — WordPress/WooCommerce 7.1/10.9.1, ~22,500 products
- `IMPORT_SYSTEM.md` — IT-Link (XML/YML) + DC-Link (JSON) suppliers
- `DATA_MAPPING.md` — 5 mapping files (195 categories, 1,119 attrs, 186 value maps, 395 remove, 5 value removes)
- `WORDPRESS_DATA_MODEL.md` — MariaDB 11.4.9 with HPOS orders, product meta, Yoast SEO

---

## 1. Principles (from audit + requirements)

- **Business logic lives in the backend (FastAPI)** — never duplicated in the
  client. The storefront (Next.js) consumes the API.
- **Imports run as background jobs** (Redis + Celery), never in HTTP requests.
- **Idempotent upserts** keyed by `(supplier_id, supplier_sku)` or `sku` (legacy products without stable SKU kept nullable).
- **Mappings are DB-native and admin-editable**; JSON mapping files are archived
  reference data (see `DATA_MAPPING.md`).
- PostgreSQL is the initial search engine (FTS + pg_trgm + GIN); a dedicated
  search engine can be added behind a repository interface later.
- The WordPress site stays untouched; staging replaces it only after approval.

## 2. High-level components

```
┌──────────────────┐     ┌──────────────────────┐
│  Next.js (front) │ ←──→│  FastAPI (backend)   │     PostgreSQL (source of truth)
│  storefront +    │     │  • /api/* (public)   │───→  Alembic migrations
│  admin UI        │     │  • /admin/* (staff)  │     Redis (cache, sessions, queue)
└──────────────────┘     └────────┬─────────────┘
                                  │ publish jobs
                            ┌─────▼──────────────┐
                            │ Celery worker(s)   │
                            │ • supplier imports │
                            │ • LiqPay callback  │
                            │ • NP cache refresh │
                            │ • email sending    │
                            └────────────────────┘
```

### Frontend (`frontend/`)
- Next.js **App Router**, React, TypeScript, Tailwind, shadcn/ui.
- Public pages are RSC/SSG-first — SEO content is server-rendered, not CSR.
- Cart works for guests; account cart merges on login.
- Admin UI: Next.js slice under `/admin/*` with role-based access (session cookie).

### Backend (`backend/app/`, FastAPI)
```
backend/app/
├── api/          # route modules (public, account, checkout, admin)
├── auth/         # registration, login, JWT/HTTP-only cookies, roles, email verify
├── models/       # SQLAlchemy 2.x ORM models (from DATABASE.md)
├── schemas/      # Pydantic v2 schemas
├── repositories/ # data-access layer (queries)
├── services/     # business services (catalog, search, cart, checkout, payments, shipping…)
├── imports/      # supplier downloaders, parsers, mappers, upsert engine
├── payments/     # LiqPay client + callback verification
├── shipping/     # NovaPosta client + cache
├── search/       # PostgreSQL search (fts, trgm), interface for later search engine
├── admin/        # admin API + permission checks
└── core/         # config, db, security, logging, background wiring
```

## 3. Import pipeline (worker)

`ImportJob` row → Celery task:
1. fetch supplier feed (IT-Link XML / DC-Link JSON; credentials from env)
2. parse & normalize into internal DTOs
3. apply DB mappings (category / attribute / values)
4. validate (fail-fast like legacy; per-row errors recorded)
5. upsert `products` (+ images, categories, attributes, prices, stock, SEO)
6. hide/disable products absent from the feed (preserving legacy semantics)
7. persist statistics: created / updated / skipped / failed / errors / logs
## 4. Public storefront pages & behaviors

- `/catalog`, `/category/[slug]` with category-specific filters (from
  `category_filters`), pagination, sort, breadcrumbs.
- `/product/[slug]` with gallery, specs (attributes), related products, SEO schema.
- `/search` → `/api/search` (PostgreSQL FTS + trgm; uk/ru/en).
- Cart (guest) → checkout (guest or logged-in) → NovaPosta city/branch/poshtomat →
  LiqPay redirect → order confirmation + email.
- Accounts: register/login/logout, forgot/reset password, email verification,
  `/account/orders`, `/account/profile`, `/order/[id]`.

## 5. Security decisions

- Passwords hashed (Argon2/bcrypt) — never plaintext.
- Sessions: HttpOnly, Secure cookies + CSRF protection.
- LiqPay callbacks: verify the server-side signature before changing order status.
- NovaPosta: backend-only; API key via env.
- Admin endpoints: authenticated + role check; never public.
- Input validation via Pydantic everywhere; SQL via ORM; XSS escaping + sanitize
  product descriptions.
- Rate limiting on auth/checkout endpoints.
- Secrets only via environment (see `ENVIRONMENT.md`).

## 8. Detailed data sources (audit findings)

### WordPress/WooCommerce (legacy production)
- **WordPress version**: 7.1
- **WooCommerce version**: 10.9.1 (initial: 10.1.2, Dec 2025)
- **MariaDB version**: 11.4.9
- **Products**: ~22,504 (publish 14,694, private 7,809, trash 1)
- **Categories**: 188 (including ~9 orphan duplicates at root)
- **Brand taxonomy**: 51 terms
- **Global WooCommerce attributes**: 196
- **HPOS orders**: 12 rows (2 non-trash, all test orders)
- **Images**: ~16,300 attachments
- **SEO plugin**: Yoast (`_yoast_wpseo_*` meta)
- **Shipping**: Nova Poshta via `mrkv_ua_shipping_nova-poshta_*` meta
- **Payment**: LiqPay via `morkva-liqpay` method

### IT-Link supplier (XML/YML format)
- **Download method**: OAuth2 via headless Playwright
- **XML structure**: `<yml_catalog><shop><categories>` + `<offers><offer id=...>`
- **Category mapping**: 11 supplier categories mapped to ~50 internal paths
- **Product fields**: url, price, rrp, currencyId, picture, name, vendorCode, vendor, barcode, categoryId
- **SKU prefix**: `ITL-`
- **Price multiplier**: 1.3 (USD→UAH)
- **Unknown attrs logged** to `unknown_attributes.txt`

### DC-Link supplier (JSON format)
- **Download method**: REST API with MD5 auth
- **JSON structure**: array of products with `options` (attribute list)
- **Category IDs**: 1007 DC-Link categories mapped to internal paths
- **Product fields**: name, articul, categoryID, price_uah, stocks, options (FilterID/OptionID/ValueID tuples)
- **SKU prefix**: `DCL-`
- **Tiered markup**: 1.20–1.50 based on price thresholds
- **Unknown attrs/values logged** to `unknown_attributes_dclink.txt`

### Final mapping data (source of truth)
- **category_mapping.json**: 195 entries (supplier category → WooCommerce category name)
- **attributes_final.json**: 1,119 entries (supplier attr → internal attr name)
- **attribute_value_mapping_final.json**: 186 attribute tables (supplier value → internal value)
- **attribute_remove.json**: 395 attrs to drop (marked as removed)
- **attribute_value_to_remove.json**: 5 attrs with value blacklists

### CategoriesSEO_Final.json (SEO metadata)
- 187 entries with: id, parent_id, name, slug, count, path, focus_keyphrase, seo_title, meta_description, description (incl. FAQ), quality_score

### woocommerce_export.csv (snapshot)
- 127 columns including: ID, Type, SKU, Name, Regular price, Sale price, Categories, Images, Brand, meta fields
- 22,505 product rows (ITL: 739, DCL: 21,746, no SKU: 20)

## 9. Performance

- Target 10k–100k products; keyset pagination, GIN indexes, FTS dictionaries
  (uk/ru/en + trgm), JOINs written to avoid N+1 (selectinload / joins).
- Image optimization: Next.js `next/image`; media served from local storage/CDN.
- Caching: Redis (search-result memoization, NovaPosta references, sessions,
  rate limits); never cache stale prices.
- Imports: batched writes, `ON CONFLICT` upserts.

## 10. Observability

- Structured JSON logging (API + Celery); per-import-job logs surfaced in the admin UI.

## 11. Decisions driven by the audit

- **No global filter list** — filters are per category via the `category_filters`
  join table (admin-editable).
- **Brand reconciliation** — `product_brand` taxonomy + `Бренди` column converge
  into one brand concept.
- **URL preservation** — product slugs kept byte-for-byte (percent-encoded
  Cyrillic); category slugs preserved; 301 redirects for orphan category variants
  and changed paths.
- **SEO** — product/category SEO fields stored in the DB; sitemap/robots generated
  by the backend; JSON-LD schema server-rendered.