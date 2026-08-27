# Backend Concurrency & Blocking-I/O Safety

These rules prevent the event-loop blocking vulnerability that previously caused a full backend freeze.

## 1. FastAPI async rule — never do this

**Forbidden:** synchronous blocking I/O inside `async def` endpoints.

```python
# NEVER DO THIS
@router.get("/products")
async def list_products():
    conn, cur = psycopg2.connect(...)
    cur.execute(...)
```

```python
# ALSO NEVER DO THIS
async def endpoint():
    db_query_using_sync_psycopg2()
```

**Use this instead** when the handler uses synchronous psycopg2 and synchronous business logic:

```python
@router.get("/products")
def list_products():
    conn, cur = admin_cursor()
    ...
```

FastAPI executes synchronous endpoints in a threadpool, keeping the event loop free.

## 2. Async endpoints must contain genuinely async operations

An endpoint should be `async def` only when it actually benefits from asynchronous I/O.

**Good examples:**

```python
async def endpoint(...):
    result = await db.execute(...)
```

```python
async with httpx.AsyncClient(...) as client:
    response = await client.get(...)
```

```python
content = await upload.read()
```

**Potentially unsafe — mixed pattern:**

```python
async def endpoint(...):
    content = await upload.read()       # async — OK
    save_to_database_using_psycopg2()   # sync — blocks event loop
```

If any line in the handler performs meaningful synchronous blocking work, either:
- make the whole handler synchronous, or
- explicitly offload the blocking operation to a worker thread.

Do not assume safety based on a single `await` in the function.

## 3. Blocking I/O classification

Treat the following as blocking by default:

- `psycopg2` (synchronous PostgreSQL driver)
- synchronous `requests`
- synchronous `httpx.Client`
- synchronous filesystem operations on potentially large files
- Playwright synchronous APIs
- subprocess calls
- CPU-heavy image processing
- CPU-heavy parsing/transformation (XML, large JSON, etc.)
- external SDKs that do not provide async APIs
- `time.sleep()`

**Never put these directly into an async event-loop path** unless the operation is demonstrably trivial (fast, bounded, <1ms) and the architecture explicitly allows it.

## 4. Never use time.sleep() in async code

**Forbidden:**

```python
async def endpoint(...):
    time.sleep(1)
```

Use `await asyncio.sleep(1)` if the operation is genuinely asynchronous.

If the surrounding logic is synchronous, keep the whole operation synchronous.

## 5. Database connection lifecycle

All synchronous PostgreSQL connections must have guaranteed cleanup.

**Never write new code like this:**

```python
conn, cur = psycopg2.connect(...)
cur.execute(...)
return result
conn.close()  # ← skipped on exception or early return
```

Use the project's established database helpers:

- `admin_cursor()` — returns `(conn, cur)` with timeouts, requires `try/finally`
- `managed_cursor()` — context manager, guaranteed cleanup
- `managed_connection()` — context manager, guaranteed cleanup
- `get_cursor_dep()` — FastAPI dependency, guaranteed cleanup
- `get_connection_dep()` — FastAPI dependency, guaranteed cleanup

Always guarantee: `acquire → use → success OR exception → rollback if required → close`

Do not introduce new ad-hoc database connection helpers. Do not directly call `psycopg2.connect()` in application endpoints.

## 6. Database timeout requirements

New PostgreSQL connections must use the project's established timeout/keepalive configuration defined in `app.core.db_connect`:

- `connect_timeout=10`
- `keepalives_idle=30`
- `keepalives_interval=10`
- `keepalives_count=3`

Do not create raw connections without these protections.

## 7. External HTTP API rules

**Async HTTP:** use an explicit timeout (e.g. `aiohttp.ClientTimeout(total=30)`).

**Synchronous HTTP:** use explicit connect/read/total timeouts (e.g. `requests.get(url, timeout=(10, 30))`).

**Never rely on implicit library defaults** for production external API calls. Synchronous HTTP must not run directly on the event loop.

## 8. Background jobs

Long-running or blocking operations such as supplier imports, exports, taxonomy synchronization, Playwright automation, large file processing, and synchronous external APIs must run outside the event loop.

Use the project's established `run_in_executor` pattern:

```python
loop = asyncio.get_event_loop()
loop.run_in_executor(None, blocking_function, arg1, arg2)
```

Do not use FastAPI `BackgroundTasks` for long-running blocking operations — `BackgroundTasks` runs synchronously in the event loop.

Inspect existing project patterns (`backend/app/api/admin/imports.py`, `backend/app/api/admin/export.py`) before introducing a new mechanism.

## 9. CPU-heavy operations

Do not execute significant CPU-heavy work directly inside an async endpoint. Examples: image manipulation, large XML/YAML/JSON processing, huge data transformations, compression, expensive calculations. Offload to an appropriate worker/thread/process mechanism.

## 10. Dependencies matter too

FastAPI dependencies can also block the event loop. Do not assume an endpoint is safe just because its own function body contains no blocking code.

Audit dependencies such as `Depends(...)` for synchronous psycopg2, synchronous HTTP, filesystem access, or CPU-heavy operations. Use synchronous dependencies when appropriate so FastAPI can execute them in the threadpool.

## 11. Preserve the async/sync boundary

When modifying existing code, before changing `async def` ↔ `def`:

- inspect whether callers use `await`
- inspect whether dependencies are async
- inspect whether the endpoint performs async I/O
- inspect whether response generation depends on async behavior
- inspect whether the function is called directly elsewhere

Do not blindly convert functions. The objective is: **Async code should perform async I/O. Blocking code should run outside the event loop.**

## 12. Mandatory pre-implementation audit

Before adding or modifying a backend endpoint, identify:

1. **Database access type** — sync psycopg2 or async SQLAlchemy?
2. **HTTP/network access type** — sync or async client?
3. **File I/O** — potentially large reads/writes?
4. **CPU-heavy operations** — parsing, transformation, image processing?
5. **Async dependencies** — does any `Depends()` use blocking code?
6. **Background/long-running operations** — should this be offloaded?

Then choose the correct execution model. Do not start implementation before determining whether the endpoint is blocking or non-blocking.

## 13. Mandatory verification for backend changes

For any change that adds or modifies backend endpoints, perform at least:

### Static search
Check for patterns such as `async def`, `psycopg2`, `requests.`, `httpx.Client`, `time.sleep`, `subprocess` and inspect whether any blocking operation can execute on the event loop.

### Syntax validation
Run `py_compile` on modified Python files.

### Runtime verification
Verify `/health` is responsive, verify the modified endpoint works, and verify at least one unrelated endpoint remains responsive. For changes involving concurrency or database access, test concurrent requests where practical.

## 14. Critical anti-patterns

The following patterns must be treated as architectural violations unless there is an explicit documented reason:

| Pattern | Problem |
|---------|---------|
| `async def` + `psycopg2` | Synchronous DB blocks event loop |
| `async def` + `requests` | Synchronous HTTP blocks event loop |
| `async def` + `httpx.Client` (sync) | Synchronous HTTP blocks event loop |
| `async def` + `time.sleep` | Blocks event loop instead of yielding |
| `async def` + blocking filesystem | Large reads/writes block event loop |
| `async def` + synchronous Playwright | Heavy browser automation blocks event loop |
| `async def` + long CPU operation | Event loop starved of CPU |

The agent must stop and reconsider the execution model when encountering one of these.

## 15. Rule priority

This rule does NOT mean "everything must be synchronous." It means: **"Every operation must execute in an execution context appropriate to its blocking characteristics."**

- `async def` + async I/O → genuinely asynchronous operations
- `def` + synchronous I/O → synchronous operations (FastAPI threadpool)
- `run_in_executor` → long-running blocking work
- managed DB helpers (`admin_cursor`, `managed_cursor`, `managed_connection`) → database lifecycle

## 16. Existing project architecture takes precedence

Before introducing new patterns, inspect existing project implementations. Prefer existing:

- DB helpers (`app.core.db_connect`)
- executor patterns (`run_in_executor` in import/export handlers)
- timeout configuration
- HTTP client abstractions
- dependency patterns

Do not introduce a second competing architecture.

## 17. Related skills

For practical implementation guidance, see the `backend-safety` skill in `.cline/skills/backend-safety/`.
