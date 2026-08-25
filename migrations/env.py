"""Alembic environment configuration.

Import paths:
  - On the host: alembic is run from the project root, where `backend/app/`
    exists as a Python package, so the import is `backend.app.models.base`.
  - Inside the container: `backend/app/` is mounted/copied as `/app/app/`
    and the current directory is `/app`, so the import is `app.models.base`.

The try/except below handles both layouts so that the same env.py works
for host-side tooling and Docker-based deployment.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from sqlalchemy.pool import NullPool

# Support both host (project root with backend/app/) and container (cwd /app with app/) layouts.
try:
    from backend.app.models.base import Base  # noqa: F811
    from backend.app.core.config import Settings
except ModuleNotFoundError:
    from app.models.base import Base  # noqa: F401
    from app.core.config import Settings

# Import all models so they register on Base.metadata
try:
    from backend.app.models import *  # noqa
except ModuleNotFoundError:
    from app.models import *  # noqa

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(Settings().DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Use `Settings` (class) already imported at the top of this module to
    avoid a second hard-coded `backend.app` import path in the container."""
    connectable = create_async_engine(str(Settings().DATABASE_URL), poolclass=NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
