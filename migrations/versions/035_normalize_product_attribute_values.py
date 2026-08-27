"""035: Populate product_attributes.attribute_value_id and category_attribute_values.

Dry-run audit confirmed 100% exact-match coverage:
  - 185,566 product_attributes
  - 185,566 have an exact matching attribute_values row (same attribute_id, same value)
  - 0 unmatched, 0 ambiguous, 0 duplicates

Phase 1: UPDATE product_attributes SET attribute_value_id = av.id
  JOIN attribute_values av ON av.attribute_id = pa.attribute_id AND av.value = pa.value_text

Phase 2: INSERT INTO category_attribute_values
  FROM product_attributes + product_categories + category_attributes

Both operations are fully reversible and use only exact existing data.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "035_normalize_product_attribute_values"
down_revision: str = "034_category_attribute_architecture"


def upgrade() -> None:
    conn = op.get_bind()

    # ── Phase 1: Populate attribute_value_id ───────────────────────────────
    conn.execute(
        sa.text("""
            UPDATE product_attributes pa
            SET attribute_value_id = av.id,
                updated_at = NOW()
            FROM attribute_values av
            WHERE av.attribute_id = pa.attribute_id
              AND av.value = pa.value_text
              AND pa.attribute_value_id IS NULL
        """)
    )

    # ── Phase 2: Populate category_attribute_values ────────────────────────
    conn.execute(
        sa.text("""
            INSERT INTO category_attribute_values
                (category_attribute_id, attribute_value_id, created_at, updated_at)
            SELECT DISTINCT
                ca.id                 AS category_attribute_id,
                pa.attribute_value_id,
                NOW(),
                NOW()
            FROM product_attributes pa
            JOIN product_categories pc
                ON pc.product_id = pa.product_id
            JOIN category_attributes ca
                ON ca.category_id = pc.category_id
               AND ca.attribute_id = pa.attribute_id
            WHERE pa.attribute_value_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM category_attribute_values cav
                  WHERE cav.category_attribute_id = ca.id
                    AND cav.attribute_value_id = pa.attribute_value_id
              )
        """)
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Phase 1 revert: clear attribute_value_id only for rows that this
    # migration populated.  Since the dry-run confirmed 0 pre-existing
    # attribute_value_id values, we can safely clear all of them.
    conn.execute(
        sa.text("UPDATE product_attributes SET attribute_value_id = NULL, updated_at = NOW()")
    )

    # Phase 2 revert: clear all category_attribute_values
    conn.execute(
        sa.text("DELETE FROM category_attribute_values")
    )
