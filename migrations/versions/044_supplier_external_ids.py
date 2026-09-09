"""044: Supplier-scoped external-ID identity for source dictionary tables.

Adds supplier-scoped external identity to the source dictionary layer:

  - supplier_attributes.external_id        (nullable, VARCHAR(255))
  - supplier_attribute_values.external_id  (nullable, VARCHAR(255))

and supplier-scoped partial unique indexes so that a source ID is unique
WITHIN one supplier (and within one supplier attribute for values):

  - supplier_categories:        UNIQUE (supplier_id, external_id) WHERE external_id IS NOT NULL
  - supplier_categories global: UNIQUE (external_id) WHERE supplier_id IS NULL AND external_id IS NOT NULL
  - supplier_attributes:        UNIQUE (supplier_id, external_id) WHERE external_id IS NOT NULL
  - supplier_attributes global: UNIQUE (external_id) WHERE supplier_id IS NULL AND external_id IS NOT NULL
  - supplier_attribute_values:  UNIQUE (supplier_attribute_id, external_id) WHERE external_id IS NOT NULL

The same external ID MAY exist in different suppliers — the scope is the
supplier, never the whole table.

This migration is PURE DDL: no existing rows are modified, no mappings are
rewritten, and no catalog data is touched.  Existing name-based identity
(UNIQUE (supplier_id, supplier_name) etc.) is preserved unchanged.

Revision ID: 044_supplier_external_ids
Revises: 043_brain_supplier
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "044_supplier_external_ids"
down_revision: str = "043_brain_supplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- supplier_attributes.external_id -------------------------------------
    op.add_column(
        "supplier_attributes",
        sa.Column("external_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_supplier_attributes_external_id",
        "supplier_attributes",
        ["external_id"],
        unique=False,
    )
    # Supplier-scoped unique identity: one external ID per supplier.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_attributes_scope_external_id
            ON supplier_attributes (supplier_id, external_id)
            WHERE external_id IS NOT NULL
        """
    )
    # Global dictionary rows (supplier_id IS NULL) are scoped by external_id alone.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_attributes_global_external_id
            ON supplier_attributes (external_id)
            WHERE supplier_id IS NULL AND external_id IS NOT NULL
        """
    )

    # -- supplier_attribute_values.external_id -------------------------------
    op.add_column(
        "supplier_attribute_values",
        sa.Column("external_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_supplier_attribute_values_external_id",
        "supplier_attribute_values",
        ["external_id"],
        unique=False,
    )
    # A value external ID is meaningful only inside its supplier attribute.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_attribute_values_scope_external_id
            ON supplier_attribute_values (supplier_attribute_id, external_id)
            WHERE external_id IS NOT NULL
        """
    )

    # -- supplier_categories external-ID uniqueness (column already exists) --
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_categories_scope_external_id
            ON supplier_categories (supplier_id, external_id)
            WHERE external_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_categories_global_external_id
            ON supplier_categories (external_id)
            WHERE supplier_id IS NULL AND external_id IS NOT NULL
        """
    )


def downgrade() -> None:
    # Supplier categories: drop external-ID uniqueness only (column predates 044).
    op.execute("DROP INDEX IF EXISTS uq_supplier_categories_global_external_id")
    op.execute("DROP INDEX IF EXISTS uq_supplier_categories_scope_external_id")

    # Supplier attribute values: drop uniqueness + column.
    op.execute("DROP INDEX IF EXISTS uq_supplier_attribute_values_scope_external_id")
    op.drop_index("ix_supplier_attribute_values_external_id", table_name="supplier_attribute_values")
    op.drop_column("supplier_attribute_values", "external_id")

    # Supplier attributes: drop uniqueness + column.
    op.execute("DROP INDEX IF EXISTS uq_supplier_attributes_global_external_id")
    op.execute("DROP INDEX IF EXISTS uq_supplier_attributes_scope_external_id")
    op.drop_index("ix_supplier_attributes_external_id", table_name="supplier_attributes")
    op.drop_column("supplier_attributes", "external_id")
