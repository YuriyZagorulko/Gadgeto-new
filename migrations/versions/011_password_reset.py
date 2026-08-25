"""011: Add password reset fields to users table.

Additive-only migration:
- password_reset_token_hash (nullable, indexed)
- password_reset_token_expires_at (nullable)
"""

from alembic import op
import sqlalchemy as sa

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


def upgrade() -> None:
    """Execute the idempotent SQL (additive, IF NOT EXISTS)."""
    op.execute(sa.text(UPGRADE_SQL))


def downgrade() -> None:
    """Reverse the additive changes using the existing DOWNGRADE_SQL constant."""
    op.execute(sa.text(DOWNGRADE_SQL))
