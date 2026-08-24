"""016: Pricing rules and USD rate configuration.

Creates the markup_rules table for tiered category-aware pricing.
The USD/UAH exchange rate is stored in the existing `settings` table
(seed the default value here as well).
"""

from alembic import op
import sqlalchemy as sa

revision: str = "016_pricing_rules"
down_revision: str = "015_import_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "markup_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_code", sa.String(50), nullable=False, server_default="*"),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("price_threshold", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Float(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_markup_rules_supplier_code"),
        "markup_rules",
        ["supplier_code"],
    )
    op.create_index(
        op.f("ix_markup_rules_category_id"),
        "markup_rules",
        ["category_id"],
    )

    # Seed the default USD rate in the settings table
    op.execute(
        "INSERT INTO settings (key, value, is_secret) VALUES ('import_usd_rate', '44.3', FALSE)"
        " ON CONFLICT (key) DO NOTHING"
    )

    # Seed the default global markup rules (legacy DC-Link defaults)
    op.execute("""
        INSERT INTO markup_rules (supplier_code, category_id, price_threshold, multiplier, sort_order, is_active)
        VALUES
            ('*', NULL, 200, 1.50, 200, TRUE),
            ('*', NULL, 500, 1.45, 500, TRUE),
            ('*', NULL, 1000, 1.40, 1000, TRUE),
            ('*', NULL, 3000, 1.35, 3000, TRUE),
            ('*', NULL, 7000, 1.30, 7000, TRUE),
            ('*', NULL, 15000, 1.25, 15000, TRUE),
            ('*', NULL, 999999999, 1.20, 999999999, TRUE)
    """)


def downgrade() -> None:
    op.drop_index(op.f("ix_markup_rules_category_id"), table_name="markup_rules")
    op.drop_index(op.f("ix_markup_rules_supplier_code"), table_name="markup_rules")
    op.drop_table("markup_rules")
    op.execute("DELETE FROM settings WHERE key = 'import_usd_rate'")