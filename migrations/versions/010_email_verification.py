"""010: Add email verification fields to users table.

Additive-only migration:
- verification_token_hash (nullable, unique)
- verification_token_expires_at (nullable)
- phone now has an index (for uniqueness lookups)
"""

revision: str = '010_email_verification'
down_revision: str = '009_media_library'

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