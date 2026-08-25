"""025: Map remaining safe IT-Link value mappings.

Maps all remaining unmapped supplier values to existing internal attribute
values that are exact semantic matches.  Covers 43 values across 6 supplier
attributes.

Safe-to-map categories (from audit):
  - Формфактор (SA#11018) -> #172 Форм-фактор  - 8 exact matches
  - Кількість у ящику, шт (SA#10429) -> #167 Кількість  - 10 exact matches
  - Кількість у коробці, шт (SA#10785) -> #167 Кількість  - 10 exact matches
  - Інтерфейсні роз'єми (SA#10783) -> #173 Інтерфейси  - 13 exact matches
  - Кількість портов (SA#11010) -> #171 Кількість портів  - 1 exact match
  - Цвет (SA#11017) -> #168 Колір  - 1 case-normalization match

Preserves:
  - All existing mappings from migrations 022, 023, 024
  - All attribute_values (no new values created)
  - All products, product_attributes, suppliers, brands, categories

Revision ID: 025_safe_value_mappings
Revises: 024_lowercase_temno_siriy
"""
from alembic import op
import sqlalchemy as sa

revision: str = "025_safe_value_mappings"
# (supplier_attribute_id, supplier_value, internal_value_id)
MAPPINGS = [
    # -- Формфактор (SA#11018) -> #172 Форм-фактор --
    (11018, "E-ATX/ATX/M-ATX/Mini-ITX",                                     365),
    (11018, "PS2",                                                            363),
    (11018, "ITX/Micro-ATX/ATX/ATX(Rear Connector)/Micro-ATX(Rear Connector)", 367),
    (11018, "ATX/MicroATX/Mini ITX",                                          364),
    (11018, "ATX/microATX/EATX/Mini-ITX",                                     366),
    (11018, "mini ITX/microATX",                                              362),
    (11018, "ITX/Micro-ATX/Micro-ATX(Rear Connector)",                        369),
    (11018, "ATX/M-ATX/ITX/BTF",                                              368),
    # -- Кількість у ящику, шт (SA#10429) -> #167 Кількість --
    (10429, "12шт. в коробці",    23),
    (10429, "8шт. в коробці",     24),
    (10429, "24 шт. в коробці",   22),
    (10429, "6шт. в коробці",     25),
    (10429, "9 шт. в коробці",    26),
    (10429, "18шт. в коробці",    29),
    (10429, "36 шт. в коробці",   27),
    (10429, "20шт. в коробці",    18),
    (10429, "4 шт. в коробці",    32),
    (10429, "40 шт. в коробці",   34),
    # -- Кількість у коробці, шт (SA#10785) -> #167 Кількість --
    (10785, "40шт. в коробці",    20),
    (10785, "30шт. в коробці",    21),
    (10785, "36шт.в коробці",     19),
    (10785, "20шт. в коробці",    18),
    (10785, "96шт. в коробці",    17),
    (10785, "16шт. в коробці",    33),
    (10785, "32шт. в коробці",    30),
    (10785, "48 шт в коробці",    28),
    (10785, "80шт в коробці",     44),
    (10785, "60шт.в коробці",     31),
    # -- Інтерфейсні роз'єми (SA#10783) -> #173 Інтерфейси --
    (10783, "2*USB3.0, 1*USB2.0, HDAudio",             6234),
    (10783, "1*USB3.0,1*USB2.0,Audiox1",               6229),
    (10783, "USB3.0х2/Gen2 Type-Cх1/Audio/Micх1",       413),
    (10783, "2*USB3.0, HDAudio",                        411),
    (10783, "2*USB3.0, 1xHDAudio,1xMic",                6235),
    (10783, "1*USB3.0, 1*USB2.0, HDAudio",              6228),
    (10783, "1*USB3.0, 2*USB2.0, HDAudio",              405),
    (10783, "USB3.0x2, USB3.1(type-C)x1, Audiox1",      6260),
    (10783, "1*USB3.0, 1*USB2.0, 1*Type-C",             6227),
    (10783, "2*USB2.0/1*USB3.0",                        410),
    (10783, "2*USB3.0, Audiox1/Micx1",                  408),
    (10783, "USB3.0*1",                                  409),
    (10783, "1*USB3.1, *USB3.1 Type-C,2xHDAudio",       6230),
    # -- Кількість портов (SA#11010) -> #171 Кількість портів --
    (11010, "2xRS232(COM)",                              330),
    # -- Цвет (SA#11017) -> #168 Колір (case normalization) --
    (11017, "сріблястий",                                134),
]
down_revision: str = "024_lowercase_temno_siriy"
branch_labels = None
def upgrade() -> None:
    conn = op.get_bind()
    created_val = 0
    existing_val = 0
    created_map = 0
    existing_map = 0

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
            created_val += 1
            val_action = "created"
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
            existing_val += 1
            val_action = "already existed"

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
        if row2:
            created_map += 1
            map_action = "created"
        else:
            existing_map += 1
            map_action = "already existed"

        print(f"  SA#{sa_id} '{s_value}' -> AV#{av_id}: value {val_action}, mapping {map_action}")

    print(f"SUMMARY: supplier_values created={created_val}, existed={existing_val}")
    print(f"         mappings created={created_map}, existed={existing_map}")


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
depends_on = None