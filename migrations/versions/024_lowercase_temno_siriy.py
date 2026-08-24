"""024: Add missing lowercase "темно-сірий" mapping under SA#10667 Колір.

Supplier SA#10667 (Колір) already had a mapping for capitalized "Темно-сірий"
(value ID 144), but the IT-Link feed supplies the value in lowercase
"темно-сірий". Since the MappingResolver uses exact string comparison, the
lowercase variant needs its own supplier_attribute_values row.

Also maps remaining unmapped values that now have exact existing internal
targets (post-fix of mapping_resolver.py key constructor bug):

  SA#10429 (Кількість у ящику, шт) → "6шт в коробці"  → ID 25 (already done)
  SA#10429 (Кількість у ящику, шт) → "4шт в коробці"  → ID 32 (already done)
  SA#10667 (Колір)                  → "темно-сірий"     → ID 144  ← NEW

Revision ID: 024_lowercase_temno_siriy
Revises: 023_seriy_to_siriy
"""
from alembic import op
import sqlalchemy as sa

revision: str = "024_lowercase_temno_siriy"
down_revision: str = "023_seriy_to_siriy"
branch_labels = None
depends_on = None

# SA#10667 (Колір), supplier_value "темно-сірий" → attribute_value_id 144 ("Темно-сірий")
SA_ID = 10667
SUPPLIER_VALUE = "темно-сірий"
INTERNAL_VALUE_ID = 144


def upgrade() -> None:
    conn = op.get_bind()

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
    msg = "created" if row or row2 else "already existed"
    print(f"  SA#{SA_ID} '{SUPPLIER_VALUE}' → AV#{INTERNAL_VALUE_ID}: {msg}")


def downgrade() -> None:
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