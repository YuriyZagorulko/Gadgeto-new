"""042: Prom.ua channel + pricing infrastructure.

Prom.ua is prepared as a SECOND export channel mirroring the Rozetka
integration, but has NO credentials/API documentation yet.  This migration:

  1. Seeds the ``channels`` row with code='prom' (disabled) — the same
     generic channel tables (channel_settings, channel_listings,
     channel_external_*, channel_*_mappings, sync_runs, ...) are reused and
     are already channel-scoped via channel_id, so no mapping/list/run tables
     need duplication.
  2. Creates Prom.ua-specific pricing storage (``prom_pricing_imports`` /
     ``prom_category_pricing_rules``) mirroring the Rozetka pricing model so
     Prom.ua can eventually carry its own pricing rules independently from
     Rozetka.  NO Prom.ua commission/price rules are seeded or invented.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "042_prom_channel"
down_revision: str = "041_catalog_sync_runs"


def upgrade() -> None:
    # ── Seed the Prom.ua channel (disabled; identified by stable code) ─────
    op.execute(
        """
        INSERT INTO channels (code, name, is_enabled, created_at, updated_at)
        VALUES ('prom', 'Prom.ua', FALSE, NOW(), NOW())
        ON CONFLICT (code) DO NOTHING
        """
    )

    # ── Prom.ua pricing imports (future use) ────────────────────────────────
    op.create_table(
        "prom_pricing_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), server_default="PROCESSING", nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("categories_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rules_imported", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("errors_json", sa.Text(), nullable=True),
        sa.Column("imported_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Prom.ua category pricing rules (future use) ────────────────────────
    op.create_table(
        "prom_category_pricing_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("import_id", sa.Integer(),
                  sa.ForeignKey("prom_pricing_imports.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("external_category_id", sa.String(255), nullable=False, index=True),
        sa.Column("category_name", sa.String(500), nullable=False),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("price_min", sa.BigInteger(), nullable=True),
        sa.Column("price_max", sa.BigInteger(), nullable=True),
        sa.Column("commission_percent", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prom_pricing_rules_cat", "prom_category_pricing_rules",
                    ["external_category_id", "import_id"])


def downgrade() -> None:
    op.drop_table("prom_category_pricing_rules")
    op.drop_table("prom_pricing_imports")
    op.execute("DELETE FROM channels WHERE code='prom'")