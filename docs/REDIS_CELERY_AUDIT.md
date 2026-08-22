# Redis/Celery Audit — Removal Report

## Summary

Redis and Celery are **NOT required** by any current Gadgeto functionality.
They were proposed during the initial architecture design but never fully
integrated. All business logic runs directly against PostgreSQL, and imports
execute as normal Python processes.

## Where Redis Was Referenced

| Location | Usage | Action |
|---|---|---|
| `backend/app/core/config.py` | `REDIS_URL` environment variable | REMOVE |
| `backend/app/core/celery_app.py` | Celery app using Redis as broker | REMOVE (file) |
| `backend/app/imports/tasks.py` | Celery task definitions | REPLACE with direct functions |
| `backend/requirements.txt` | `redis>=5.2.0`, `celery[redis]>=5.4.0` | REMOVE |
| `backend/pyproject.toml` | redis, celery dependencies | REMOVE |
| `docker-compose.yml` | Redis service, worker service, redis volume | REMOVE |
| `.env.example` | `REDIS_URL` | REMOVE |
| `.env` | `REDIS_URL` | REMOVE |
| `README.md` | References in tech stack | UPDATE |

## Where Celery Was Referenced

| Location | Usage | Action |
|---|---|---|
| `backend/app/core/celery_app.py` | Celery app initialization | REMOVE (entire file) |
| `backend/app/imports/tasks.py` | Celery task decorators | REPLACE with direct functions |
| `docker-compose.yml` | Celery worker container | REMOVE |

## What Was Replaced

The `tasks.py` module was using Celery decorators but never actually called
from production code. The `run_import_task` function was the only real task,
and it simply wrapped `ITLinkImporter` and `DCLinkImporter` which are
already directly executable.

The importers continue to work as normal Python processes:
- `python -m app.imports.itlink`
- `python -m app.imports.dclink`

## Import Pipeline After Removal

```
Supplier feed (XML/JSON)
        ↓
Python importer (normal process)
        ↓
PostgreSQL
```

For scheduled imports, Coolify cron jobs or a simple container restart
can trigger the import process. No Redis or Celery broker needed.

## Verification After Removal

- IT-Link importer: runs directly ✅
- DC-Link importer: runs directly ✅
- Health checks: only verify FastAPI + PostgreSQL ✅
- Docker Compose: starts without Redis/worker ✅
