"""029: Consolidate 16 case-only duplicate internal attribute values.

Pre-existing duplicates found during DC-Link mapping audit. All are in the
"Колір" (color) attribute except one in "Процесор" (processor).

Strategy:
  1. For each duplicate with a value mapping: redirect the mapping to the
     canonical value (UPDATE attribute_value_mappings.attribute_value_id).
  2. Delete the obsolete duplicate value from attribute_values.

All 16 duplicates have 0 product_attributes references, so no product data
migration is needed. No overlapping mappings were found (canonical values
have no existing mapping for the same supplier value).
"""

import sqlalchemy as sa
from alembic import op

revision: str = "029_consolidate_duplicate_values"
down_revision: str = "028_dclink_mappings"


# ── Mapping: (duplicate_value_id, canonical_value_id) ────────────────────────

DUP_TO_CANON = {
    # Колір
    6087: 283,   # білий, синій -> Білий, Синій
    6088: 236,   # білий, сірий -> Білий, Сірий
    6089: 273,   # білий, фіолетовий -> Білий, Фіолетовий
    6090: 295,   # білий, червоний -> Білий, Червоний
    6091: 194,   # білий, чорний -> Білий, Чорний
    6094: 136,   # прозорий -> Прозорий
    6098: 140,   # прозорий, сірий -> Прозорий, Сірий
    6097: 169,   # прозорий, сріблястий -> Прозорий, Сріблястий
    6099: 162,   # прозорий, чорний -> Прозорий, Чорний
    6101: 275,   # синій, сірий -> Синій, Сірий
    6103: 137,   # сірий, чорний -> Сірий, Чорний
    6105: 161,   # темно-зелений, чорний -> Темно-зелений, Чорний
    245: 6084,   # темно-синій -> Темно-синій
    171: 6106,   # темно-синій, Чорний -> темно-синій, чорний
    6107: 166,   # червоний, чорний -> Червоний, Чорний
    # Процесор
    2071: 5925,  # MediaTek Dimensity 7300 -> Mediatek Dimensity 7300
}


def upgrade() -> None:
    conn = op.get_bind()

    for dup_id, canon_id in DUP_TO_CANON.items():
        # Step 1: Redirect mappings from duplicate to canonical value
        # Using UPDATE with a subquery to avoid joining on the same table
        conn.execute(
            sa.text(
                "UPDATE attribute_value_mappings "
                "SET attribute_value_id = :canon_id "
                "WHERE attribute_value_id = :dup_id "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM attribute_value_mappings avm2 "
                "  WHERE avm2.supplier_attribute_value_id = attribute_value_mappings.supplier_attribute_value_id "
                "  AND avm2.attribute_value_id = :canon_id2"
                ")"
            ),
            {"dup_id": dup_id, "canon_id": canon_id, "canon_id2": canon_id},
        )

        # Step 2: Delete any remaining mappings (should not happen, but safe)
        conn.execute(
            sa.text(
                "DELETE FROM attribute_value_mappings WHERE attribute_value_id = :dup_id"
            ),
            {"dup_id": dup_id},
        )

        # Step 3: Delete the obsolete duplicate value
        conn.execute(
            sa.text("DELETE FROM attribute_values WHERE id = :dup_id"),
            {"dup_id": dup_id},
        )


def downgrade() -> None:
    """Insert back the 16 deleted values.

    NOTE: This restores the values but does NOT restore the original
    attribute_value_mappings rows. The mappings were redirected to the
    canonical values in upgrade() and those redirects are preserved.
    """
    conn = op.get_bind()
    values = [
        (6087, 168, "білий, синій"),
        (6088, 168, "білий, сірий"),
        (6089, 168, "білий, фіолетовий"),
        (6090, 168, "білий, червоний"),
        (6091, 168, "білий, чорний"),
        (6094, 168, "прозорий"),
        (6098, 168, "прозорий, сірий"),
        (6097, 168, "прозорий, сріблястий"),
        (6099, 168, "прозорий, чорний"),
        (6101, 168, "синій, сірий"),
        (6103, 168, "сірий, чорний"),
        (6105, 168, "темно-зелений, чорний"),
        (245, 168, "темно-синій"),
        (171, 168, "темно-синій, Чорний"),
        (6107, 168, "червоний, чорний"),
        (2071, 196, "MediaTek Dimensity 7300"),
    ]
    for vid, attr_id, val in values:
        conn.execute(
            sa.text(
                "INSERT INTO attribute_values (id, attribute_id, value, slug, sort, is_active, created_at, updated_at) "
                "VALUES (:vid, :aid, :val, :slug, 0, TRUE, NOW(), NOW()) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"vid": vid, "aid": attr_id, "val": val, "slug": val.lower().replace(" ", "-").replace(",", "")[:100]},
        )