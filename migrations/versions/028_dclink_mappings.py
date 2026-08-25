"""028: Map DC-Link categories, attributes, and attribute values.

Based on the DC-Link import report (job #57), this migration:

1. Creates missing internal categories for gaming-specific categories
   that exist in the DC-Link catalog but not in our internal taxonomy.

2. Creates missing category mappings so DC-Link products in those
   categories can be imported.

3. Creates missing internal attributes for display specs
   (response time, brightness) that DC-Link provides.

4. Creates missing attribute mappings so DC-Link products can
   have those attributes assigned.

Categories created:
  - Ігрові приставки (id acquired at runtime)
  - Геймпади, джойстики, керма
  - Крісла для геймерів
  - Столи для геймерів
  - Одяг для геймерів
  - Інші аксесуари для ігрових консолей
  - Ігри

Categories mapped (existing):
  - Ноутбуки Б/у -> Ноутбуки (id=39)

Attributes created:
  - Час відгуку матриці (response time)
  - Яскравість дисплея (brightness)

IMPORTANT: This migration does NOT handle the 2892 unmapped attribute
values from the report. Those require individual analysis and mapping
on a per-attribute-value basis.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "028_dclink_mappings"
down_revision: str = "027_supplier_image_suppression"


def upgrade() -> None:
    conn = op.get_bind()

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Create internal categories
    # ──────────────────────────────────────────────────────────────────────────

    cat_data = [
        ("Ігрові приставки", "ігрові-приставки", 40),
        ("Геймпади, джойстики, керма", "геймпади-джойстики-керма", 40),
        ("Крісла для геймерів", "крісла-для-геймерів", 40),
        ("Столи для геймерів", "столи-для-геймерів", 40),
        ("Одяг для геймерів", "одяг-для-геймерів", 40),
        ("Інші аксесуари для ігрових консолей", "аксесуари-для-ігрових-консолей", None),
        ("Ігри", "ігри", 3),
    ]

    cat_ids = {}
    for name, slug, parent_id in cat_data:
        existing = conn.execute(
            sa.text("SELECT id FROM categories WHERE slug = :slug"),
            {"slug": slug},
        ).scalar()
        if existing:
            cat_ids[slug] = existing
            continue
        result = conn.execute(
            sa.text(
                "INSERT INTO categories (name, slug, parent_id, sort_order, is_active, created_at, updated_at) "
                "VALUES (:name, :slug, :parent_id, 0, TRUE, NOW(), NOW()) RETURNING id"
            ),
            {"name": name, "slug": slug, "parent_id": parent_id},
        )
        cat_ids[slug] = result.scalar()

    # Fix parent for console accessories — should be under "ігрові-приставки"
    console_id = cat_ids.get("ігрові-приставки")
    acc_slug = "аксесуари-для-ігрових-консолей"
    if console_id and acc_slug in cat_ids:
        conn.execute(
            sa.text("UPDATE categories SET parent_id = :pid WHERE id = :cid"),
            {"pid": console_id, "cid": cat_ids[acc_slug]},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Create supplier_categories and category_mappings for DC-Link
    # ──────────────────────────────────────────────────────────────────────────

    cat_maps = [
        ("69", "Ігрові приставки", cat_ids.get("ігрові-приставки")),
        ("770", "Геймпади, джойстики, керма", cat_ids.get("геймпади-джойстики-керма")),
        ("125", "Крісла для геймерів", cat_ids.get("крісла-для-геймерів")),
        ("1376", "Столи для геймерів", cat_ids.get("столи-для-геймерів")),
        ("1564", "Одяг для геймерів", cat_ids.get("одяг-для-геймерів")),
        ("1514", "Інші аксесуари для ігрових консолей", cat_ids.get("аксесуари-для-ігрових-консолей")),
        ("972", "Ігри", cat_ids.get("ігри")),
        ("1589", "Ноутбуки Б/у", 39),
    ]

    for ext_id, name, internal_cat_id in cat_maps:
        if internal_cat_id is None:
            continue
        sc_id = conn.execute(
            sa.text(
                "INSERT INTO supplier_categories (supplier_id, external_id, supplier_name, is_removed, created_at, updated_at) "
                "VALUES (2, :eid, :name, FALSE, NOW(), NOW()) RETURNING id"
            ),
            {"eid": ext_id, "name": name},
        ).scalar()
        conn.execute(
            sa.text(
                "INSERT INTO category_mappings (supplier_category_id, category_id, is_active, created_at, updated_at) "
                "VALUES (:scid, :cid, TRUE, NOW(), NOW())"
            ),
            {"scid": sc_id, "cid": internal_cat_id},
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Create internal attributes and mappings
    # ──────────────────────────────────────────────────────────────────────────

    attr_data = [
        ("Час відгуку матриці", "час-відгуку-матриці"),
        ("Яскравість дисплея", "яскравість-дисплея"),
    ]

    for name, slug in attr_data:
        existing = conn.execute(
            sa.text("SELECT id FROM attributes WHERE slug = :slug"),
            {"slug": slug},
        ).scalar()
        if existing:
            attr_id = existing
        else:
            attr_id = conn.execute(
                sa.text(
                    "INSERT INTO attributes (slug, name, type, is_global, is_filterable, sort_order, created_at, updated_at) "
                    "VALUES (:slug, :name, 'select', FALSE, TRUE, 0, NOW(), NOW()) RETURNING id"
                ),
                {"slug": slug, "name": name},
            ).scalar()

        sa_id = conn.execute(
            sa.text(
                "INSERT INTO supplier_attributes (supplier_id, supplier_name, is_removed, created_at, updated_at) "
                "VALUES (2, :name, FALSE, NOW(), NOW()) RETURNING id"
            ),
            {"name": name},
        ).scalar()
        conn.execute(
            sa.text(
                "INSERT INTO attribute_mappings (supplier_attribute_id, attribute_id, is_active, created_at, updated_at) "
                "VALUES (:said, :aid, TRUE, NOW(), NOW())"
            ),
            {"said": sa_id, "aid": attr_id},
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove all DC-Link mappings
    conn.execute(
        sa.text(
            "DELETE FROM attribute_mappings WHERE supplier_attribute_id IN "
            "(SELECT id FROM supplier_attributes WHERE supplier_id = 2 "
            "AND supplier_name IN ('Час відгуку матриці', 'Яскравість дисплея'))"
        )
    )
    conn.execute(
        sa.text(
            "DELETE FROM supplier_attributes WHERE supplier_id = 2 "
            "AND supplier_name IN ('Час відгуку матриці', 'Яскравість дисплея')"
        )
    )
    conn.execute(
        sa.text("DELETE FROM attributes WHERE slug IN ('час-відгуку-матриці', 'яскравість-дисплея')")
    )

    conn.execute(
        sa.text(
            "DELETE FROM category_mappings WHERE supplier_category_id IN "
            "(SELECT id FROM supplier_categories WHERE supplier_id = 2 "
            "AND external_id IN ('69', '770', '125', '1376', '1564', '1514', '972', '1589'))"
        )
    )
    conn.execute(
        sa.text(
            "DELETE FROM supplier_categories WHERE supplier_id = 2 "
            "AND external_id IN ('69', '770', '125', '1376', '1564', '1514', '972', '1589')"
        )
    )
    conn.execute(
        sa.text(
            "DELETE FROM categories WHERE slug IN ("
            "'ігрові-приставки', 'геймпади-джойстики-керма', 'крісла-для-геймерів', "
            "'столи-для-геймерів', 'одяг-для-геймерів', 'аксесуари-для-ігрових-консолей', 'ігри'"
            ")"
        )
    )
