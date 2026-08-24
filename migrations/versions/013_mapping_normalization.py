"""013: Mapping normalization layer readiness.

- Allow NULL internal targets on attribute/category mappings so that records
  imported as "Не імпортувати" (excluded) can exist without a catalog entity,
  and so unresolved targets stay visible for manual linking in the admin UI.
- Unique indexes making every mapping identity-safe for idempotent imports:
  one mapping row per supplier item (category / attribute / attribute value).
"""

from alembic import op

revision: str = '013_mapping_normalization'
down_revision: str = '012_system_suppliers'

UPGRADE_SQL = """
ALTER TABLE attribute_mappings ALTER COLUMN attribute_id DROP NOT NULL;
ALTER TABLE category_mappings ALTER COLUMN category_id DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_mappings_supplier_attribute
    ON attribute_mappings (supplier_attribute_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_category_mappings_supplier_category
    ON category_mappings (supplier_category_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attribute_value_mappings_supplier_value
    ON attribute_value_mappings (supplier_attribute_value_id);
"""

DOWNGRADE_SQL = """
DROP INDEX IF EXISTS uq_attribute_value_mappings_supplier_value;
DROP INDEX IF EXISTS uq_category_mappings_supplier_category;
DROP INDEX IF EXISTS uq_attribute_mappings_supplier_attribute;

-- Restore NOT NULL only where no excluded (NULL-target) rows exist.
DELETE FROM attribute_mappings WHERE attribute_id IS NULL;
DELETE FROM category_mappings WHERE category_id IS NULL;
ALTER TABLE attribute_mappings ALTER COLUMN attribute_id SET NOT NULL;
ALTER TABLE category_mappings ALTER COLUMN category_id SET NOT NULL;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
