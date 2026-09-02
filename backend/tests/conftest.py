"""Central pytest configuration for the Gadgeto backend.

Validates and bootstraps the dedicated test database BEFORE any
application code is imported. Provides transactional isolation
fixtures for integration tests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Resolve backend/ on sys.path so ``import app.*`` works regardless of
# where pytest was invoked from. Must happen BEFORE any ``app.*`` import.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
import pytest  # noqa: E402


# Database names that integration tests are NEVER allowed to target.
# - "gadgeto": the live development database.
# - "production", "prod", "live", "main", "master": common production names.
_FORBIDDEN_DB_NAMES = frozenset(
    {
        "gadgeto",
        "production",
        "prod",
        "live",
        "main",
        "master",
    }
)


def _parse_dsn(dsn: str) -> tuple[str, str]:
    """Return (host, dbname) from a postgresql://... DSN.

    Best-effort parser; we only need host and dbname for the safety
    check.
    """
    body = dsn
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://"):
        if body.startswith(prefix):
            body = body[len(prefix):]
            break
    if "@" in body:
        _, body = body.split("@", 1)
    if "/" in body:
        host_part, _, _ = body.partition("/")
    else:
        host_part = body
    if ":" in host_part:
        host, _, _ = host_part.partition(":")
    else:
        host = host_part
    _, _, dbname = body.partition("/")
    if "?" in dbname:
        dbname = dbname.split("?", 1)[0]
    return host, dbname


def _looks_like_remote_host(host: str) -> bool:
    """Return True if the host looks like a remote/production host."""
    if not host:
        return False
    h = host.lower().split(":")[0]
    if h in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}:
        return False
    if h.startswith("10.") or h.startswith("192.168."):
        return False
    if h.startswith("172."):
        parts = h.split(".")
        if len(parts) == 4 and 16 <= int(parts[1]) <= 31:
            return False
    return True


def _validate_test_database_url(url: str) -> None:
    """Hard-fail if the URL is unsafe. Aborts the test session."""
    if not url:
        pytest.exit(
            "TEST_DATABASE_URL is required for tests.\n"
            "Refusing to run tests without a dedicated test database.",
            returncode=2,
        )
    host, dbname = _parse_dsn(url)
    if not dbname:
        pytest.exit(
            f"TEST_DATABASE_URL is missing a database name: {url!r}\n"
            "Refusing to run.",
            returncode=2,
        )
    if dbname.lower() in _FORBIDDEN_DB_NAMES:
        pytest.exit(
            f"TEST_DATABASE_URL points at a forbidden database name: {dbname!r}.\n"
            f"Blocked names: {sorted(_FORBIDDEN_DB_NAMES)}.",
            returncode=2,
        )
    if _looks_like_remote_host(host):
        pytest.exit(
            f"TEST_DATABASE_URL host looks remote: {host!r}. Refusing to run.",
            returncode=2,
        )


# Read and validate TEST_DATABASE_URL before anything else.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
if not TEST_DATABASE_URL:
    fallback = os.environ.get("GADGETO_ALLOW_TEST_DB_FALLBACK", "").strip() == "1"
    if not fallback:
        pytest.exit(
            "TEST_DATABASE_URL is not set.\n"
            "Refusing to run tests without a dedicated test database.\n"
            "Set TEST_DATABASE_URL=postgresql+asyncpg://gadgeto_test:gadgeto_test@localhost:5432/gadgeto_test\n"
            "or set GADGETO_ALLOW_TEST_DB_FALLBACK=1 to fall back to DATABASE_URL (unsafe).",
            returncode=2,
        )
    import warnings  # local import; warnings are uncommon on this path
    TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
    warnings.warn(
        "GADGETO_ALLOW_TEST_DB_FALLBACK=1 is set; tests will use DATABASE_URL. "
        "This is unsafe for shared/development databases.",
        stacklevel=1,
    )

_validate_test_database_url(TEST_DATABASE_URL)

# Force DATABASE_URL to point at the test database BEFORE any app import.
# ``app.core.db_connect`` reads DATABASE_URL at module-import time and
# caches it as ``_DATABASE_URL``; if we don't override it here, every
# ``from app.core.db_connect import DB`` would see the dev DB.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"


# ─────────────────────────────────────────────────────────────────────────────
# Marker registration (unit / integration).
# ─────────────────────────────────────────────────────────────────────────────


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so ``-m unit`` / ``-m integration`` work."""
    config.addinivalue_line(
        "markers",
        "unit: fast, no PostgreSQL dependency. Safe to run anywhere.",
    )
    config.addinivalue_line(
        "markers",
        "integration: requires a dedicated TEST_DATABASE_URL. "
        "Runs inside a transaction that is rolled back at teardown.",
    )


def _looks_like_integration_test(item: pytest.Item) -> bool:
    """Heuristic: does this test talk to a real PostgreSQL database?"""
    module = getattr(item, "module", None)
    if module is None:
        return False
    mod_name = getattr(module, "__name__", "") or ""
    if "psycopg2" in mod_name:
        return True
    g = getattr(module, "__dict__", {}) or {}
    needles = ("psycopg2", "DB", "create_engine", "create_async_engine")
    for n in needles:
        if n in g:
            return True
    return False


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-mark unmarked tests as ``unit`` (the safe default).

    Tests that talk to PostgreSQL are auto-marked ``integration``. Tests
    that don't are auto-marked ``unit``. Either marker can be overridden
    with an explicit decorator.
    """
    for item in items:
        if "integration" in item.keywords or "unit" in item.keywords:
            continue
        if _looks_like_integration_test(item):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


# ─────────────────────────────────────────────────────────────────────────────
# Schema bootstrap (session-scoped, autouse, runs once per test run).
# ─────────────────────────────────────────────────────────────────────────────


def _admin_dsn() -> str:
    """DSN to the ``postgres`` admin DB on the same host."""
    host, _ = _parse_dsn(TEST_DATABASE_URL)
    user = os.environ.get("TEST_POSTGRES_ADMIN_USER", "postgres")
    pw = os.environ.get("TEST_POSTGRES_ADMIN_PASSWORD", "")
    return f"postgresql://{user}:{pw}@{host}:5432/postgres"


def _ensure_test_database_exists() -> None:
    """Create the test database if missing, using an admin DSN."""
    _, dbname = _parse_dsn(TEST_DATABASE_URL)
    admin_dsn = _admin_dsn()
    try:
        conn = psycopg2.connect(
            admin_dsn,
            connect_timeout=5,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )
    except psycopg2.OperationalError as exc:
        import warnings
        warnings.warn(
            f"Could not connect to admin database ({admin_dsn!r}): {exc}. "
            "Assuming the test database already exists.",
            stacklevel=1,
        )
        return
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)
            )
            if cur.fetchone() is None:
                try:
                    cur.execute(f'CREATE DATABASE "{dbname}"')
                except psycopg2.errors.InsufficientPrivilege as exc:
                    pytest.exit(
                        f"Test database {dbname!r} does not exist and the "
                        f"admin user could not create it: {exc}\n"
                        "Create the database manually, then re-run pytest.",
                        returncode=2,
                    )
    finally:
        conn.close()


def _ensure_test_schema() -> None:
    """Create all tables in the test DB if they are missing.

    Uses the same ``main_metadata`` that ``scripts/create_tables.py``
    uses. ``checkfirst=True`` makes this a no-op when the schema
    already exists.
    """
    # Import after DATABASE_URL override so any module-level capture
    # picks up the test DSN.
    from app.models.base import main_metadata  # noqa: WPS433
    from sqlalchemy import create_engine

    sync_dsn = TEST_DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_dsn)
    try:
        main_metadata.create_all(engine, checkfirst=True)
    finally:
        engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_test_database() -> None:
    """Session-scoped fixture: ensure the test DB exists and has schema."""
    _ensure_test_database_exists()
    _ensure_test_schema()


# ─────────────────────────────────────────────────────────────────────────────
# Transactional isolation fixtures.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_connection():
    """Yield a psycopg2 connection wrapped in an outer transaction.

    The connection is opened with ``autocommit=False``. The test's
    statements run inside a single transaction on this connection.
    When the test finishes (success, failure, or KeyboardInterrupt),
    the transaction is rolled back.

    Important caveat: if the test calls ``conn.commit()`` itself, that
    ``commit`` ends the OUTER transaction (psycopg2 does not expose
    SAVEPOINT-aware commits). The fixture's teardown ``rollback``
    afterwards has nothing left to roll back, and any earlier writes
    committed by the test are persisted into the test database.

    Tests should therefore AVOID calling ``conn.commit()``. With
    ``autocommit=False``, every statement is buffered in the
    transaction and is visible to subsequent SELECTs on the same
    connection — there is no need to commit to see your own writes.

    Tests must NOT open their own ``psycopg2.connect()`` call against
    the test database, because such a connection is a separate session
    and will not see the rolled-back state of ``db_connection``.
    """
    sync_dsn = TEST_DATABASE_URL.replace("+asyncpg", "")
    conn = psycopg2.connect(
        sync_dsn,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )
    # CRITICAL: do NOT enable autocommit. We rely on the implicit
    # transaction to capture every statement so the teardown rollback
    # undoes them all.
    conn.autocommit = False
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


@pytest.fixture
def db_cursor(db_connection):
    """Yield a RealDictCursor bound to ``db_connection``.

    Convenience wrapper for tests that need a cursor but don't care
    about the underlying connection object. The cursor participates in
    the outer transaction held by ``db_connection`` and is rolled back
    at teardown.
    """
    cur = db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
    finally:
        try:
            cur.close()
        except Exception:
            pass


@pytest.fixture
def test_settings(monkeypatch):
    """Force ``app.core.config.settings.DATABASE_URL`` and
    ``app.core.db_connect.DB`` to point at the test database.

    Belt-and-braces measure in case any module captured the dev DB URL
    before conftest had a chance to override ``DATABASE_URL``.
    """
    from app.core import config as app_config
    from app.core import db_connect as app_db_connect

    sync = TEST_DATABASE_URL.replace("+asyncpg", "")
    monkeypatch.setattr(app_config.settings, "DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setattr(app_db_connect, "_DATABASE_URL", sync)
    monkeypatch.setattr(app_db_connect, "DB", sync)
    yield TEST_DATABASE_URL