"""026: Create 3 missing internal attribute_values and their mappings.

Creates new internal attribute_values for 3 supplier values that currently
have no exact existing target.  These are exact, non-approximate values.

New values:
  - #176 Матеріал радіатора: "алюм. + 7 6мм теплових трубок"
  - #176 Матеріал радіатора: "мідь+4 теплов.трубки"
  - #175 Максимальна довжина відеокарти: "до 449 мм"

Preserves:
  - All existing mappings from migrations 022, 023, 024, 025
  - All existing attribute_values (only adds new ones)
  - All products, product_attributes, suppliers, brands, categories

Revision ID: 026_itlink_remaining_exact_values
Revises: 025_safe_value_mappings
"""
from alembic import op
import sqlalchemy as sa

revision: str = "026_itlink_remaining_exact_values"
down_revision: str = "025_safe_value_mappings"
# New values to create: (attribute_id, value, slug)
NEW_VALUES = [
    (176, "алюм. + 7 6мм теплових трубок", "алюм- - 7-6мм-теплових-трубок"),
    (176, "мідь+4 теплов.трубки", "мідь-4-теплов-трубки"),
    (175, "до 449 мм", "до-449-мм"),
]

# Corresponding mappings: (supplier_attribute_id, supplier_value, expected_internal_value)
MAPPINGS = [
    (11381, "алюм. + 7 6мм теплових трубок", "алюм. + 7 6мм теплових трубок"),
    (11381, "мідь+4 теплов.трубки", "мідь+4 теплов.трубки"),
    (10742, "до 449 мм", "до 449 мм"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: create new attribute_values
    for attr_id, value, slug in NEW_VALUES:
        row = conn.execute(
            sa.text(
                "SELECT id FROM attribute_values WHERE attribute_id = :aid AND value = :val"
            ),
            {"aid": attr_id, "val": value},
        ).fetchone()
        if row:
            av_id = row[0]
            print(f"  AV already exists: #{attr_id} '{value}' (id={av_id})")
        else:
            result = conn.execute(
                sa.text(
                    """INSERT INTO attribute_values
                       (attribute_id, value, slug, sort, is_active,
                        created_at, updated_at)
                       VALUES (:aid, :val, :slug, 0, TRUE, NOW(), NOW())
                       RETURNING id"""
                ),
                {"aid": attr_id, "val": value, "slug": slug},
            )
            av_id = result.fetchone()[0]
            print(f"  Created AV #{attr_id} '{value}' (id={av_id})")

    # Step 2: create supplier_attribute_values + mappings
    for sa_id, s_value, av_value in MAPPINGS:
        # Find the internal attribute_value id
        attr_row = conn.execute(
            sa.text(
                "SELECT attribute_id FROM attribute_mappings WHERE supplier_attribute_id = :sa_id"
            ),
            {"sa_id": sa_id},
        ).fetchone()
        if not attr_row:
            print(f"  ERROR: No attribute_mapping for SA#{sa_id}")
            continue
        attr_id = attr_row[0]
        av_row = conn.execute(
            sa.text(
                "SELECT id FROM attribute_values WHERE attribute_id = :aid AND value = :val"
            ),
            {"aid": attr_id, "val": av_value},
        ).fetchone()
        if not av_row:
            print(f"  ERROR: Could not find attribute_value '{av_value}' for attr #{attr_id}")
            continue
        av_id = av_row[0]

        # Create supplier_attribute_value
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
                    "SELECT id FROM supplier_attribute_values WHERE supplier_attribute_id = :sa_id AND supplier_value = :s_value"
                ),
                {"sa_id": sa_id, "s_value": s_value},
            ).fetchone()
            sav_id = row2[0]

        # Create attribute_value_mapping
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
        action = "created" if row2 else "already existed"
        print(f"  SA#{sa_id} '{s_value}' -> AV#{av_id} '{av_value}': {action}")


def downgrade() -> None:
    """Remove the mappings, supplier_values, and attribute_values added in upgrade."""
    conn = op.get_bind()

    for sa_id, s_value, av_value in MAPPINGS:
        row = conn.execute(
            sa.text(
                "SELECT id FROM supplier_attribute_values WHERE supplier_attribute_id = :sa_id AND supplier_value = :s_value"
            ),
            {"sa_id": sa_id, "s_value": s_value},
        ).fetchone()
        if row is not None:
            sav_id = row[0]
            conn.execute(
                sa.text("DELETE FROM attribute_value_mappings WHERE supplier_attribute_value_id = :sav_id"),
                {"sav_id": sav_id},
            )
            conn.execute(
                sa.text("DELETE FROM supplier_attribute_values WHERE id = :sav_id"),
                {"sav_id": sav_id},
            )
            print(f"  Removed SA#{sa_id} '{s_value}'")

    for attr_id, value, slug in NEW_VALUES:
        conn.execute(
            sa.text("DELETE FROM attribute_values WHERE attribute_id = :aid AND value = :val"),
            {"aid": attr_id, "val": value},
        )
        print(f"  Removed AV #{attr_id} '{value}'")
branch_labels = None
depends_on = None