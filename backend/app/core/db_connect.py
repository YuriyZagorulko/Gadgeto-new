"""Shared database connection - all DB connections use this.
Database URL comes from DATABASE_URL environment variable only.
Never hardcode credentials."""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

# Get DATABASE_URL from environment (set via .env or Coolify secrets)
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")

# Bounds for every connection. PostgreSQL/database defaults are effectively
# unbounded (`statement_timeout=0`, `tcp_keepalives_idle=7200` = ~2h), so a
# stalled/silent libpq socket can block a caller for minutes. These timeouts
# make any network/socket stall fail fast instead of parking a worker for the
# OS default keepalive interval.
_CONNECT_TIMEOUT_SECONDS = 10
_KEEPALIVES_IDLE_SECONDS = 30
_KEEPALIVES_INTERVAL_SECONDS = 10
_KEEPALIVES_COUNT = 3

def _dsn():
    u = _DATABASE_URL
    if u.startswith("postgresql+asyncpg://"):
        u = "postgresql://" + u[len("postgresql+asyncpg://"):]
    return u

# Export DB variable for backward compatibility with existing API files
DB = _dsn()

def connect():
    """Get a database connection with autocommit (each statement commits).

    Every connection created here is a standalone connection (no pool), so it is
    the caller's responsibility to close it. Use the context managers /
    FastAPI dependencies below so connections are always released, including
    on exceptions.
    """
    conn = psycopg2.connect(
        _dsn(),
        connect_timeout=_CONNECT_TIMEOUT_SECONDS,
        keepalives=1,
        keepalives_idle=_KEEPALIVES_IDLE_SECONDS,
        keepalives_interval=_KEEPALIVES_INTERVAL_SECONDS,
        keepalives_count=_KEEPALIVES_COUNT,
    )
    conn.autocommit = True
    return conn

def cursor():
    """Get cursor with RealDictCursor factory."""
    conn = connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur

def get_cursor():
    """Get cursor only (for FastAPI endpoints that close it manually)."""
    conn = connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return cur


@contextmanager
def managed_cursor():
    """Cursor with guaranteed close (and best-effort rollback) on exceptions.

    Connections are standalone (never pooled), so close() is the correct way
    to release them in every case.
    """
    cur = get_cursor()
    try:
        yield cur
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        raise
    finally:
        if not cur.connection.closed:
            cur.connection.close()


@contextmanager
def managed_connection():
    """(connection, cursor) pair with guaranteed close/rollback on exceptions."""
    conn, cur = cursor()
    try:
        yield conn, cur
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if not conn.closed:
            conn.close()


def get_cursor_dep():
    """FastAPI dependency that yields a cursor and always closes the connection.

    Even when a request handler raises, FastAPI resumes this generator after
    the request, so the connection is never leaked and the transaction is
    rolled back.
    """
    with managed_cursor() as cur:
        yield cur


def get_connection_dep():
    """Like get_cursor_dep but yields (conn, cur) for handlers that need conn."""
    with managed_connection() as (conn, cur):
        yield conn, cur
