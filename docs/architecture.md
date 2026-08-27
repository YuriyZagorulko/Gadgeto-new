# Architecture — Gadgeto New Store

For a comprehensive audit-driven architecture report, see `docs/ARCHITECTURE.md`.

## High-Level Overview

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

## Frontend

- **Storefront** (`frontend/`): Next.js App Router, React, TypeScript, Tailwind CSS, shadcn/ui.
  Public pages are RSC/SSG-first. Cart works for guests; account cart merges on login.
- **Admin** (`admin/`): Next.js App Router under `/admin/*` with role-based access.
  Separate Next.js instance.

## Backend

**FastAPI** application at `backend/app/`:

| Directory | Purpose |
|-----------|---------|
| `api/` | Route modules (public, account, checkout, admin) |
| `auth/` | Registration, login, JWT/HTTP-only cookies, roles, email verify |
| `models/` | SQLAlchemy 2.x ORM models |
| `schemas/` | Pydantic v2 schemas |
| `repositories/` | Data-access layer |
| `services/` | Business services (catalog, search, cart, checkout, payments, shipping) |
| `imports/` | Supplier downloaders, parsers, mappers, upsert engine |
| `channels/` | Sales channel integration (Rozetka export) |
| `payments/` | LiqPay client + callback verification |
| `shipping/` | Nova Poshta client + cache |
| `search/` | PostgreSQL search (FTS, trgm) |
| `admin/` | Admin API + permission checks |
| `core/` | Config, database, security, logging, background wiring |

## Database

PostgreSQL as the source of truth. Redis for cache, sessions, and Celery task queue.
See `docs/database.md` for schema details.

## Import Pipeline

See `docs/imports.md` for detailed import architecture and `supplier-import` skill.

## Channels / Export

See `docs/mappings.md` for mapping architecture and `rozetka` skill for Rozetka-specific details.

## Docker

- **PostgreSQL** — host-level (not in Docker Compose for development)
- **Backend** — FastAPI with Uvicorn
- **Frontend** — Next.js storefront
- **Admin** — Next.js admin panel
- Services defined in `docker-compose.yml` with a development override at `docker-compose.dev.yml`

## Principles

- Business logic lives in the backend (FastAPI) — never duplicated in the client.
- Imports run as background jobs (Redis + Celery), never in HTTP requests.
- Idempotent upserts keyed by `(supplier_id, supplier_sku)`.
- Mappings are DB-native and admin-editable (JSON files are archived reference data).
- PostgreSQL is the initial search engine (FTS + pg_trgm + GIN).
- The legacy WordPress site stays untouched.

## Related Documentation

- `docs/ARCHITECTURE.md` — comprehensive audit-driven architecture report
- `docs/DATABASE.md` — detailed database design
- `docs/IMPORT_SYSTEM.md` — supplier import audit and target design
- `docs/DATA_MAPPING.md` — mapping data audit and migration plan
- `docs/DEPLOYMENT.md` — deployment configuration
- `docs/DEVELOPMENT.md` — development setup and conventions