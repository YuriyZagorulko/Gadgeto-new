#!/usr/bin/env python3
"""
Standalone database migration script.
Creates all tables from SQLAlchemy models directly.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")

async def create_tables():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created successfully!")

async def drop_tables():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    print("Tables dropped successfully!")

async def list_tables():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.run_sync(lambda sync_conn: 
            [t.name for t in Base.metadata.sorted_tables])
    await engine.dispose()
    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "drop", "list"])
    args = parser.parse_args()
    
    if args.action == "create":
        asyncio.run(create_tables())
    elif args.action == "drop":
        resp = input("This will DELETE ALL DATA! Continue? (yes/no): ")
        if resp.lower() == "yes":
            asyncio.run(drop_tables())
    elif args.action == "list":
        tables = asyncio.run(list_tables())
        print("Tables:", tables)
