#!/usr/bin/env python3
"""
Drop and recreate all database tables.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")

async def run():
    # Import everything through the centralized __init__
    from backend.app.models import *
    from backend.app.models.base import Base, main_metadata
    
    print(f"Tables in metadata: {main_metadata.sorted_tables}")
    
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(main_metadata.drop_all)
        await conn.run_sync(main_metadata.create_all)
    await engine.dispose()
    
    tables = [t.name for t in main_metadata.sorted_tables]
    print(f"\nCreated {len(tables)} tables:")
    for t in sorted(tables):
        print(f"  - {t}")

if __name__ == "__main__":
    asyncio.run(run())
