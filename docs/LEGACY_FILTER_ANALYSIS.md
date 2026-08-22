# Legacy Filter Analysis - HUSKY + Zagorulko Category Filters

## Source Systems

| Plugin | Location | Version |
|---|---|---|
| HUSKY (Products Filter Professional for WooCommerce) | `wp-content/plugins/woocommerce-products-filter/` | Unknown (138KB index.php) |
| Zagorulko Category Filters for HUSKY | `wp-content/plugins/zagorulko-category-filters-for-husky/` | 1.0.3 |

## Where Filter Configuration is Stored

### Primary Source: `export_filters_data.php` Output

The WordPress backup contains a custom PHP script `export_filters_data.php` that was written to export the filter configuration for migration purposes.

It produced 3 files in `filter_export/`:

| File | Entries | Purpose |
|---|---|---|
| `categories.json` | 195 | All WooCommerce product categories |
| `attributes.json` | 198 | All WooCommerce product attributes (pa_* taxonomies) used as filters |
| `category_attribute_usage.json` | 99 | Category -> [attribute_slug] mappings |

### The HUSKY Plugin Options (EMPTY in backup)

The Zagorulko plugin stores configuration in WordPress option `woof_by_category_settings`. In this backup this option is empty (serialized empty string), possibly because:
- The configuration was stored in a different way in production
- The backup was taken at a specific moment
- The option was not serialized during backup

### The Database Custom Tables

Found in wp_ database:
- `wp_woof_sd` - 1 row (preset configuration)
- Other HUSKY tables exist but contain mainly system/structural data

## Filter Configuration Extracted

### Category-Attribute Mappings

- 99 categories have filter configurations
- 482 total filter assignments (category-attribute pairs)
- Average: ~4.9 filters per category
- Most filters per category: 24 (Комп'ютери)
- Least: 1

### Top Attributes Used as Filters

| Attribute Slug | Categories | Label |
|---|---|---|
| pa_kolir | 64 | Колір |
| pa_kilkist | 29 | Кількість |
| pa_form-faktor | 20 | Форм-фактор |
| pa_material-korpusu | 13 | Матеріал корпусу |
| pa_sumisnist | 12 | Сумісність |
| pa_sumisnii-brend | 11 | Сумісний бренд |
| pa_interfeisi | 11 | Інтерфейси |
| pa_diagonal-ekranu | 9 | Діагональ екрану |
| pa_ob-iem-pam-iati | 9 | Об'єм пам'яті |
| pa_operativna-pam-iat | 9 | Оперативна пам'ять |

### Example: Laptops (category ID 131)

Filters: 23 attributes including:
- Діагональ екрану
- Процесор
- Оперативна пам'ять
- Об'єм пам'яті
- Обсяг SSD
- Операційна система
- Графічний процесор
- Колір
- Частота оновлення
- Роздільна здатність
- Веб-камера
- Сенсорний екран
- Частота процесора
- Матеріал корпусу

### Example: Monitors (category ID 410 subcategory)

Filters include:
- Діагональ екрану
- Роздільна здатність
- Частота оновлення
- Інтерфейси
- Колір

### Example: Smartphones (category ID 29)

Filters: 21 attributes including:
- Процесор
- Оперативна пам'ять
- Об'єм пам'яті
- Діагональ екрану
- Основна камера
- Ємність акумулятора
- Швидка зарядка
- Стандарт зв'язку
- Роздільна здатність
- Матеріал корпусу
- Спалах основної камери
- Формат SIM-карти

## Migration to PostgreSQL

The `category_attribute_usage.json` data will be used as the source for filter migration.

Each `pa_*` slug maps to a HUSKY attribute label which maps to our PostgreSQL attribute name.

160 of 198 HUSKY attributes map directly to our 162 PostgreSQL attributes.
38 unmapped attributes are WooCommerce-specific or feature-level attributes not relevant as filters in the new system.

## Conclusion

The legacy filter configuration IS recoverable from the `filter_export/` files.
The `category_attribute_usage.json` with 99 categories and 482 filter assignments is the authoritative source.
The new system will store these in the `category_filters` table with proper category/attribute FK references.
