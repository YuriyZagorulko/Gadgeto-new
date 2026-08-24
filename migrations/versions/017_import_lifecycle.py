"""017: Import job lifecycle & progress tracking.

Improves import-job observability and lifecycle control:

- Persistent progress counters as real columns (total/processed/created/
  updated/skipped/failed) instead of only the JSON blob.
- heartbeat_at / last_activity_at timestamps for stale-job detection.
- current_item (SKU) for the admin UI.
- error_count / warning_count.
- cancel_requested flag for safe cooperative cancellation.
- New statuses: STALE, CANCELLED.
- Missing indexes on import_jobs(status, heartbeat_at) and
  import_logs(created_at).

The migration is idempotent (IF NOT EXISTS wherever possible).
"""

from alembic import op

revision: str = "017_import_lifecycle"
down_revision: str = "016_pricing_rules"
branch_labels = None
depends_on = None

_NEW_JOB_COLUMNS = [
    ("heartbeat_at", "TIMESTAMP"),
    ("last_activity_at", "TIMESTAMP"),
    ("total_count", "INTEGER DEFAULT 0"),
    ("processed_count", "INTEGER DEFAULT 0"),
    ("created_count", "INTEGER DEFAULT 0"),
    ("updated_count", "INTEGER DEFAULT 0"),
    ("skipped_count", "INTEGER DEFAULT 0"),
    ("failed_count", "INTEGER DEFAULT 0"),
    ("error_count", "INTEGER DEFAULT 0"),
    ("warning_count", "INTEGER DEFAULT 0"),
    ("current_item", "VARCHAR(255)"),
    ("cancel_requested", "BOOLEAN DEFAULT FALSE"),
]


def upgrade() -> None:
    for column, ddl in _NEW_JOB_COLUMNS:
        op.execute(f"ALTER TABLE import_jobs ADD COLUMN IF NOT EXISTS {column} {ddl}")

    op.execute("ALTER TYPE importjobstatus ADD VALUE IF NOT EXISTS 'STALE'")
    op.execute("ALTER TYPE importjobstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    op.execute("CREATE INDEX IF NOT EXISTS ix_import_jobs_status ON import_jobs (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_import_jobs_heartbeat_at ON import_jobs (heartbeat_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_import_logs_created_at ON import_logs (created_at)")

    op.execute(
        """
        UPDATE import_jobs SET
          total_count = COALESCE((progress_json::jsonb ->> 'total')::int, 0),
          processed_count = COALESCE((progress_json::jsonb ->> 'processed')::int, 0),
          created_count = COALESCE((progress_json::jsonb ->> 'created')::int, 0),
          updated_count = COALESCE((progress_json::jsonb ->> 'updated')::int, 0),
          skipped_count = COALESCE((progress_json::jsonb ->> 'skipped')::int, 0),
          failed_count = COALESCE((progress_json::jsonb ->> 'failed')::int, 0),
          heartbeat_at = updated_at,
          last_activity_at = updated_at
        WHERE progress_json IS NOT NULL AND progress_json <> ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_import_logs_created_at")
    op.execute("DROP INDEX IF EXISTS ix_import_jobs_heartbeat_at")
    op.execute("DROP INDEX IF EXISTS ix_import_jobs_status")
    for column, _ in _NEW_JOB_COLUMNS:
        op.execute(f"ALTER TABLE import_jobs DROP COLUMN IF EXISTS {column}")
    # STALE/CANCELLED enum values are intentionally NOT dropped (removing enum
    # values would require a destructive type recreation).
