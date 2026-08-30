"""039: Widen product_attributes.value_text to VARCHAR(500).

Four DC-Link power-supply products carry a legitimate ~330-character
cable-length specification ("Довжина кабеля") that exceeds the previous
VARCHAR(255) limit on product_attributes.value_text.

Phase 7.2 widened attribute_values.value to VARCHAR(500) but missed
product_attributes.value_text — closing that gap.

Only product_attributes.value_text is changed. No other columns, indexes,
constraints, or tables are touched.

Downgrade guarded: if any value_text longer than 255 chars exists,
downgrade raises instead of truncating data.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "039_product_attributes_value_text_500"
down_revision: str = "038_attribute_values_value_500"


def upgrade() -> None:
    op.alter_column(
        "product_attributes",
        "value_text",
        existing_type=sa.VARCHAR(255),
        type_=sa.VARCHAR(500),
        existing_nullable=True,
    )


def downgrade() -> None:
    conn = op.get_bind()
    overlong = conn.execute(
        sa.text("SELECT count(*) FROM product_attributes WHERE length(value_text) > 255")
    ).scalar()
    if overlong:
        raise RuntimeError(
            f"downgrade unsafe: {overlong} product_attributes rows exceed 255 chars; "
            "reducing to VARCHAR(255) would destroy data. Leave at VARCHAR(500)."
        )
    op.alter_column(
        "product_attributes",
        "value_text",
        existing_type=sa.VARCHAR(500),
        type_=sa.VARCHAR(255),
        existing_nullable=True,
    )