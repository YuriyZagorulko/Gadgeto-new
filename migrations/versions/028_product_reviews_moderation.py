"""028: Product reviews moderation - unique constraint, moderation fields, status enum.

Additive-only migration. Existing reviews are unaffected.

Changes:
- Add moderated_at, moderated_by columns for moderation tracking
- Add unique constraint on (product_id, user_id) where user_id is not null
- Add index on created_at for sorting
- Migrate status values: 'published' -> 'APPROVED', 'pending' -> 'PENDING', 'hidden' -> 'REJECTED'
- Set default status to 'PENDING'
"""
from alembic import op
import sqlalchemy as sa

revision: str = '028_product_reviews_moderation'
down_revision: str = '041_catalog_sync_runs'


def upgrade() -> None:
    """Execute the idempotent SQL (additive, IF NOT EXISTS).
    
    Each statement is executed separately because PostgreSQL's asyncpg driver
    does not support multiple commands in a single prepared statement.
    """
    # Add moderation tracking columns
    op.execute(sa.text(
        "ALTER TABLE product_reviews "
        "ADD COLUMN IF NOT EXISTS moderated_at TIMESTAMP NULL, "
        "ADD COLUMN IF NOT EXISTS moderated_by INTEGER NULL REFERENCES users(id) ON DELETE SET NULL"
    ))

    # Add index on created_at for sorting
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_product_reviews_created_at "
        "ON product_reviews(created_at DESC)"
    ))

    # Add index on moderated_by for admin queries
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_product_reviews_moderated_by "
        "ON product_reviews(moderated_by)"
    ))

    # Add unique constraint: one review per user per product (only for authenticated users)
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_reviews_user_product "
        "ON product_reviews(product_id, user_id) "
        "WHERE user_id IS NOT NULL"
    ))

    # Migrate existing status values to new enum
    op.execute(sa.text("UPDATE product_reviews SET status = 'APPROVED' WHERE status = 'published'"))
    op.execute(sa.text("UPDATE product_reviews SET status = 'PENDING' WHERE status = 'pending'"))
    op.execute(sa.text("UPDATE product_reviews SET status = 'REJECTED' WHERE status = 'hidden'"))

    # Set default status to PENDING for new reviews
    op.execute(sa.text(
        "ALTER TABLE product_reviews ALTER COLUMN status SET DEFAULT 'PENDING'"
    ))


def downgrade() -> None:
    """Historically this was a manual additive migration with no defined
    rollback. The columns, indexes and constraints added here are now
    depended upon by application code. Rollback is intentionally not
    implemented."""
    pass
