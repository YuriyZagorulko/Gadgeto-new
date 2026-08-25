"""027: Add is_supplier_image and is_suppressed columns to product_images.

Supports administrator-controlled suppression of supplier-provided product images.

- ``is_supplier_image`` (bool): marks images imported from supplier feeds
- ``is_suppressed`` (bool): marks images that admin has hidden from storefront

Both columns default to FALSE for backward compatibility.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "027_supplier_image_suppression"
down_revision: str = "026_itlink_remaining_exact_values"


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column("is_supplier_image", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "product_images",
        sa.Column("is_suppressed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_index(
        "ix_product_images_active",
        "product_images",
        ["product_id", "is_suppressed"],
        postgresql_where=sa.text("is_suppressed = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_product_images_active", table_name="product_images")
    op.drop_column("product_images", "is_suppressed")
    op.drop_column("product_images", "is_supplier_image")
