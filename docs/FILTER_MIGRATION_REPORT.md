# Category Filter Migration Report

Generated: 2026-08-22
Source: `/home/yuri/Desktop/my/temp/tempFiles/category_filters_export_2026-08-22.json`

## Results

| Metric | Value |
|---|---|
| Export categories | 186 |
| Export filter assignments | 470 |
| Export unique attribute slugs | 149 |
| Resolved categories (in our DB) | 146 |
| Migrated filters | 453 |
| New attributes created | 3 |
| Categories with empty filters | 85 |
| Unresolved categories (not in our DB) | 40 |
| Unresolved attributes | 0 |

## New Attributes Created

- Перевірка та корекція помилок (ECC)
- Обсяг HDD
- Обсяг SSD

## Unresolved Categories (not migrated)

40 categories from the export have no matching category in our PostgreSQL. These are:
- Categories present in WooCommerce but having no products in the CSV export
- Examples: bluray, dvd-discs, gps, coolers-fans, batteries, binding materials
- They can be created in PostgreSQL if needed when products are imported for them

## Attribute Counts by Category (Top 10)

| Category | Filters |
|---|---|
| БФП та принтери | 19 |
| Монітори | 18 |
| Корпуси для ПК | 18 |
| Комп'ютери | 17 |
| Смартфони | 16 |
| Ноутбуки | 16 |
| Планшети | 15 |
| Відеокарти | 12 |
| Моноблоки | 12 |
| Маршрутизатори (роутери) | 11 |

## Verification Script

```bash
python3 scripts/migration/migrate_category_filters.py
```
