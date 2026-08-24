# Gadgeto — Standalone E-commerce Platform

A standalone production-oriented e-commerce platform being developed as a replacement for the legacy Gadgeto WordPress/WooCommerce store (`gadgeto.com.ua`).

> **Status: ACTIVE DEVELOPMENT.**
> The core backend, database, supplier import system, admin panel, frontend architecture, and deployment infrastructure are implemented and under active development and validation.

## Architecture

- **Backend:** FastAPI + Python
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Migrations:** Alembic
- **Frontend:** Next.js App Router + React + TypeScript
- **Styling:** Tailwind CSS + shadcn/ui
- **Payments:** LiqPay with backend-verified callbacks
- **Delivery:** Nova Poshta API integration
- **Search:** PostgreSQL Full-Text Search
- **Deployment:** Docker / Docker Compose
- **Reverse Proxy:** Nginx
- **Supplier Integrations:** IT-Link, DC-Link

## Project Structure

```text
Gadgeto-new/
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── repositories/     # Data access layer
│   │   ├── services/         # Business logic
│   │   ├── imports/          # Supplier import system
│   │   ├── payments/         # Payment processing
│   │   ├── shipping/         # Nova Poshta integration
│   │   ├── search/           # Search services
│   │   └── core/             # Configuration, DB, security
│   ├── migrations/           # Alembic migrations
│   ├── tests/                # Backend tests
│   ├── requirements.txt
│   └── Dockerfile
│
├── admin/                    # Admin panel
│   └── src/
│       └── app/
│           ├── imports/       # Supplier import management
│           └── ...
│
├── frontend/                 # Next.js storefront
│   ├── src/
│   │   ├── app/              # App Router pages
│   │   └── components/       # React components
│   ├── package.json
│   └── Dockerfile
│
├── docs/                     # Project documentation
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── IMPORT_SYSTEM.md
│   ├── MIGRATION_PLAN.md
│   ├── DEPLOYMENT.md
│   └── ...
│
├── docker-compose.yml        # Local development environment
├── .env.example              # Environment template
└── README.md

Current System
Product Catalog
Products and categories
Product attributes and attribute values
Category-specific filters
Product brands
Product images
Product search
PostgreSQL Full-Text Search
Supplier Import System

The platform includes a dedicated supplier import pipeline supporting:

IT-Link
DC-Link
Supplier authentication
Catalog downloads
Category mapping
Attribute mapping
Attribute value mapping
Product creation and updates
Price calculation
Import statistics
Import logs
Error handling
Import cancellation
Import history
Detailed import reports

Each completed import can be inspected through a dedicated report containing information such as:

processed products
created products
updated products
skipped products
failed products
unmapped categories
unmapped attributes
unmapped attribute values
warnings
errors
import logs
execution duration
Attribute & Mapping System

The application uses a normalized internal attribute taxonomy with supplier-specific mappings.

The mapping system supports:

Supplier attributes → internal attributes
Supplier values → internal values
Active/inactive mappings
Existing attribute reuse
Deterministic taxonomy migrations
Safe handling of unmapped supplier data
Historical mapping migrations through Alembic

Ambiguous supplier data is intentionally not automatically assigned to unrelated internal attributes.

Admin Panel

The admin panel provides management interfaces for:

Products
Categories
Attributes
Attribute values
Supplier mappings
Supplier imports
Import history
Import reports
Import logs
Import errors and warnings
Import Workflow

The general supplier import flow is:

Supplier
   │
   ▼
Authentication
   │
   ▼
Catalog Download
   │
   ▼
XML / Catalog Parsing
   │
   ▼
Category Resolution
   │
   ▼
Attribute Resolution
   │
   ▼
Value Resolution
   │
   ▼
Price Calculation
   │
   ▼
Product Create / Update
   │
   ▼
Import Statistics & Logs
   │
   ▼
Detailed Import Report

Import execution is performed by the backend.

The admin panel is used to start, monitor, cancel, and review imports.

Import Reports

Every import job has a detailed report available from:

Import history
The active import console after completion

Reports provide a complete overview of the import result and are intended to make data-quality problems visible without inspecting backend logs manually.

A report may include:

Import status
Supplier
Import type
Start and finish time
Execution duration
Processing statistics
Created products
Updated products
Skipped products
Failed products
Unmapped categories
Unmapped attributes
Unmapped attribute values
Warnings
Errors
Detailed import logs
Database & Migrations

Database schema changes are managed through Alembic.

Migrations are used for:

Schema changes
Attribute taxonomy changes
Supplier mapping changes
Data migrations
Deterministic cleanup operations

Production migrations must be reviewed and validated before execution.

Destructive data migrations are treated separately from normal schema migrations and require explicit validation.

Quick Start — Local Development
1. Clone the repository
git clone https://github.com/YuriyZagorulko/Gadgeto-new.git
cd Gadgeto-new
2. Configure environment
cp .env.example .env

Edit .env with the required database, supplier, payment, shipping, and application settings.

3. Start Docker services
docker compose up -d
4. Run database migrations
docker compose exec backend alembic upgrade head

Alternatively, if running the backend directly:

cd backend
alembic upgrade head
5. Access the application
Frontend: http://localhost:3000
Admin panel: http://localhost:3001
Backend API: http://localhost:8000
API documentation: http://localhost:8000/docs
Testing
Backend

Run the backend test suite:

cd backend
pytest
Admin TypeScript

Run the TypeScript type checker:

cd admin
npx tsc --noEmit

The project also contains regression tests for critical supplier import behaviour.

Docker

The project is designed to run using Docker Compose.

Start services
docker compose up -d
Rebuild a service
docker compose build backend
docker compose up -d backend
View logs
docker compose logs -f backend
Check running services
docker compose ps
Documentation

See docs/ for detailed technical documentation:

ARCHITECTURE.md — System architecture
DATABASE.md — PostgreSQL schema and data model
IMPORT_SYSTEM.md — Supplier import architecture
MIGRATION_PLAN.md — Migration strategy
DEPLOYMENT.md — Docker and deployment documentation

Additional documentation should be added to docs/ when a subsystem becomes sufficiently complex to require independent documentation.

Reference Systems — READ ONLY

The following legacy systems and data sources are used for analysis and migration purposes only.

They must not be modified by the new application.

Legacy Importer
/home/yuri/Desktop/my/projects/gedgeto/catalog/
Final Mapping Data
/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping/
Legacy WordPress Backup
/home/yuri/Desktop/my/temp/tempFiles/myWPAdmin.2026-08-21_20-56-42.tar
Development Principles

The project follows several important data-safety principles:

Do not guess the semantic meaning of supplier data.
Prefer deterministic mappings.
Do not silently overwrite conflicting data.
Avoid destructive migrations unless explicitly required.
Preserve existing data when semantic meaning is uncertain.
Validate migrations against development/test databases before production execution.
Keep supplier-specific logic isolated from the core product taxonomy.
Record import warnings and errors rather than silently ignoring them.
Make import results observable through statistics, logs, and reports.
Do not run supplier imports automatically as part of database migrations.
Review destructive data-cleanup operations separately before production execution.
Roadmap
Complete supplier import validation
Complete attribute/value mapping coverage
Improve import data-quality reporting
Complete product catalog migration
Complete storefront functionality
Complete search implementation
Complete LiqPay integration
Complete Nova Poshta integration
Expand automated test coverage
Production deployment
Gradual migration from the legacy WordPress/WooCommerce platform
License

Internal use only.