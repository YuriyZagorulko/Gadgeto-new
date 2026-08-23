#!/usr/bin/env python3
"""
Migration 010: Add email verification fields to users table.

Run with: python scripts/migration_010_verify_email.py upgrade
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto")

UPGRADE_SQL = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS verification_token_hash VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS verification_token_expires_at TIMESTAMP NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_verification_token_hash
    ON users(verification_token_hash)
    WHERE verification_token_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_users_phone
    ON users(phone);
"""

DOWNGRADE_SQL = """
DROP INDEX IF EXISTS ix_users_phone;
DROP INDEX IF EXISTS ix_users_verification_token_hash;
ALTER TABLE users
    DROP COLUMN IF EXISTS verification_token_hash,
    DROP COLUMN IF EXISTS verification_token_expires_at;
"""

async def run_migration(sql: str):
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: sync_conn.execute(sql))
    await engine.dispose()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["upgrade", "downgrade"])
    args = parser.parse_args()

    sql = UPGRADE_SQL if args.action == "upgrade" else DOWNGRADE_SQL
    asyncio.run(run_migration(sql))
    print(f"Migration {args.action} completed successfully!")
