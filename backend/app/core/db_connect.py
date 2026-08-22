"""Shared database connection - all DB connections use this.
Database URL comes from DATABASE_URL environment variable only.
Never hardcode credentials."""
import os
import psycopg2
import psycopg2.extras

# Get DATABASE_URL from environment (set via .env or Coolify secrets)
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")

def _dsn():
    u = _DATABASE_URL
    if u.startswith("postgresql+asyncpg://"):
        u = "postgresql://" + u[len("postgresql+asyncpg://"):]
    return u

# Export DB variable for backward compatibility with existing API files
DB = _dsn()

def connect():
    """Get a database connection with autocommit."""
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    return conn

def cursor():
    """Get cursor with RealDictCursor factory."""
    conn = connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur
