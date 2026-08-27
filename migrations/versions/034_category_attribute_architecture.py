"""034: Category-oriented attribute architecture.

Introduces two new core tables:

  category_attributes       — configuration of an Attribute in a Category
  category_attribute_values — which AttributeValues are available per
                              CategoryAttribute

Data migration:
  1. Every existing category_filters row -> category_attributes row
  2. Every distinct (category_id, attribute_id) from product_attributes ->
     category_attributes (if not already present)
  3. Every distinct (category_attribute, attribute_value_id) from
     product_attributes -> category_attribute_values

Existing IDs are preserved.  No duplicate canonical attributes or values
are created.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "034_category_attribute_architecture"
down_revision: str = "032_channel_mappings"


def upgrade() -> None:
    # -- 1. Create category_attributes table ----------------------------
    op.create_table(
        "category_attributes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("attribute_id", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("multiple", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("filterable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("searchable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("filter_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_ca_category"),
        sa.ForeignKeyConstraint(["attribute_id"], ["attributes.id"], name="fk_ca_attribute"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "attribute_id", name="uq_category_attribute"),
    )
    op.create_index(op.f("ix_category_attributes_category"), "category_attributes", ["category_id"])
    op.create_index(op.f("ix_category_attributes_attribute"), "category_attributes", ["attribute_id"])

    # -- 2. Create category_attribute_values table ----------------------
    op.create_table(
        "category_attribute_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category_attribute_id", sa.Integer(), nullable=False),
        sa.Column("attribute_value_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(
            ["category_attribute_id"], ["category_attributes.id"],
            name="fk_cav_category_attribute", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attribute_value_id"], ["attribute_values.id"],
            name="fk_cav_attribute_value",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "category_attribute_id", "attribute_value_id",
            name="uq_category_attribute_value",
        ),
    )
    op.create_index(
        op.f("ix_category_attribute_values_ca"),
        "category_attribute_values", ["category_attribute_id"],
    )
    op.create_index(
        op.f("ix_category_attribute_values_av"),
        "category_attribute_values", ["attribute_value_id"],
    )

    # -- 3. Add category_id column to attribute_mappings -----------------
    op.add_column(
        "attribute_mappings",
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", name="fk_am_category"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_attribute_mappings_category"),
        "attribute_mappings", ["category_id"],
    )

    # -- 4. Migrate existing category_filters -> category_attributes -----
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            INSERT INTO category_attributes
                (category_id, attribute_id, required, multiple,
                 filterable, searchable, sort_order, filter_type,
                 created_at, updated_at)
            SELECT
                cf.category_id,
                cf.attribute_id,
                FALSE             AS required,
                FALSE             AS multiple,
                cf.enabled        AS filterable,
                FALSE             AS searchable,
                cf.position       AS sort_order,
                NULL              AS filter_type,
                NOW(),
                NOW()
            FROM category_filters cf
            WHERE cf.category_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM category_attributes ca
                  WHERE ca.category_id = cf.category_id
                    AND ca.attribute_id = cf.attribute_id
              )
        """)
    )

    # -- 5. Populate category_attributes from product_attributes usage ---
    conn.execute(
        sa.text("""
            INSERT INTO category_attributes
                (category_id, attribute_id, required, multiple,
                 filterable, searchable, sort_order, filter_type,
                 created_at, updated_at)
            SELECT DISTINCT
                pc.category_id,
                pa.attribute_id,
                FALSE  AS required,
                FALSE  AS multiple,
                FALSE  AS filterable,
                FALSE  AS searchable,
                0      AS sort_order,
                NULL   AS filter_type,
                NOW(),
                NOW()
            FROM product_attributes pa
            JOIN product_categories pc ON pc.product_id = pa.product_id
            WHERE NOT EXISTS (
                SELECT 1 FROM category_attributes ca
                WHERE ca.category_id = pc.category_id
                  AND ca.attribute_id = pa.attribute_id
            )
        """)
    )

    # -- 6. Populate category_attribute_values from product data --------
    conn.execute(
        sa.text("""
            INSERT INTO category_attribute_values
                (category_attribute_id, attribute_value_id,
                 created_at, updated_at)
            SELECT DISTINCT
                ca.id               AS category_attribute_id,
                pa.attribute_value_id,
                NOW(),
                NOW()
            FROM product_attributes pa
            JOIN product_categories pc ON pc.product_id = pa.product_id
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

    # -- 7. Best-effort category inference for attribute_mappings -------
    conn.execute(
        sa.text("""
            UPDATE attribute_mappings am
            SET category_id = (
                SELECT ca.category_id
                FROM category_attributes ca
                WHERE ca.attribute_id = am.attribute_id
                GROUP BY ca.category_id
                HAVING COUNT(*) = (
                    SELECT COUNT(*) FROM category_attributes ca2
                    WHERE ca2.attribute_id = am.attribute_id
                )
            )
            WHERE am.category_id IS NULL
              AND am.attribute_id IS NOT NULL
              AND (
                  SELECT COUNT(DISTINCT ca3.category_id)
                  FROM category_attributes ca3
                  WHERE ca3.attribute_id = am.attribute_id
              ) = 1
        """)
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_category_attribute_values_ca"),
        table_name="category_attribute_values",
    )
    op.drop_index(
        op.f("ix_category_attribute_values_av"),
        table_name="category_attribute_values",
    )
    op.drop_table("category_attribute_values")

    op.drop_index(
        op.f("ix_category_attributes_category"),
        table_name="category_attributes",
    )
    op.drop_index(
        op.f("ix_category_attributes_attribute"),
        table_name="category_attributes",
    )
    op.drop_table("category_attributes")

    op.drop_index(
        op.f("ix_attribute_mappings_category"),
        table_name="attribute_mappings",
    )
    op.drop_column("attribute_mappings", "category_id")
