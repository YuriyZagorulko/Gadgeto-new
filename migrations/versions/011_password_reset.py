"""011: Add password reset fields to users table.

Additive-only migration:
- password_reset_token_hash (nullable, indexed)
- password_reset_token_expires_at (nullable)
"""

revision: str = '011_password_reset'
down_revision: str = '010_email_verification'

UPGRADE_SQL = """
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS password_reset_token_expires_at TIMESTAMP NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_password_reset_token_hash
    ON users(password_reset_token_hash)
    WHERE password_reset_token_hash IS NOT NULL;
"""

DOWNGRADE_SQL = """
DROP INDEX IF EXISTS ix_users_password_reset_token_hash;
ALTER TABLE users
    DROP COLUMN IF EXISTS password_reset_token_hash,
    DROP COLUMN IF EXISTS password_reset_token_expires_at;
"""
