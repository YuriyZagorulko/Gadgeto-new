"""030: Channel publication foundation.

Creates the channel layer required to publish catalog products onto external
marketplaces (first: Rozetka) WITHOUT touching the master catalog schema:

  channels, channel_settings, channel_listings,
  channel_validation_issues, sync_runs, sync_jobs, sync_logs

Seeds the first channel row (code='rozetka').  The supplier importer mapping
tables are intentionally NOT reused or modified here.

Listing state is split into two axes (publication_status x sync_status) so a
published product whose latest update failed can be represented correctly.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "030_channel_publication_foundation"
down_revision: str = "029_consolidate_duplicate_values"

# ── Enums (labels are uppercase member NAMES, same convention as userrole /
#    productstatus / importjobstatus) ──────────────────────────────────────────

publication_status = sa.Enum(
    "DISABLED", "DRAFT", "READY", "PUBLISHED",
    name="channelpublicationstatus",
)
sync_status = sa.Enum(
    "IDLE", "SYNCING", "SUCCESS", "ERROR",
    name="channelsyncstatus",
)
run_type = sa.Enum(
    "MANUAL", "SCHEDULED", "FULL", "DELTA", "VALIDATION", "TAXONOMY",
    name="syncruntype",
)
run_status = sa.Enum(
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "PARTIAL", "CANCELLED",
    name="syncrunstatus",
)
job_operation = sa.Enum(
    "PUBLISH", "UPDATE", "PRICE_STOCK", "UNPUBLISH", "FULL",
    name="syncjoboperation",
)
job_status = sa.Enum(
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED",
    name="syncjobstatus",
)
job_error_type = sa.Enum(
    "NETWORK", "TIMEOUT", "RATE_LIMIT", "SERVER_5XX",
    "AUTH", "VALIDATION", "MAPPING", "INVALID_DATA",
    name="syncjoberrortype",
)
log_level = sa.Enum(
    "INFO", "WARNING", "ERROR", "DEBUG",
    name="syncloglevel",
)

_ALL_ENUMS = (
    publication_status, sync_status, run_type, run_status,
    job_operation, job_status, job_error_type, log_level,
)


def upgrade() -> None:
    # ── channels ────────────────────────────────────────────────────────────
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("adapter_config_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_channel_code"),
    )
    op.create_index(op.f("ix_channels_code"), "channels", ["code"], unique=True)

    # ── channel_settings ───────────────────────────────────────────────────
    op.create_table(
        "channel_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "key", name="uq_channel_setting"),
    )

    # ── channel_listings ───────────────────────────────────────────────────
    op.create_table(
        "channel_listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("publication_status", publication_status, nullable=False,
                  server_default="DRAFT"),
        sa.Column("sync_status", sync_status, nullable=False, server_default="IDLE"),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("commercial_hash", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_type", sa.String(length=50), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("remote_status", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "channel_id", name="uq_channel_listing"),
    )
    op.create_index(op.f("ix_channel_listings_external_id"), "channel_listings",
                    ["external_id"], unique=False)
    op.create_index("ix_channel_listings_channel_publication", "channel_listings",
                    ["channel_id", "publication_status"], unique=False)
    op.create_index("ix_channel_listings_channel_sync", "channel_listings",
                    ["channel_id", "sync_status"], unique=False)

    # ── channel_validation_issues ──────────────────────────────────────────
    op.create_table(
        "channel_validation_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["channel_listings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "code", name="uq_channel_validation_issue"),
    )

    # ── sync_runs ──────────────────────────────────────────────────────────
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("run_type", run_type, nullable=False, server_default="MANUAL"),
        sa.Column("status", run_status, nullable=False, server_default="QUEUED"),
        sa.Column("total_count", sa.Integer(), server_default="0"),
        sa.Column("processed_count", sa.Integer(), server_default="0"),
        sa.Column("created_count", sa.Integer(), server_default="0"),
        sa.Column("updated_count", sa.Integer(), server_default="0"),
        sa.Column("failed_count", sa.Integer(), server_default="0"),
        sa.Column("skipped_count", sa.Integer(), server_default="0"),
        sa.Column("progress_json", sa.Text(), nullable=True),
        sa.Column("current_stage", sa.String(length=255), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_channel_status", "sync_runs",
                    ["channel_id", "status"], unique=False)
    op.create_index("ix_sync_runs_created_at", "sync_runs", ["created_at"],
                    unique=False)

    # ── sync_jobs ──────────────────────────────────────────────────────────
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("operation", job_operation, nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="QUEUED"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("error_type", job_error_type, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["sync_runs.id"]),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["channel_listings.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_jobs_status_next_retry", "sync_jobs",
                    ["status", "next_retry_at"], unique=False)
    op.create_index("ix_sync_jobs_run", "sync_jobs", ["run_id"], unique=False)
    op.create_index("ix_sync_jobs_listing", "sync_jobs", ["listing_id"], unique=False)
    op.create_index("ix_sync_jobs_product", "sync_jobs", ["product_id"], unique=False)

    # ── sync_logs ──────────────────────────────────────────────────────────
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("level", log_level, nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["sync_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_logs_job"), "sync_logs", ["job_id"], unique=False)

    # ── seed: first channel (identified by stable code, never by id) ───────
    op.execute(
        """
        INSERT INTO channels (code, name, is_enabled, created_at, updated_at)
        VALUES ('rozetka', 'Rozetka', FALSE, NOW(), NOW())
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("sync_logs")
    op.drop_table("sync_jobs")
    op.drop_table("sync_runs")
    op.drop_table("channel_validation_issues")
    op.drop_table("channel_listings")
    op.drop_table("channel_settings")
    op.drop_table("channels")

    for enum_obj in _ALL_ENUMS:
        enum_obj.drop(op.get_bind(), checkfirst=True)