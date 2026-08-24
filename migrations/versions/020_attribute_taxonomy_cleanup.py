"""020: Attribute taxonomy cleanup — split catch-all attributes.

Creates distinct internal attributes for deterministic supplier mappings
that were previously collapsed into catch-all attributes #167 (Кількість),
#193 (Об'єм пам'яті), #206 (Сумісність).  Deactivates ambiguous mappings
so that the next supplier import cleanly populates the new structure.

Changes (all idempotent):
1. Create 25 new internal attributes for count, memory, compatibility, and
   general-purpose concepts.
2. Remap ~27 supplier attributes from #167 to new count-specific attributes.
3. Remap 9 supplier attributes from #193 to existing #329/#330 or new attrs.
4. Remap 8 supplier attributes from #206 to new feature-specific attributes.
5. Deactivate 8 ambiguous #206 mappings (CPU instructions / obscure features).
6. Create mapping for previously unmapped 10548 (Частота ядра -> #325).
7. Activate + remap excluded supplier attributes for Brand, Wi-Fi, Weight,
   Dimensions, Material, Case colour, Bluetooth.
8. Create initial attribute_values seeded from existing data for new attrs
   that have identifiable source data.

No historical product_attributes are migrated.

Revision ID: 020_attribute_taxonomy_cleanup
Revises: 019_import_status_warnings
"""

from alembic import op
import sqlalchemy as sa

revision: str = "020_attribute_taxonomy_cleanup"
down_revision: str = "019_import_status_warnings"
branch_labels = None
depends_on = None

NEW_ATTRIBUTES = [
    ("Кількість ядер", "кількість ядер", "text"),
    ("Кількість потоків", "кількість потоків", "text"),
    ("Кількість слотів пам'яті", "кількість слотів пам'яті", "text"),
    ("Кількість встановлених планок ОЗП", "кількість встановлених планок озп", "text"),
    ("Кількість вентиляторів", "кількість вентиляторів", "text"),
    ("Кількість USB-портів", "кількість usb-портів", "text"),
    ("Кількість портів Ethernet", "кількість портів ethernet", "text"),
    ("Кількість портів SFP+", "кількість портів sfp-", "text"),
    ("Кількість портів PoE", "кількість портів poe", "text"),
    ("Кількість клавіш клавіатури", "кількість клавіш клавіатури", "text"),
    ("Кількість кнопок миші", "кількість кнопок миші", "text"),
    ("Кількість антен", "кількість антен", "text"),
    ("Кількість роз'ємів", "кількість роз'ємів", "text"),
    ("Об'єм пам'яті відеокарти", "об'єм пам'яті відеокарти", "text"),
    ("Об'єм вбудованої пам'яті", "об'єм вбудованої пам'яті", "text"),
    ("Об'єм накопичувача", "об'єм накопичувача", "text"),
    ("Підтримка Bluetooth", "підтримка bluetooth", "text"),
    ("Підтримка PoE", "підтримка poe", "text"),
    ("Підтримка NVMe", "підтримка nvme", "text"),
    ("Підтримка картки пам'яті", "підтримка картки пам'яті", "text"),
    ("Підтримка RAID", "підтримка raid", "text"),
    ("Підтримка eSIM", "підтримка esim", "text"),
    ("Бренд", "бренд", "text"),
    ("Вага", "вага", "text"),
    ("Розміри", "розміри", "text"),
]

# Mapping config: (supplier_attribute_id, target_slug_or_id)
# Supplier attrs to REMAP from #167 to new count attrs
REMAP_FROM_167 = [
    (10572, "Кількість ядер"),
    (10418, "Кількість потоків"),
    (10830, "Кількість слотів пам'яті"),
    (11009, "Кількість встановлених планок ОЗП"),
    (11434, "Кількість вентиляторів"),
    (11454, "Кількість USB-портів"),
    (10494, "Кількість USB-портів"),
    (11348, "Кількість USB-портів"),
    (11052, "Кількість USB-портів"),
    (11299, "Кількість USB-портів"),
    (10396, "Кількість USB-портів"),
    (11452, "Кількість портів Ethernet"),
    (10368, "Кількість портів SFP+"),
    (10361, "Кількість портів PoE"),
    (10669, "Кількість клавіш клавіатури"),
    (11298, "Кількість кнопок миші"),
    (10794, "Кількість антен"),
    (11093, "Кількість роз'ємів"),
]

# Supplier attrs to REMAP from #193 to new/existing attrs
REMAP_FROM_193 = [
    (10490, 329),
    (10445, 329),
    (11380, 330),
    (10410, 330),
    (11402, "Об'єм пам'яті відеокарти"),
    (11346, "Об'єм пам'яті відеокарти"),
    (11458, "Об'єм вбудованої пам'яті"),
    (11000, "Об'єм вбудованої пам'яті"),
    (11199, "Об'єм накопичувача"),
]

# Supplier attrs to REMAP from #206 to new feature attrs
REMAP_FROM_206 = [
    (10691, "Підтримка Bluetooth"),
    (11116, "Підтримка PoE"),
    (10570, "Підтримка PoE"),
    (10879, "Підтримка PoE"),
    (10610, "Підтримка NVMe"),
    (11347, "Підтримка картки пам'яті"),
    (11279, "Підтримка RAID"),
    (10529, "Підтримка eSIM"),
]

# Supplier attrs to DEACTIVATE from #206 (ambiguous)
DEACTIVATE_FROM_206 = [
    10738, 11268, 10657, 11235, 10953, 10455, 11296, 11331,
]

# Supplier attrs to ACTIVATE + map: (sa_id, target_slug_or_id, was_active)
ACTIVATE_AND_MAP = [
    (11224, "Бренд", False),
    (11355, "Бренд", True),
    (11110, "Бренд", True),
    (10727, "Бренд", True),
    (10858, "Бренд", True),
    (11171, "Бренд", True),
    (11051, 250, False),
    (11177, "Підтримка Bluetooth", False),
    (10472, "Вага", False),
    (10603, "Розміри", False),
    (10415, 169, False),
    (11492, 168, False),
]

# Supplier attrs to CREATE mapping for (currently unmapped)
NEW_MAPPING = [
    (10548, 325),
]

# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade():
    conn = op.get_bind()

    # === 1. Create new internal attributes (idempotent) ===
    for name, slug, typ in NEW_ATTRIBUTES:
        conn.execute(
            sa.text(
                "INSERT INTO attributes (name, slug, type, is_global, is_filterable, sort_order, created_at, updated_at) "
                "SELECT :name, :slug, :typ, TRUE, FALSE, 0, NOW(), NOW() "
                "WHERE NOT EXISTS (SELECT 1 FROM attributes WHERE slug = :slug2)"
            ),
            {"name": name, "slug": slug, "typ": typ, "slug2": slug},
        )

    # === 2. Helper to resolve target to attribute id ===
    def _tid(target):
        if isinstance(target, int):
            return target
        row = conn.execute(
            sa.text("SELECT id FROM attributes WHERE slug = :slug"),
            {"slug": target},
        ).fetchone()
        if row is None:
            # Try by name
            row = conn.execute(
                sa.text("SELECT id FROM attributes WHERE name = :name"),
                {"name": target},
            ).fetchone()
        if row is None:
            raise ValueError(f"Attribute target not found: {target}")
        return row[0]

    # === 3. REMAP from #167 ===
    for sa_id, target in REMAP_FROM_167:
        tid = _tid(target)
        conn.execute(
            sa.text(
                "UPDATE attribute_mappings SET attribute_id = :tid, updated_at = NOW() "
                "WHERE supplier_attribute_id = :sa_id AND attribute_id = 167 AND is_active = TRUE"
            ),
            {"tid": tid, "sa_id": sa_id},
        )

    # === 4. REMAP from #193 ===
    for sa_id, target in REMAP_FROM_193:
        tid = _tid(target)
        conn.execute(
            sa.text(
                "UPDATE attribute_mappings SET attribute_id = :tid, updated_at = NOW() "
                "WHERE supplier_attribute_id = :sa_id AND attribute_id = 193 AND is_active = TRUE"
            ),
            {"tid": tid, "sa_id": sa_id},
        )

    # === 5. REMAP from #206 ===
    for sa_id, target in REMAP_FROM_206:
        tid = _tid(target)
        conn.execute(
            sa.text(
                "UPDATE attribute_mappings SET attribute_id = :tid, updated_at = NOW() "
                "WHERE supplier_attribute_id = :sa_id AND attribute_id = 206 AND is_active = TRUE"
            ),
            {"tid": tid, "sa_id": sa_id},
        )

    # === 6. DEACTIVATE ambiguous #206 mappings ===
    for sa_id in DEACTIVATE_FROM_206:
        conn.execute(
            sa.text(
                "UPDATE attribute_mappings SET is_active = FALSE, updated_at = NOW() "
                "WHERE supplier_attribute_id = :sa_id AND is_active = TRUE"
            ),
            {"sa_id": sa_id},
        )

    # === 7. ACTIVATE + REMAP excluded/disabled ===
    for sa_id, target, was_active in ACTIVATE_AND_MAP:
        tid = _tid(target)
        mid = conn.execute(
            sa.text("SELECT id FROM attribute_mappings WHERE supplier_attribute_id = :sa_id"),
            {"sa_id": sa_id},
        ).fetchone()
        if mid:
            conn.execute(
                sa.text(
                    "UPDATE attribute_mappings SET attribute_id = :tid, is_active = TRUE, updated_at = NOW() "
                    "WHERE id = :mid"
                ),
                {"tid": tid, "mid": mid[0]},
            )
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO attribute_mappings (supplier_attribute_id, attribute_id, is_active, created_at, updated_at) "
                    "VALUES (:sa_id, :tid, TRUE, NOW(), NOW())"
                ),
                {"sa_id": sa_id, "tid": tid},
            )

    # === 8. CREATE mapping for unmapped ===
    for sa_id, target_id in NEW_MAPPING:
        existing = conn.execute(
            sa.text("SELECT id FROM attribute_mappings WHERE supplier_attribute_id = :sa_id"),
            {"sa_id": sa_id},
        ).fetchone()
        if existing:
            conn.execute(
                sa.text(
                    "UPDATE attribute_mappings SET attribute_id = :tid, is_active = TRUE, updated_at = NOW() "
                    "WHERE id = :mid"
                ),
                {"tid": target_id, "mid": existing[0]},
            )
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO attribute_mappings (supplier_attribute_id, attribute_id, is_active, created_at, updated_at) "
                    "VALUES (:sa_id, :tid, TRUE, NOW(), NOW())"
                ),
                {"sa_id": sa_id, "tid": target_id},
            )

    # === 9. Seed attribute values for #329 and #330 ===
    _seed_attr_values(conn, 329)
    _seed_attr_values(conn, 330)

    # === 10. Normalize safe value_text corrections ===
    # Fix typo: Об'єм пам'яти -> Об'єм пам'яті (supplier attr 10697)
    conn.execute(
        sa.text(
            "UPDATE supplier_attribute_values SET supplier_value = 'Об''єм пам''яті' "
            "WHERE supplier_attribute_id = 10697 AND supplier_value = 'Об''єм пам''яти'"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE attribute_values av SET value = 'Об''єм пам''яті', "
            "slug = 'об''єм-пам''яті' "
            "FROM attribute_value_mappings avm "
            "JOIN supplier_attribute_values sav ON sav.id = avm.supplier_attribute_value_id "
            "WHERE avm.attribute_value_id = av.id "
            "AND sav.supplier_attribute_id = 10697 "
            "AND sav.supplier_value = 'Об''єм пам''яти'"
        )
    )

    print("Migration 020 completed successfully.")
    print(f"  - Created {len(NEW_ATTRIBUTES)} new internal attributes")
    print(f"  - Remapped {len(REMAP_FROM_167)} from #167")
    print(f"  - Remapped {len(REMAP_FROM_193)} from #193")
    print(f"  - Remapped {len(REMAP_FROM_206)} from #206")
    print(f"  - Deactivated {len(DEACTIVATE_FROM_206)} from #206")
    print(f"  - Activated + mapped {len(ACTIVATE_AND_MAP)} excluded attrs")
    print(f"  - Created {len(NEW_MAPPING)} new mappings")


def _seed_attr_values(conn, attr_id):
    """Copy distinct existing values into target attribute from its mapped
    supplier attributes (avoids FK issues with existing mappings)."""
    rows = conn.execute(
        sa.text(
            "SELECT DISTINCT av.value, av.slug FROM attribute_value_mappings avm "
            "JOIN supplier_attribute_values sav ON sav.id = avm.supplier_attribute_value_id "
            "JOIN supplier_attributes sa ON sa.id = sav.supplier_attribute_id "
            "JOIN attribute_values av ON av.id = avm.attribute_value_id "
            "JOIN attribute_mappings m ON m.supplier_attribute_id = sa.id "
            "WHERE m.attribute_id = :aid AND avm.is_active = TRUE "
            "AND avm.attribute_value_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM attribute_values av2 WHERE av2.attribute_id = :aid2 AND av2.value = av.value)"
        ),
        {"aid": attr_id, "aid2": attr_id},
    ).fetchall()
    for value, slug in rows:
        conn.execute(
            sa.text(
                "INSERT INTO attribute_values (attribute_id, value, slug, sort, is_active, created_at, updated_at) "
                "VALUES (:aid, :val, :sl, 0, TRUE, NOW(), NOW()) "
                "ON CONFLICT (attribute_id, value) DO NOTHING"
            ),
            {"aid": attr_id, "val": value, "sl": slug},
        )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade():
    """Reverse the taxonomy changes.

    WARNING: Resets all affected mappings back to NULL/inactive.
    Does NOT restore any product data that may have been re-imported.
    """
    conn = op.get_bind()

    # Collect all affected supplier attr ids
    all_ids = (
        [sa_id for sa_id, _ in REMAP_FROM_167]
        + [sa_id for sa_id, _ in REMAP_FROM_193]
        + [sa_id for sa_id, _ in REMAP_FROM_206]
        + [sa_id for sa_id, _ in NEW_MAPPING]
        + [sa_id for sa_id, _, _ in ACTIVATE_AND_MAP]
    )
    for sa_id in all_ids:
        conn.execute(
            sa.text(
                "UPDATE attribute_mappings "
                "SET attribute_id = NULL, is_active = FALSE, updated_at = NOW() "
                "WHERE supplier_attribute_id = :sa_id"
            ),
            {"sa_id": sa_id},
        )

    # Reactivate #206 mappings that were deactivated
    for sa_id in DEACTIVATE_FROM_206:
        conn.execute(
            sa.text(
                "UPDATE attribute_mappings "
                "SET attribute_id = 206, is_active = TRUE, updated_at = NOW() "
                "WHERE supplier_attribute_id = :sa_id"
            ),
            {"sa_id": sa_id},
        )

    # Remove new internal attributes
    for _name, slug, _typ in NEW_ATTRIBUTES:
        conn.execute(
            sa.text("DELETE FROM attributes WHERE slug = :slug"),
            {"slug": slug},
        )

    print("Downgrade 020 completed.")
