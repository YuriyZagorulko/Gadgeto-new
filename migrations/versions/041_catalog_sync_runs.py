"""041: Catalog sync automation tables.

One top-level run represents a full automated cycle:

    run_catalog_sync → supplier import jobs → channel exports

Suppliers/export details stay in the existing import_jobs / sync_runs tables;
this table only tracks the run itself plus the refs (job ids / run ids) inside
progress_json.  catalog_sync_logs mirrors import_logs for user-facing messages.

Statuses are plain strings (RUNNING/SUCCEEDED/PARTIAL/FAILED/SKIPPED) — no new
PostgreSQL enum is introduced.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "041_catalog_sync_runs"
down_revision: str = "040_category_attribute_uniqueness"


def upgrade() -> None:
    op.create_table(
        "catalog_sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="RUNNING"),
        sa.Column("trigger", sa.String(length=20), nullable=False,
                  server_default="scheduler"),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("progress_json", sa.Text(), nullable=True),
        sa.Column("error_details_json", sa.Text(), nullable=True),
        sa.Column("lock_token", sa.String(length=64), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_sync_runs_status", "catalog_sync_runs", ["status"])
    op.create_index("ix_catalog_sync_runs_created_at", "catalog_sync_runs",
                    ["created_at"])

    op.create_table(
        "catalog_sync_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False,
                  server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_sync_logs_run_id", "catalog_sync_logs", ["run_id"])


def downgrade() -> None:
    op.drop_table("catalog_sync_logs")
    op.drop_table("catalog_sync_runs")