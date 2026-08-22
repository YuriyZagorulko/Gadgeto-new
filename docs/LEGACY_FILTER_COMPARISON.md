# Legacy Filter Comparison: Export vs WordPress Backup

## Sources Compared

| Source | File | Entries |
|---|---|---|
| Export (Zagorulko) | `category_filters_export_2026-08-22.json` | 186 categories, 470 filter assignments |
| WordPress DB (via export_filters_data.php) | `filter_export/category_attribute_usage.json` | 99 categories, 482 filter assignments |
| PostgreSQL (before migration) | `category_filters` table | 98 categories, 476 filter assignments |

## Category Resolution

| Metric | Export vs WordPress DB |
|---|---|
| Categories in export | 186 |
| Categories with filters in export | 101 (85 empty) |
| Categories with filters in WP DB | 99 |
| Common categories with filters | 99 |
| Export-only categories (with filters) | 2 |
| WP DB-only categories (with filters) | 0 |

## Filter Counts

| Metric | Count |
|---|---|
| Export total filter assignments | 470 |
| WP DB total filter assignments | 482 |
| Migrated to PostgreSQL | 453 |
| Unresolved (category not in our DB) | 17 (from 40 unmapped export categories) |

## Attribute Coverage

| Metric | Count |
|---|---|
| Unique attribute slugs in export | 149 |
| Mapped to PostgreSQL attributes | 146 |
| Unmapped (created as new) | 3 (ECC, HDD size, SSD size) |
| HUSKY attributes.json total | 198 |

## Conclusion

The export file is the AUTHORITATIVE source for category filter configuration. It contains:
- 186 categories with proper WC slugs and names
- 101 categories with filter assignments (470 total)
- Ordered filter lists (preserving position)
- Filter names (via HUSKY attributes.json mapping)
- Global filter defaults

The WordPress DB export (category_attribute_usage.json) was derived from the same active configuration and aligns closely with the dedicated export file.

The migration uses the export file as primary source.
