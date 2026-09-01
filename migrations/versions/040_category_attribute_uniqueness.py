"""040: Add case-insensitive uniqueness constraints for categories, attributes and values.

Adds PostgreSQL functional unique indexes with LOWER(TRIM(...)) so that
duplicate entries differing only in case or whitespace are prevented at the
database level.  Resolves existing case-sensitive duplicate attribute values.

New constraints:
  - categories:  (parent_id, LOWER(TRIM(name))) unique (root cats: parent_id IS NULL)
  - attributes:  LOWER(TRIM(name)) globally unique
  - attribute_values:  (attribute_id, LOWER(TRIM(value))) unique

Four existing case-sensitive duplicate attribute-value pairs are resolved
by keeping the lowest-ID record and re-pointing references to it.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "040_category_attribute_uniqueness"
down_revision: str = "039_product_attributes_value_text_500"


def _resolve_duplicate_attribute_values(conn):
    """Merge case-insensitive duplicate attribute values."""
    sql = text("""
        SELECT attribute_id, LOWER(TRIM(value)) AS norm,
               min(id) AS keep_id,
               array_remove(array_agg(id ORDER BY id), min(id)) AS remove_ids
        FROM attribute_values
        GROUP BY attribute_id, LOWER(TRIM(value))
        HAVING COUNT(*) > 1
    """)
    dups = conn.execute(sql).fetchall()
    if not dups:
        return
    total_removed = 0
    for row in dups:
        attr_id, norm, keep_id, remove_ids = row[0], row[1], row[2], row[3]
        conn.execute(
            text("UPDATE product_attributes SET attribute_value_id = :keep "
                 "WHERE attribute_value_id = ANY(:remove) AND attribute_value_id != :keep"),
            {"keep": keep_id, "remove": remove_ids},
        )
        conn.execute(
            text("UPDATE category_attribute_values SET attribute_value_id = :keep "
                 "WHERE attribute_value_id = ANY(:remove) AND attribute_value_id != :keep"),
            {"keep": keep_id, "remove": remove_ids},
        )
        conn.execute(
            text("UPDATE attribute_value_mappings SET attribute_value_id = :keep "
                 "WHERE attribute_value_id = ANY(:remove) AND attribute_value_id != :keep"),
            {"keep": keep_id, "remove": remove_ids},
        )
        conn.execute(
            text("DELETE FROM attribute_values WHERE id = ANY(:remove) AND id != :keep"),
            {"keep": keep_id, "remove": remove_ids},
        )
        total_removed += len(remove_ids)
    print(f"  Total duplicate attribute values removed: {total_removed}")


def upgrade() -> None:
    conn = op.get_bind()
    _resolve_duplicate_attribute_values(conn)

    op.create_index(
        "uq_categories_root_normalized_name",
        "categories",
        [sa.text("LOWER(TRIM(name))")],
        postgresql_where=sa.text("parent_id IS NULL"),
        unique=True,
    )
    op.create_index(
        "uq_categories_parent_normalized_name",
        "categories",
        [sa.text("parent_id"), sa.text("LOWER(TRIM(name))")],
        postgresql_where=sa.text("parent_id IS NOT NULL"),
        unique=True,
    )
    op.create_index(
        "uq_attributes_normalized_name",
        "attributes",
        [sa.text("LOWER(TRIM(name))")],
        unique=True,
    )
    op.drop_constraint(
        "attribute_values_attribute_id_value_key",
        "attribute_values",
        type_="unique",
    )
    op.create_index(
        "uq_attribute_values_attr_normalized_value",
        "attribute_values",
        [sa.text("attribute_id"), sa.text("LOWER(TRIM(value))")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_attribute_values_attr_normalized_value", table_name="attribute_values")
    op.create_unique_constraint(
        "attribute_values_attribute_id_value_key",
        "attribute_values",
        ["attribute_id", "value"],
    )
    op.drop_index("uq_attributes_normalized_name", table_name="attributes")
    op.drop_index("uq_categories_parent_normalized_name", table_name="categories")
    op.drop_index("uq_categories_root_normalized_name", table_name="categories")
