"""
Database configuration and session management.
"""

import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Metadata for Alembic autogenerate
metadata = MetaData()


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Get database session context manager."""
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Create all tables (useful for testing)."""
    from app.models import *  # noqa: Import all models

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def drop_tables():
    """Drop all tables (useful for testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
