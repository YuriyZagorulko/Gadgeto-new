# Gadgeto — Standalone E-commerce Platform

A production-ready replacement for the legacy Gadgeto WordPress/WooCommerce store (`gadgeto.com.ua`).

> **Status: IMPLEMENTATION PHASE.** Backend, frontend, and database schema in progress.

## Architecture

- **Frontend:** Next.js (App Router) + React + TypeScript + Tailwind + shadcn/ui
- **Backend:** FastAPI + Pydantic + SQLAlchemy 2.x + Alembic + PostgreSQL + Redis
- **Background jobs:** Celery worker (supplier imports, email, etc.)
- **Payments:** LiqPay (backend-verified callbacks)
- **Delivery:** Nova Poshta API integration

## Project Structure

```
Gadgeto-new/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── repositories/ # Data access layer
│   │   ├── services/     # Business logic
│   │   ├── imports/      # Supplier importers
│   │   ├── payments/     # Payment processing
│   │   ├── shipping/     # Nova Poshta integration
│   │   ├── search/       # Search service
│   │   └── core/         # Config, DB, security
│   ├── migrations/       # Alembic migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/             # Next.js frontend
│   ├── src/
│   │   ├── app/          # App Router pages
│   │   └── components/   # React components
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml    # Local dev setup
├── docs/                 # Documentation
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── IMPORT_SYSTEM.md
│   └── ...
├── .env.example          # Environment template
└── README.md
```

## Quick Start (Local Development)

1. **Clone and set up:**
   ```bash
   cd /home/yuri/Desktop/my/projects/Gadgeto-new
   cp .env.example .env
   # Edit .env with your values
   ```

2. **Start services with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

3. **Run migrations:**
   ```bash
   cd backend
   alembic upgrade head
   ```

4. **Access:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API docs: http://localhost:8000/docs

## Key Features

- Product catalog with categories
- Category-specific filters
- Product attributes and values
- Advanced search (PostgreSQL FTS)
- Shopping cart (guest + registered)
- Guest checkout
- Nova Poshta delivery integration
- LiqPay payments
- Supplier imports (IT-Link, DC-Link)
- Admin panel
- SEO-friendly pages
- Docker deployment

## Documentation

See `docs/` for detailed documentation:
- `ARCHITECTURE.md` — System architecture
- `DATABASE.md` — PostgreSQL schema
- `IMPORT_SYSTEM.md` — Import pipeline
- `MIGRATION_PLAN.md` — Migration strategy
- `DEPLOYMENT.md` — Docker & Coolify deployment

## Reference Systems (READ-ONLY)

The following legacy systems are analyzed but not modified:
1. **Legacy importer:** `/home/yuri/Desktop/my/projects/gedgeto/catalog/`
2. **Final mappings:** `/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping/`
3. **WordPress backup:** `/home/yuri/Desktop/my/temp/tempFiles/myWPAdmin.2026-08-21_20-56-42.tar`

## Roadmap

- [x] Audit and documentation
- [x] Backend structure (models, repositories, services)
- [x] Frontend structure (pages, components)
- [ ] Complete supplier importers
- [ ] Full search implementation
- [ ] Payment callbacks
- [ ] Nova Poshta integration
- [ ] Admin panel
- [ ] Tests
- [ ] Production deployment

## License

Internal use only.
