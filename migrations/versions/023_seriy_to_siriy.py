"""023: Map IT-Link Колір "серый" to existing Сірий.

Russian "серый" → Ukrainian "Сірий" (ID 132) under SA#10667 Колір.
Semantically identical color value, language normalization only.

Changes:
  - Insert supplier_attribute_values row for "серый" under SA#10667
  - Insert attribute_value_mapping linking to attribute_value_id 132

Preserves:
  - All existing mappings from migration 022
  - All attribute_values (no new values created)
  - All products, product_attributes, suppliers, brands, categories

Revision ID: 023_seriy_to_siriy
Revises: 022_itlink_value_mappings
"""
from alembic import op
import sqlalchemy as sa

revision: str = "023_seriy_to_siriy"
down_revision: str = "022_itlink_value_mappings"
branch_labels = None
depends_on = None

# SA#10667 (Колір), supplier_value "серый" → attribute_value_id 132 ("Сірий")
SA_ID = 10667
SUPPLIER_VALUE = "серый"
INTERNAL_VALUE_ID = 132


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: create supplier_attribute_values row
    result = conn.execute(
        sa.text(
            """INSERT INTO supplier_attribute_values
               (supplier_attribute_id, supplier_value, is_removed,
                created_at, updated_at)
               VALUES (:sa_id, :s_value, FALSE, NOW(), NOW())
               ON CONFLICT (supplier_attribute_id, supplier_value)
               DO NOTHING
               RETURNING id"""
        ),
        {"sa_id": SA_ID, "s_value": SUPPLIER_VALUE},
    )
    row = result.fetchone()
    if row:
        sav_id = row[0]
    else:
        row2 = conn.execute(
            sa.text(
                """SELECT id FROM supplier_attribute_values
                   WHERE supplier_attribute_id = :sa_id
                     AND supplier_value = :s_value"""
            ),
            {"sa_id": SA_ID, "s_value": SUPPLIER_VALUE},
        ).fetchone()
        sav_id = row2[0]

    # Step 2: create the attribute_value_mapping
    result2 = conn.execute(
        sa.text(
            """INSERT INTO attribute_value_mappings
               (supplier_attribute_value_id, attribute_value_id,
                is_active, created_at, updated_at)
               VALUES (:sav_id, :av_id, TRUE, NOW(), NOW())
               ON CONFLICT (supplier_attribute_value_id)
               DO NOTHING
               RETURNING id"""
        ),
        {"sav_id": sav_id, "av_id": INTERNAL_VALUE_ID},
    )
    row2 = result2.fetchone()
    if row2:
        print(f"  SA#{SA_ID} '{SUPPLIER_VALUE}' → AV#{INTERNAL_VALUE_ID}: created")
    else:
        print(f"  SA#{SA_ID} '{SUPPLIER_VALUE}' → AV#{INTERNAL_VALUE_ID}: already existed")


def downgrade() -> None:
    """Remove the mapping and supplier_attribute_value added in upgrade."""
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            """SELECT id FROM supplier_attribute_values
               WHERE supplier_attribute_id = :sa_id
                 AND supplier_value = :s_value"""
        ),
        {"sa_id": SA_ID, "s_value": SUPPLIER_VALUE},
    ).fetchone()
    if row is not None:
        sav_id = row[0]
        conn.execute(
            sa.text(
                """DELETE FROM attribute_value_mappings
                   WHERE supplier_attribute_value_id = :sav_id"""
            ),
            {"sav_id": sav_id},
        )
        conn.execute(
            sa.text(
                """DELETE FROM supplier_attribute_values WHERE id = :sav_id"""
            ),
            {"sav_id": sav_id},
        )
        print(f"  Removed SA#{SA_ID} '{SUPPLIER_VALUE}'")