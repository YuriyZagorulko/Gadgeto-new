"""033: Add 'EXPORT' to the sync_runs.run_type enum.

Phase 6.3 introduces background Rozetka product-export runs.  Reusing the
existing `sync_runs` table (run_type = 'EXPORT') keeps the export history,
progress and cancel infrastructure unified with taxonomy runs.

PostgreSQL enum values are appended via `ALTER TYPE ... ADD VALUE`, which is
transaction-safe.  `run_type = 'EXPORT'` follows the SyncRunType model values
(MANUAL, SCHEDULED, FULL, DELTA, VALIDATION, TAXONOMY) already present.

NOT starting a transaction: PostgreSQL forbids ADD VALUE inside a
transaction block, so this migration commits the value immediately.
"""

from alembic import op

revision: str = "033_channel_export"
down_revision: str = "032_channel_mappings"


def upgrade() -> None:
    op.execute("ALTER TYPE syncruntype ADD VALUE IF NOT EXISTS 'EXPORT'")


def downgrade() -> None:
    # PostgreSQL cannot remove a value from an enum without expensive
    # rewrites.  Once 'EXPORT' has been used it cannot be dropped safely,
    # so downgrade is intentionally a no-op.
    pass