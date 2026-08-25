"""008: Add user_id to reviews for storefront submissions.

Additive-only migration. Existing reviews are unaffected.
"""
from alembic import op
import sqlalchemy as sa

revision: str = '008_review_user'
down_revision: str = '007_product_editor'

UPGRADE_SQL = """
ALTER TABLE product_reviews
    ADD COLUMN IF NOT EXISTS user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_product_reviews_status ON product_reviews(status);
"""


def upgrade() -> None:
    """Execute the idempotent SQL (additive, IF NOT EXISTS)."""
    op.execute(sa.text(UPGRADE_SQL))


def downgrade() -> None:
    """Historically this was a manual additive migration with no defined
    rollback.  The columns and indexes added here are now depended upon by
    later migrations and application code.  Rollback is intentionally not
    implemented."""
    pass