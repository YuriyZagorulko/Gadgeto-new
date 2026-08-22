# Category Migration Report

Generated: 2026-08-22
Source: `scripts/migration/migrate_csv.py`

## Source Categories

| Source | Count |
|---|---|
| WooCommerce CSV unique paths | 139 |
| WooCommerce CSV unique names | 147 |
| WC categories JSON (`woocommerce_categories.json`) | 188 |
| Final mapping entries | 195 |

## Cross-Reference

| Metric | Count |
|---|---|
| CSV names matching WC categories | 147 (100%) |
| CSV names NOT in WC categories | 0 |
| WC categories NOT in CSV paths | 41 |
| Category mappings (supplier->internal) | 195 |
| Unique internal category targets | ~150 |

## Category Hierarchy

- Root categories: ~15 (from WC categories JSON)
- Leaf categories: ~100+
- Maximum depth: 4-5 levels (e.g. "Комп'ютери > Периферія > Кабелі > ...")

## Resolution

- Category mapping uses `category_mapping.json` for supplier->internal name resolution
- Paths are built from the WC categories `path` field
- Unmapped WC categories (41) are admin/structural categories (not targeted by any supplier mapping)
- All 147 CSV category names exist in the WC categories JSON - no orphan CSV categories

## Target Migrated Categories

| Status | Count |
|---|---|
| To be created in PostgreSQL | ~147 |
| With parent/child hierarchy | ~147 |
| With SEO data | 187 (from CategoriesSEO_Final.json) |
| With legacy IDs | 188 (from WC cat IDs) |

## Integrity Checks

- [ ] No duplicate names in migrated categories
- [ ] All parent references valid
- [ ] All CSV category names present
- [ ] All mapping targets present
- [ ] Orphan categories flagged (41 unused WC cats)
