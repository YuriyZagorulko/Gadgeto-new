"""037: Rozetka category-based pricing/commission rules.

Creates tables for uploading and managing Rozetka commission rules from
the Excel price file.  Commission is Rozetka's share of the selling price
(e.g. 18% means Rozetka keeps 18%, seller receives 82%).
"""

import sqlalchemy as sa
from alembic import op

revision: str = "037_rozetka_pricing_rules"
down_revision: str = "036_homepage_content"


def upgrade() -> None:
    # ── Import versions ─────────────────────────────────────────────────────
    op.create_table(
        "rozetka_pricing_imports",
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

    # ── Category pricing rules ──────────────────────────────────────────────
    op.create_table(
        "rozetka_category_pricing_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("import_id", sa.Integer(), sa.ForeignKey("rozetka_pricing_imports.id", ondelete="CASCADE"),
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
    op.create_index("ix_rozetka_pricing_rules_cat", "rozetka_category_pricing_rules",
                    ["external_category_id", "import_id"])


def downgrade() -> None:
    op.drop_table("rozetka_category_pricing_rules")
    op.drop_table("rozetka_pricing_imports")