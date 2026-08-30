"""038: Widen attribute_values.value to VARCHAR(500).

DC-Link supplies a legitimate 330-character PSU cable-length specification
(SAV 24353, attribute "Довжина" id=179) that exceeds the previous
VARCHAR(255) limit. Human decision (Phase 7.2) chose a bounded widening:

    VARCHAR(255) -> VARCHAR(500)

instead of unrestricted TEXT, retaining protection against arbitrarily large
or malformed payloads.

Only `attribute_values.value` is changed. No other columns, indexes,
constraints, or tables are touched.

Downgrade note: unique constraint (attribute_id, value) and index
dependencies are not affected by the width change. However, if any
attribute_value longer than 255 chars exists (e.g. the Phase 7.2
DC-Link value), downgrading back to VARCHAR(255) would destroy data,
therefore downgrade raises explicitly instead of truncating.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "038_attribute_values_value_500"
down_revision: str = "037_rozetka_pricing_rules"


def upgrade() -> None:
    op.alter_column(
        "attribute_values",
        "value",
        existing_type=sa.VARCHAR(255),
        type_=sa.VARCHAR(500),
        existing_nullable=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    overlong = conn.execute(
        sa.text("SELECT count(*) FROM attribute_values WHERE length(value) > 255")
    ).scalar()
    if overlong:
        raise RuntimeError(
            f"downgrade unsafe: {overlong} attribute_values exceed 255 chars; "
            "reducing to VARCHAR(255) would destroy data. Leave at VARCHAR(500)."
        )
    op.alter_column(
        "attribute_values",
        "value",
        existing_type=sa.VARCHAR(500),
        type_=sa.VARCHAR(255),
        existing_nullable=False,
    )