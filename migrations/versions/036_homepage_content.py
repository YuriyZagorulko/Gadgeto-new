"""036: Homepage content — slider slides and recommended products.

Creates two tables for the Admin → Content → Головна сторінка CMS:
  - homepage_slides
  - homepage_recommended_products
"""

import sqlalchemy as sa
from alembic import op

revision: str = "036_homepage_content"
down_revision: str = "035_normalize_product_attribute_values"


def upgrade() -> None:
    # ── Homepage slider slides ──────────────────────────────────────────────
    op.create_table(
        "homepage_slides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("image", sa.String(500), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("subtitle", sa.String(500), nullable=True),
        sa.Column("button_text", sa.String(255), nullable=True),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_homepage_slides_active_sort", "homepage_slides",
                    ["is_active", "sort_order"])

    # ── Homepage recommended products ───────────────────────────────────────
    op.create_table(
        "homepage_recommended_products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", name="uq_homepage_recommended_product"),
    )
    op.create_index("ix_homepage_recommended_sort", "homepage_recommended_products",
                    ["sort_order"])


def downgrade() -> None:
    op.drop_table("homepage_recommended_products")
    op.drop_table("homepage_slides")