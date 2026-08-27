# Supplier Import Skill

## Overview

The import system ingests product data from supplier feeds, maps it to the
internal catalog, and upserts products. Imports run as background Celery jobs,
never in HTTP requests.

## Supported Suppliers

The project currently has only **two** suppliers:

| Supplier | Code | Feed Format | Download Method |
|----------|------|-------------|-----------------|
| IT-Link  | `itlink` | XML (YML) | OAuth2 via headless Playwright |
| DC-Link  | `dclink` | JSON | REST API with MD5 auth |

Do not:

- create arbitrary suppliers;
- add supplier CRUD;
- add "Create supplier" / "Delete supplier";
- create test suppliers.

Supplier selection in mapping/import interfaces must use only these predefined
system suppliers. Adding a new supplier is an explicit architecture/code/database
change and must be intentionally implemented.

## Import Pipeline

```
POST /admin/imports → ImportJob (PostgreSQL) → Celery task (Redis)
  → download supplier feed (credentials via env)
  → parse & normalize into internal DTOs
  → apply DB mappings (category / attribute / values)
  → validate (fail-fast; per-row errors recorded)
  → upsert products by UNIQUE (supplier_id, supplier_sku)
  → update price / stock / brand / images (idempotent)
  → statistics: created / updated / skipped / failed / errors
  → import_logs rows for the admin UI
```

### Key source files

| File | Purpose |
|------|---------|
| `backend/app/imports/tasks.py` | Celery task definitions |
| `backend/app/imports/importer_service.py` | Main import orchestration |
| `backend/app/imports/import_runner.py` | Per-supplier import runner |
| `backend/app/imports/import_stats.py` | Import statistics tracking |
| `backend/app/imports/itlink.py` | IT-Link parser and normalization |
| `backend/app/imports/dclink.py` | DC-Link parser and normalization |
| `backend/app/imports/mapping_resolver.py` | Resolve supplier → internal mappings |
| `backend/app/imports/attribute_processor.py` | Attribute processing logic |
| `backend/app/imports/pricing_service.py` | Price calculation and markup |
| `backend/app/imports/job_health.py` | Import job health monitoring |
| `backend/app/imports/image_helper.py` | Image download and management |
| `backend/app/imports/base.py` | Base import classes |
| `backend/app/imports/registry.py` | Supplier registry |

## Import Job State

Each import is tracked via an `ImportJob` row with:

- `status` — queued, running, succeeded, failed, aborted
- `current_stage` — download, parse, map, validate, upsert
- `progress_json` — detailed progress counters
- `stats_json` — created/updated/skipped/failed counts
- `error_details_json` — per-row and system errors
- `created_at`, `started_at`, `finished_at`

## Debugging Workflow

1. Inspect import job state (check DB or admin UI for status/stats/errors).
2. Check `import_logs` for detailed per-item messages.
3. Inspect `supplier_products` for specific supplier SKU data.
4. Use dry-run mode when available (preview without persisting).
5. Parse and validate supplier feed locally.
6. Do NOT restart a full import as the first debugging step.

A failed diagnostic command does **not** mean the import itself failed.

## Testing

Regression tests are in `backend/tests/`:

```bash
cd backend
pytest tests/test_import_stats.py
pytest tests/test_itlink_regression.py
```

Key test areas:

- Import statistics accuracy (created/updated/skipped/failed)
- Unmapped attribute handling
- Unmapped category handling
- Image deduplication
- Image suppression
- DC-Link image fixes