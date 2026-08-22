# API — Design Overview

Status: **outline** (endpoints will be finalized during implementation). Base path:
`/api`. All requests/responses JSON (Pydantic v2). Authentication via HTTP-only
session cookie; admin routes require an `admin`/`staff` role.

---

## 1. Public (storefront)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/catalog` | products listing (filters, sort, pagination) |
| GET | `/api/categories` | full category tree |
| GET | `/api/categories/{slug}` | category detail (filters config included) |
| GET | `/api/products/{slug}` | product detail |
| GET | `/api/search` | full-text + substring search (uk/ru/en) |
| GET | `/api/cities` / `/api/cities/{city}/warehouses` | Nova Posta references (cached) |
| GET | `/api/shipping/options` | shipping methods for a city |
| GET | `/api/checkout/liqpay` | LiqPay payment creation (POST order → return redirect URL) |
| POST | `/api/liqpay/callback` | LiqPay server callback (verified) |

## 2. Cart (signed cookie/guest)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/cart/items` | add / change qty |
| DELETE | `/api/cart/items/{product_id}` | remove |
| GET | `/api/cart` | cart summary (subtotal, delivery estimate, total) |
| POST | `/api/cart/merge` | merge guest cart on login |

## 3. Orders & checkout

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/checkout` | create order (guest or user) |
| GET | `/api/orders/{id}` | order status (public via order token) |
| GET | `/api/account/orders` | own orders (auth) |
| GET | `/api/account/orders/{id}` | own order detail |
| POST | `/api/orders/{id}/pay` | start payment |

## 4. Auth

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | auth |
| POST | `/api/auth/password-reset/request`, `/reset/confirm` | reset |
| POST | `/api/auth/verify-email` | verification |
| GET | `/api/account/profile` · PUT `/api/account/profile` | account |

## 5. Admin (role-scoped)

REST under `/api/admin/…`: `products`, `categories`, `attributes`,
`attribute-values`, `filters`, `mappings/categories`, `mappings/attributes`,
`mappings/values`, `suppliers`, `imports`, `orders`, `users`, `settings`, `dashboard`.

Admin import flow:
```
POST /api/admin/imports                                   # create ImportJob
GET  /api/admin/imports/{id}                              # status + stats
POST /api/admin/imports/{id}/run                          # trigger worker
GET  /api/admin/imports/{id}/logs                         # log entries
```

## 6. Errors & pagination

- Errors: `{"detail": …}` (FastAPI) with proper HTTP status; business errors in a
  consistent `code` field.
- Listing endpoints support `page`/`page_size` (keyset on search), stable sorting.

## 7. Versioning

- Public API versioned (`/api/v1`); admin API versioned separately if needed.
- Breaking changes bump the version.