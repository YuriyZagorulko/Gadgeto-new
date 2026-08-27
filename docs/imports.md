# Import System

For the comprehensive audit report, see `docs/IMPORT_SYSTEM.md`.

## Overview

The import system ingests product data from supplier feeds, maps it to the
internal catalog, and upserts products. Imports run as background Celery jobs,
never in HTTP requests.

## Supported Suppliers

| Supplier | Code | Feed Format | Download Method | SKU Prefix | Markup |
|----------|------|-------------|-----------------|------------|--------|
| IT-Link  | `itlink` | XML (YML) | OAuth2 via headless Playwright | `ITL-` | 1.3× (USD→UAH) |
| DC-Link  | `dclink` | JSON | REST API with MD5 auth | `DCL-` | 1.20–1.50 tiered |

## Pipeline

```
POST /admin/imports
  → ImportJob created (PostgreSQL)
  → Celery task picked up (Redis)
  → download feed
  → parse & normalize
  → apply DB mappings (category, attribute, values)
  → validate (fail-fast, per-row errors)
  → upsert products by UNIQUE(supplier_id, supplier_sku)
  → update price / stock / brand / images
  → record stats + logs
```

## Key Source Files

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
| `backend/app/imports/registry.py` | Supplier registry |

## Import Job Tracking

Each import is tracked via an `ImportJob` row with status, stage, progress,
statistics, and error details — all surfaced in the admin UI.

## Debugging

1. Inspect the import job state (status, stage, stats, errors).
2. Check `import_logs` for per-item messages.
3. Inspect `supplier_products` for specific SKU data.
4. Use dry-run / preview when available.
5. Do NOT restart a full import as the first debugging step.

## Related Documentation

- `docs/IMPORT_SYSTEM.md` — comprehensive supplier import audit report
- `docs/DATA_MAPPING.md` — mapping data audit and migration plan
- `docs/ARCHITECTURE.md` — system architecture with import pipeline diagram
- `.cline/skills/supplier-import/SKILL.md` — import operational skill