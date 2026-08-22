# Mapping Migration Report

Generated: 2026-08-22  
Script: `scripts/verify_mappings.py`  
Source: `/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping/`

## Summary

| Mapping File | Entries | Status |
|---|---|---|
| `category_mapping.json` | 195 | ✅ Migrated |
| `attributes_final.json` | 1,119 | ✅ Migrated |
| `attribute_value_mapping_final.json` | 186 attrs (5,289 values) | ✅ Migrated |
| `attribute_remove.json` | 395 | ✅ Migrated |
| `attribute_value_to_remove.json` | 5 attrs | ✅ Migrated |
| `woocommerce_categories.json` | 188 cats | ✅ Reference |
| `CategoriesSEO_Final.json` | 187 cats | ✅ Reference |

## Category Mapping Verification

- **Source entries**: 195
- **Identity mappings** (supplier name = internal name): 114
- **Multi-source categories** (1 internal target, multiple supplier names): 31
- **Mapped to existing WC category**: 147 out of 150 unique targets
- **Mapped to missing WC category**: 3 (see below)
- **WC categories with SEO data**: 187

### Missing Internal Categories (not in `woocommerce_categories.json`)

These are mapping entries whose target does not exist as a WC category:
1. `Відеокомутатори` — likely a new category not yet created in WC
2. `Окуляри для комп’ютера` — typo variant (uses `'` versus standard `'`)

### Unmapped WC Categories (not targeted by any mapping)

20 WC categories have no supplier mapping targeting them. These are either:
- Root container categories (`Інше`, `Аксесуари`)
- Categories from the `mine` (manual) supplier
- Historical categories no longer used by suppliers

### Conflict Detection

No mapping conflicts detected. Each supplier category maps to exactly one internal category.

## Attribute Mapping Verification

- **Source entries**: 1,119
- **Unique internal attribute names**: 807
- **Multi-source internal attributes**: 71 (multiple supplier names → same internal name)
- **Attributes to remove**: 395
- **Removed attrs also in final map**: 367 (these are attributes that have a mapping but are also flagged for removal)
- **Removed attrs NOT in final map**: 28 (these are historical artifacts)

### Value Mapping Verification

- **Value-mapped attributes**: 186
- **Total value mapping entries**: 5,289
- **Identity value mappings**: 5,153 (97.4%) — most values map 1:1
- **Non-identity mappings**: 136 (2.6%) — supplier values are transformed

### Value Removal Verification

- **Attrs with removal rules**: 5
- **Total removed values**: 5
- **Rules**:
  - `Кількість`: removes `немає`
  - `Об'єм пам'яті`: removes `-`, `немає`
  - `Стандарт 80 Plus`: removes `-`
  - `Технологія сенсора`: removes `немає даних`
  - `Батарея`: empty list (no removals, attribute kept as-is)

## WooCommerce Catalog Snapshot

- **Total products in CSV**: 22,505
- **By supplier**: IT-Link 741, DC-Link 21,746, mine 10, unknown 8
- **Unique categories used**: 139
- **Products without SKU**: ~20

## Import Pipeline Compatibility

| Component | Legacy | New | Status |
|---|---|---|---|
| Category resolution | `category_mapping.json` → WC path | Same mapping | ✅ Compatible |
| Attribute remove | `attribute_remove.json` | Same file | ✅ Compatible |
| Attribute name map | `attributes_final.json` | Same file | ✅ Compatible |
| Attribute value map | `attribute_value_mapping_final.json` | Same file | ✅ Compatible |
| Value remove | `attribute_value_to_remove.json` | Same file | ✅ Compatible |
| Attribute merging | `merge_attributes()` with `\|` separator | Same logic | ✅ Compatible |
| Unknown logging | `unknown_*.txt` files | `import_logs` | 🔄 Improved |
| Fail-fast on categories | Yes | Same | ✅ Compatible |

## Rerun Verification

```bash
cd /home/yuri/Desktop/my/projects/Gadgeto-new
python3 scripts/verify_mappings.py
```

This script reads directly from the authoritative JSON files and produces a comparison report. No database connection required.
