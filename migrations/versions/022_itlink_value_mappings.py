"""022: Add IT-Link attribute value mappings for approved unmapped values.

High-confidence value mappings from the audit report.  These link existing
supplier attribute values that appear in the IT-Link feed but have no active
value-level mapping to the correct internal attribute_values.

Changes:
  - Insert missing supplier_attribute_values rows for approved values
  - Insert attribute_value_mappings rows for those values

Preserves:
  - All existing attribute_mappings (already active)
  - All existing attribute_value_mappings
  - All attribute_values (no new values created)
  - All products, product_attributes, suppliers, brands, categories

Revision ID: 022_itlink_value_mappings
Revises: 021_clean_historical_catchall_attrs
"""
from alembic import op
import sqlalchemy as sa

revision: str = "022_itlink_value_mappings"
down_revision: str = "021_clean_historical_catchall_attrs"
branch_labels = None
depends_on = None
# ---------------------------------------------------------------------------
# Mapping data: (supplier_attribute_id, supplier_value, internal_value_id)
# ---------------------------------------------------------------------------
# 1. Кількість у ящику, шт (10429) → Кількість (167)
#     "6шт в коробці"   → value id 25  ("6шт. в коробці")
#     "4шт в коробці"   → value id 32  ("4 шт. в коробці")
# 2. Колір (10667) → Колір (168)
#     "сірий"           → value id 132 ("Сірий")
# 3. Цвет (11017) → Колір (168)
#     "черный"          → value id 128 ("Чорний")
#     "белый"           → value id 129 ("Білий")
#     "темно-сірий"     → value id 144 ("Темно-сірий")
# 4. Формфактор (11018) → Форм-фактор (172)
#     "mini-ITX"        → value id 400 ("Mini-ITX")
# 5. Тип підшипника (11460) → Тип підшипника (166)
#     "Double BB"       → value id 13  ("подвійний кульковий (Dual Ball Bearing)")
# ---------------------------------------------------------------------------
MAPPINGS = [
    (10429, "6шт в коробці",  25),
    (10429, "4шт в коробці",  32),
    (10667, "сірий",          132),
    (11017, "черный",         128),
    (11017, "белый",          129),
    (11017, "темно-сірий",    144),
    (11018, "mini-ITX",       400),
    (11460, "Double BB",       13),
]


def upgrade() -> None:
    conn = op.get_bind()
    for sa_id, s_value, av_id in MAPPINGS:
        # Step 1: ensure supplier_attribute_value row exists
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
            {"sa_id": sa_id, "s_value": s_value},
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
                {"sa_id": sa_id, "s_value": s_value},
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
            {"sav_id": sav_id, "av_id": av_id},
        )
        row2 = result2.fetchone()
        msg = "created" if row or row2 else "already existed"
        print(f"  SA#{sa_id} '{s_value}' → AV#{av_id}: {msg}")


def downgrade() -> None:
    """Remove the mappings and supplier_attribute_values added in upgrade."""
    conn = op.get_bind()
    for sa_id, s_value, av_id in MAPPINGS:
        row = conn.execute(
            sa.text(
                """SELECT id FROM supplier_attribute_values
                   WHERE supplier_attribute_id = :sa_id
                     AND supplier_value = :s_value"""
            ),
            {"sa_id": sa_id, "s_value": s_value},
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
            print(f"  Removed SA#{sa_id} '{s_value}'")