# Gadgeto — Standalone E-commerce Platform

A production-ready replacement for the legacy Gadgeto WordPress/WooCommerce store
(`gadgeto.com.ua`). The new platform is fully independent of WordPress and WooCommerce.

> **Status: IMPLEMENTATION PHASE.** Audit complete; documentation published. Backend,
> frontend, and database schema implementation in progress.

## Why this project exists

The current store runs on WordPress + WooCommerce. Product import flows through
legacy Python scripts that generate WooCommerce CSV import files. This project
rebuilds the entire store as a standalone application:

- **Frontend:** Next.js (App Router) + React + TypeScript + Tailwind + shadcn/ui
- **Backend:** FastAPI + Pydantic + SQLAlchemy 2.x + Alembic + PostgreSQL + Redis
- **Background jobs:** Celery worker (supplier imports run outside HTTP requests)
- **Payments:** LiqPay (backend-verified callbacks)
- **Delivery:** NovaPosta API
- **Deployment:** Docker + Coolify (staging first; production switched only after approval)

## Source / reference systems (READ-ONLY — never modify)

1. **Legacy Python importer:** `/home/yuri/Desktop/my/projects/gedgeto/catalog/`
   (`attributesManager/` is explicitly **excluded** from the new implementation).
2. **Final mapping data:** `catalog/final data mapping/` — SOURCE OF TRUTH for
   categories/attributes/values mappings (to be migrated into PostgreSQL).
3. **WordPress backup:** `/home/yuri/Desktop/my/temp/tempFiles/myWPAdmin.2026-08-21_20-56-42.tar`
   (HestiaCP full backup of `gadgeto.com.ua`; WP 7.1, WooCommerce 10.9.1).

## Documentation

| Document | Contents |
|---|---|
| `docs/CURRENT_SYSTEM.md` | Audit of the existing WordPress/WooCommerce store |
| `docs/IMPORT_SYSTEM.md` | Audit of the existing Python importer |
| `docs/DATA_MAPPING.md` | Final mapping files — semantics, structure, migration plan |
| `docs/WORDPRESS_DATA_MODEL.md` | WordPress/WooCommerce data model from the backup |
| `docs/DATABASE.md` | Proposed PostgreSQL schema (audit-derived) |
| `docs/ARCHITECTURE.md` | New application architecture |
| `docs/MIGRATION_PLAN.md` | Staged migration & go-live plan |
| `docs/DEPLOYMENT.md` | Docker & Coolify deployment architecture |
| `docs/ENVIRONMENT.md` | Environment variables reference |
| `docs/API.md` | API design overview |

## Project layout (planned)

```
backend/       FastAPI application (api, models, services, imports, admin, ...)
frontend/      Next.js storefront + admin UI
worker/        Celery worker (import jobs, notifications)
docker/        Compose + Dockerfiles
docs/          Documentation
migrations/    Alembic migrations (database schema)
scripts/       Data migration & bootstrap scripts
```

## Operating rules

- The WordPress site, the Python importer and the final mapping files are
  **source/reference systems**. They are kept untouched until the new
  application is validated.
- All changes are reversible: database changes go through Alembic migrations;
  every pre-migration state is backed up.
- No secrets in Git. Only `.env.example` is committed.

## Definition of success

The new store runs independently of WordPress/WooCommerce: catalog, imports,
mappings, filters, search, cart, checkout (guest + registered), orders, NovaPost,
LiqPay, admin panel, SEO, tests, Docker/Coolify deployment.