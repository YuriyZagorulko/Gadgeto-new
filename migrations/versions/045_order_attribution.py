"""045: Order traffic-source attribution columns.

Adds first-touch and latest/session attribution to `orders` so the admin
panel can show where each order came from without querying GA4:

  first_source / first_medium / first_campaign / first_term / first_content /
  first_landing_page / first_gclid
  last_source / last_medium / last_campaign / last_term / last_content /
  last_landing_page / last_gclid

All columns are NULLABLE: missing attribution must never break order
creation. Pure DDL, no existing rows are modified.

Revision ID: 045_order_attribution
Revises: 044_supplier_external_ids
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "045_order_attribution"
down_revision: str = "044_supplier_external_ids"
branch_labels = None
depends_on = None


_ATTRIBUTION_COLUMNS = (
    # (name, length)
    ("first_source", 100),
    ("first_medium", 100),
    ("first_campaign", 255),
    ("first_term", 255),
    ("first_content", 255),
    ("first_landing_page", 500),
    ("first_gclid", 255),
    ("last_source", 100),
    ("last_medium", 100),
    ("last_campaign", 255),
    ("last_term", 255),
    ("last_content", 255),
    ("last_landing_page", 500),
    ("last_gclid", 255),
)


def upgrade() -> None:
    for name, length in _ATTRIBUTION_COLUMNS:
        op.add_column(
            "orders",
            sa.Column(name, sa.String(length=length), nullable=True),
        )
    op.create_index(
        "ix_orders_first_source", "orders", ["first_source"], unique=False
    )
    op.create_index(
        "ix_orders_last_source", "orders", ["last_source"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_orders_last_source", table_name="orders")
    op.drop_index("ix_orders_first_source", table_name="orders")
    for name, _ in _ATTRIBUTION_COLUMNS:
        op.drop_column("orders", name)
