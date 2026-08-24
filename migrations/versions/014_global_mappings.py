"""014: Global-by-default mappings.

supplier_id = NULL  -> GLOBAL dictionary entry / mapping (applies to all)
supplier_id = <id>  -> supplier-specific entry/override

Converts every supplier-bound mapping row into a global one, merging the
duplicated per-supplier dictionary entries into single global rows. Idempotent.
"""

from alembic import op

revision: str = '014_global_mappings'
down_revision: str = '013_mapping_normalization'

UPGRADE_SQL = """
DROP TABLE IF EXISTS _vmap_dedupe;
DROP TABLE IF EXISTS _val_losers;
DROP TABLE IF EXISTS _val_merge;
DROP TABLE IF EXISTS _repoint_cat;
DROP TABLE IF EXISTS _repoint_attr;

ALTER TABLE supplier_categories ALTER COLUMN supplier_id DROP NOT NULL;
ALTER TABLE supplier_attributes  ALTER COLUMN supplier_id DROP NOT NULL;

INSERT INTO supplier_categories (supplier_id, supplier_name, is_removed,
                                 created_at, updated_at)
SELECT DISTINCT NULL::integer, sc.supplier_name, FALSE, NOW(), NOW()
FROM supplier_categories sc
WHERE NOT EXISTS (SELECT 1 FROM supplier_categories g
                  WHERE g.supplier_id IS NULL AND g.supplier_name = sc.supplier_name);

INSERT INTO supplier_attributes (supplier_id, supplier_name, is_removed,
                                 created_at, updated_at)
SELECT DISTINCT NULL::integer, sa.supplier_name, FALSE, NOW(), NOW()
FROM supplier_attributes sa
WHERE NOT EXISTS (SELECT 1 FROM supplier_attributes g
                  WHERE g.supplier_id IS NULL AND g.supplier_name = sa.supplier_name);

-- 3) repoint mappings to GLOBAL rows, collapsing per-supplier copies -------
CREATE TEMP TABLE _repoint_cat AS
SELECT m.id AS map_id, g.id AS new_fk,
       ROW_NUMBER() OVER (PARTITION BY g.id ORDER BY m.id) AS rn
FROM category_mappings m
JOIN supplier_categories o ON o.id = m.supplier_category_id AND o.supplier_id IS NOT NULL
JOIN supplier_categories g ON g.supplier_name = o.supplier_name AND g.supplier_id IS NULL;

DELETE FROM category_mappings WHERE id IN (SELECT map_id FROM _repoint_cat WHERE rn > 1);
UPDATE category_mappings m SET supplier_category_id = r.new_fk, updated_at = NOW()
FROM _repoint_cat r WHERE m.id = r.map_id;
DROP TABLE _repoint_cat;

CREATE TEMP TABLE _repoint_attr AS
SELECT m.id AS map_id, g.id AS new_fk,
       ROW_NUMBER() OVER (PARTITION BY g.id ORDER BY m.id) AS rn
FROM attribute_mappings m
JOIN supplier_attributes o ON o.id = m.supplier_attribute_id AND o.supplier_id IS NOT NULL
JOIN supplier_attributes g ON g.supplier_name = o.supplier_name AND g.supplier_id IS NULL;

DELETE FROM attribute_mappings WHERE id IN (SELECT map_id FROM _repoint_attr WHERE rn > 1);
UPDATE attribute_mappings m SET supplier_attribute_id = r.new_fk, updated_at = NOW()
FROM _repoint_attr r WHERE m.id = r.map_id;
DROP TABLE _repoint_attr;

-- 4) move value children under GLOBAL holder attributes --------------------
UPDATE supplier_attribute_values v SET supplier_attribute_id = g.id, updated_at = NOW()
FROM supplier_attributes o
JOIN supplier_attributes g ON g.supplier_name = o.supplier_name AND g.supplier_id IS NULL
WHERE v.supplier_attribute_id = o.id AND o.supplier_id IS NOT NULL;
-- __PART2__

CREATE TEMP TABLE _val_merge AS
    SELECT MIN(v.id) AS keep_id, v.supplier_attribute_id, v.supplier_value
    FROM supplier_attribute_values v
    GROUP BY v.supplier_attribute_id, v.supplier_value HAVING COUNT(*) > 1;

CREATE TEMP TABLE _val_losers AS
    SELECT v.id AS loser_id, k.keep_id
    FROM supplier_attribute_values v
    JOIN _val_merge k ON k.supplier_attribute_id = v.supplier_attribute_id
                     AND k.supplier_value = v.supplier_value
    WHERE v.id <> k.keep_id;

-- mappings of losing rows collapse onto the keeper; any resulting duplicates
-- are removed by the safety-net dedupe below
CREATE TEMP TABLE _vmap_dedupe AS
SELECT m.id AS map_id, l.keep_id,
       EXISTS (SELECT 1 FROM attribute_value_mappings k2
               WHERE k2.supplier_attribute_value_id = l.keep_id) AS keeper_has_mapping
FROM attribute_value_mappings m
JOIN _val_losers l ON l.loser_id = m.supplier_attribute_value_id;

-- losers whose keeper already owns a mapping are exact duplicates -> drop
DELETE FROM attribute_value_mappings WHERE id IN
    (SELECT map_id FROM _vmap_dedupe WHERE keeper_has_mapping);

-- remaining losers adopt their keeper (collisions handled by safety net)
UPDATE attribute_value_mappings m
SET supplier_attribute_value_id = d.keep_id, updated_at = NOW()
FROM _vmap_dedupe d
WHERE m.id = d.map_id AND NOT d.keeper_has_mapping;

DELETE FROM supplier_attribute_values v USING _val_losers l WHERE v.id = l.loser_id;
DROP TABLE _val_losers; DROP TABLE _val_merge;

DELETE FROM supplier_attribute_values v
WHERE NOT EXISTS (SELECT 1 FROM attribute_value_mappings m
                  WHERE m.supplier_attribute_value_id = v.id);

DELETE FROM supplier_attributes o
WHERE o.supplier_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM attribute_mappings m WHERE m.supplier_attribute_id = o.id)
  AND NOT EXISTS (SELECT 1 FROM supplier_attribute_values v WHERE v.supplier_attribute_id = o.id);

DELETE FROM supplier_categories o
WHERE o.supplier_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM category_mappings m WHERE m.supplier_category_id = o.id);

-- Safety net: collapse ANY residual duplicate mappings (interrupted runs,
-- prior partial states). Identical legacy rules — lowest id survives.
DELETE FROM attribute_value_mappings m USING attribute_value_mappings k
 WHERE k.supplier_attribute_value_id = m.supplier_attribute_value_id AND k.id < m.id;
DELETE FROM attribute_mappings m USING attribute_mappings k
 WHERE k.supplier_attribute_id = m.supplier_attribute_id AND k.id < m.id;
DELETE FROM category_mappings m USING category_mappings k
 WHERE k.supplier_category_id = m.supplier_category_id AND k.id < m.id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_categories_scope_name
    ON supplier_categories (supplier_id, supplier_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_categories_global_name
    ON supplier_categories (supplier_name) WHERE supplier_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_attributes_scope_name
    ON supplier_attributes (supplier_id, supplier_name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_attributes_global_name
    ON supplier_attributes (supplier_name) WHERE supplier_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_supplier_attr_values_scope
    ON supplier_attribute_values (supplier_attribute_id, supplier_value);
"""

DOWNGRADE_SQL = """
DROP INDEX IF EXISTS uq_supplier_attr_values_scope;
DROP INDEX IF EXISTS uq_supplier_attributes_global_name;
DROP INDEX IF EXISTS uq_supplier_attributes_scope_name;
DROP INDEX IF EXISTS uq_supplier_categories_global_name;
DROP INDEX IF EXISTS uq_supplier_categories_scope_name;

DELETE FROM supplier_attribute_values WHERE supplier_attribute_id IN
    (SELECT id FROM supplier_attributes WHERE supplier_id IS NULL);
DELETE FROM attribute_value_mappings WHERE supplier_attribute_value_id NOT IN
    (SELECT id FROM supplier_attribute_values);
DELETE FROM supplier_attributes WHERE supplier_id IS NULL;
DELETE FROM category_mappings WHERE supplier_category_id IN
    (SELECT id FROM supplier_categories WHERE supplier_id IS NULL);
DELETE FROM supplier_categories WHERE supplier_id IS NULL;

ALTER TABLE supplier_attributes  ALTER COLUMN supplier_id SET NOT NULL;
ALTER TABLE supplier_categories ALTER COLUMN supplier_id SET NOT NULL;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
