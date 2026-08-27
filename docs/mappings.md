# Mapping System

For the comprehensive mapping data audit, see `docs/DATA_MAPPING.md`.

## Overview

The mapping system translates between supplier data and the internal catalog.
Mappings are stored in PostgreSQL and administered via the admin UI.
Legacy JSON mapping files are archived as reference and should not be modified.

## Mapping Types

### 1. Category Mappings

Maps a **supplier category name** (as it appears in the supplier feed) to an
**internal category** in the catalog.

- Stored in `category_mappings` table.
- Multiple supplier spellings can collapse to one internal category.
- Admin-editable via the mapping UI.
- Unresolved mappings are visible for manual reconciliation.

### 2. Attribute Mappings

Maps a **supplier attribute name** to an **internal attribute**.

- Stored in `attribute_mappings` table.
- Many supplier names can produce one internal attribute.
- Missing mapping means the attribute is dropped (logged).

### 3. Attribute Value Mappings

Maps a **supplier attribute value** to an **internal attribute value**.

- Stored in `attribute_value_mappings` table.
- If a mapping table exists for an attribute but the supplier value is missing
  → the value is dropped and logged.
- If no mapping table exists for the attribute → supplier value is kept as-is.
- NULL target = "remove this value" (preserves allowlist semantics).

## Exclusion Mappings

Excluded attributes/values are represented as mappings marked:
**`Не імпортувати`**

Do not create a separate removal system unless explicitly requested.

## Mapping CRUD

All mapping types support:

- Search, sorting, pagination
- Create, read, update, delete
- Enable/disable toggles
- Unresolved mapping visibility

**Deletion semantics**: Deleting a mapping deletes **only the mapping rule**,
never the underlying category, attribute, attribute value, or supplier entity.

## Legacy Data Handling

For imported legacy mappings:

- Preserve valid mappings; avoid duplicates.
- Prefer idempotent upserts.
- Never overwrite valid mappings with empty values.
- Do not invent internal entities when a match cannot be established.
- Keep unresolved mappings visible and editable.

## Channel Mappings (Rozetka)

In addition to supplier mappings, the system supports **channel mappings** for
sales channels such as Rozetka. These map internal entities → channel entities:

- Internal category → Rozetka category ID
- Internal attribute → Rozetka attribute ID (scoped to Rozetka category)
- Internal attribute value → Rozetka attribute value

Channel mappings follow the same CRUD, search, and pagination semantics as
supplier mappings. See `.cline/skills/rozetka/SKILL.md` for details.

## Key Tables

| Table | Description |
|-------|-------------|
| `category_mappings` | Maps `supplier_category_id → category_id` |
| `attribute_mappings` | Maps `supplier_attribute_id → attribute_id` |
| `attribute_value_mappings` | Maps `supplier_attribute_value_id → attribute_value_id` (NULL = drop) |
| `supplier_categories` | Supplier category names (verbatim, per-supplier) |
| `supplier_attributes` | Supplier attribute names (verbatim, per-supplier) |
| `supplier_attribute_values` | Supplier attribute values (verbatim, per-supplier) |

## Related Documentation

- `docs/DATA_MAPPING.md` — complete mapping data audit with file contents
- `docs/DATABASE.md` — database schema for mapping tables
- `.cline/skills/rozetka/SKILL.md` — Rozetka channel mapping specifics
- `.cline/skills/supplier-import/SKILL.md` — import pipeline that uses mappings