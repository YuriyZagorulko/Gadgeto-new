# Backend Safety Skill

Practical implementation workflow for agents adding or modifying backend endpoints.

## Pre-Implementation Checklist

Before writing code, answer these questions:

```text
1. Database access type:   sync psycopg2  /  async SQLAlchemy  /  none
2. HTTP/network access:    sync requests  /  async httpx  /  none
3. File I/O:               none  /  small  /  large (size: ___)
4. CPU-heavy operations:   none  /  parsing  /  image  /  transform
5. Async dependencies:     none  /  Depends uses blocking code
6. Background work:        none  /  needs offloading to thread pool
```

Choose the execution model based on the answers:

| Has async I/O? | Has blocking I/O? | Use |
|----------------|-------------------|-----|
| Yes | No | `async def` |
| No | Yes | `def` (FastAPI threadpool) |
| Yes | Yes | `async def` + offload blocking part via `run_in_executor` |
| No | No | `def` (simplest, no overhead) |

## Database Connection Pattern

### ✅ Use this for sync psycopg2 endpoints

```python
from app.core.db_connect import admin_cursor

@router.get("/resource")
def list_resource(...):
    conn, cur = admin_cursor()
    try:
        cur.execute(...)
        ...
        return {"items": items}
    finally:
        conn.close()
```

### ✅ Use this for async SQLAlchemy endpoints

```python
from app.core.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

@router.get("/resource")
async def list_resource(session: AsyncSession = Depends(get_session)):
    result = await session.execute(...)
    ...
```

### ✅ Use this for guaranteed cleanup as a FastAPI dependency

```python
from app.core.db_connect import get_cursor_dep

@router.get("/resource")
def list_resource(cur=Depends(get_cursor_dep)):
    cur.execute(...)
    return {"items": cur.fetchall()}
```

## Running Imports/Exports in Background

Do not do this:

```python
async def start_import(...):
    run_import(...)  # blocks the event loop for minutes
```

Use this pattern (from existing project code):

```python
async def start_import(...):
    # ... DB setup ...
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_import, supplier_code, import_type)
    return {"ok": True}
```

## Verification Steps

For any backend change:

1. **Static check:** Search for `async def`, `psycopg2`, `requests.`, `time.sleep` in the changed file.
2. **Compile check:** `python -m py_compile path/to/file.py`
3. **Health check:** Verify `/health` returns 200.
4. **Endpoint check:** Verify the modified endpoint returns expected status.
5. **Concurrency check:** Where practical, send 10+ concurrent requests and confirm all return 200.
6. **Cleanup:** `git status` — confirm only intended files changed.

## Key Files to Know

| File | Purpose |
|------|---------|
| `backend/app/core/db_connect.py` | All DB connection helpers (connect, cursor, admin_cursor, managed_cursor, managed_connection, get_cursor_dep, get_connection_dep) |
| `backend/app/core/database.py` | Async SQLAlchemy engine and session factory |
| `backend/app/core/config.py` | Timeouts, keepalives, and other settings |
| `backend/app/api/admin/imports.py` | Reference pattern for run_in_executor background jobs |
| `backend/app/api/admin/export.py` | Reference pattern for run_in_executor background jobs |

## Common Mistakes

- **Writing `async def` + `psycopg2`** — this is the #1 vulnerability. Use `def` instead.
- **Forgetting `try/finally`** — any exception path leaks the connection. Always use `try/finally`.
- **No network timeout** — external API calls without explicit timeout can hang indefinitely.
- **`time.sleep()` in async** — blocks the event loop. Use `await asyncio.sleep()`.
- **`BackgroundTasks` for heavy work** — runs on the event loop. Use `run_in_executor` instead.