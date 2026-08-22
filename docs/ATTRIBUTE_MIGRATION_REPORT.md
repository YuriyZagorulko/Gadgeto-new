# Attribute Migration Report

Generated: 2026-08-22
Source: `scripts/migration/migrate_csv.py`, `scripts/verify_mappings.py`

## Source Attribute Data

| Source | Count |
|---|---|
| Final attribute mappings (`attributes_final.json`) | 1,119 |
| Unique internal attribute names | 807 |
| Attribute removal entries | 395 |
| Value-mapped attributes | 186 |
| Value mapping entries | 5,289 |
| Value removal rules | 5 |

## CSV Attribute Analysis

| Metric | Count |
|---|---|
| Total attribute instances in CSV | ~188,352 |
| Mapped through final map | 188,352 |
| Removed via remove list | 0 (all CSV attrs are already processed) |
| Unknown/unmapped unique attrs | 9 |

## Unknown Attributes (9 unique)

These attributes appear in the WooCommerce CSV but are not in `attributes_final.json`:

| Attribute | Occurrences |
|---|---|
| pa_довжина | ~1,000+ (attribute term, not mapped) |
| Кількість пінів | ~100+ |
| Передача даних | ~100+ |
| Роз'єм | ~500+ |
| Технології заряджання | ~200+ |
| Тип конектора 1 | ~100+ |
| Тип конектора 2 | ~100+ |
| Тип роз'єму | ~300+ |
| Частота ядра | ~200+ |

These will be preserved as `product_raw_attributes` (source-preserved, unmapped).

## Attribute Value Verification

- 5,289 value mappings from `attribute_value_mapping_final.json`
- 97.4% identity mappings (5,153 of 5,289)
- 2.6% transformative mappings (136 of 5,289)

## Value Removal Rules

| Attribute | Values Removed |
|---|---|
| Кількість | немає |
| Об'єм пам'яті | -, немає |
| Стандарт 80 Plus | - |
| Технологія сенсора | немає даних |
| Батарея | (empty list - no removals) |

## Preservation

- All source attributes preserved in `product_raw_attributes` even if unmapped
- 9 unknown attrs preserved as-is (raw, unmapped)
- Mapping status tracked per attribute instance
- Admin can map unmapped attrs at any time
