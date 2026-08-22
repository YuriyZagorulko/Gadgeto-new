# Final Mapping Data — Audit & Migration Plan

The files below are the **authoritative, manually curated mapping data**. They are
the source of truth for the new system. They are treated as **read-only reference**;
the long-term goal is to migrate their content into PostgreSQL and edit it via the
admin UI.

Audited directory: `/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping/`

Last audit date: 2026-08-22.

---

## 1. File inventory & semantics

### 1.1 `category_mapping.json` — supplier → internal category (195 entries)

Maps a **supplier category name** (as it appears in the supplier feed) to an
**internal category name** (a WooCommerce category name). The internal name is then
resolved by the category resolver to a full tree path.

```json
{
  "SSD": "SSD-накопичувачі",
  "SSD накопители": "SSD-накопичувачі",
  "Твердотельные накопители": "SSD-накопичувачі",
  "Корпуса для ПК": "Корпуси для ПК",
  "Хаби USB и кард-рідери": "USB-хаби та картрідери"
}
```

Semantics observed:
- Multiple supplier spellings collapse to one internal category.
- Supplier terms are Russian and/or Ukrainian; internal names are Ukrainian.
- The internal name must exist in the WooCommerce category export
  (`woocommerce_categories.json`, 188 cats) — validated at import start.
- Identity mappings (e.g. `SSD-накопичувачі` → `SSD-накопичувачі`) are present;
  there is no "unmapped fallback" category in practice.

### 1.2 `attributes_final.json` — supplier attribute → internal attribute (1,119 entries)

```json
{
  "+12V1": "Роз'єм живлення",
  "+5V": "Роз'єм живлення",
  "DisplayPort": "Display Port",
  "Adaptive Fast Charging (AFC)": "Технології заряджання",
  "Стан": "Стан"
}
```

Semantics:
- Key = supplier attribute name (incl. case/punctuation variants); value = internal
  attribute label (Ukrainian). Many supplier names can produce one internal name.
- A missing mapping means the attribute name is **unknown** → the attribute is
  dropped (logged). No automatic renaming happens.
- Mappings target internal *labels*; the new DB model stores an attribute entity
  (slug + label) and maps supplier names to it.

### 1.3 `attribute_value_mapping_final.json` — internal attribute → value map (186 attrs)

```json
{
  "Швидкість кольорового друку": {
    "0,5 стор/хв": "0,5 стор/хв",
    "15,5 стор/хві": "15,5 стор/хв",
    "40 стор/хв": "40 стор/хв"
  },
  "Діагональ екрану": {
    "1.44\"": "1.44\"",
    "10.1": "10.1",
    "10.1\"": "10.1\""
  }
}
```

- Key = **internal attribute name** (after `attributes_final`); value = table
  {supplier value → internal value}.
- Presence of a table for an attribute means: values not present are **not imported**
  (dropped + logged).
- Absence of a table for an attribute means the supplier value is imported as-is.
- This is a strict "allowlist + enrichment" model for normalized values.
### 1.4 `attribute_remove.json` — attributes to drop entirely (395 keys)

```json
{ "CAS Latency (CL)": true, "Description": true, "HDMI": true, … }
```
`true` is a marker; any supplier attribute in the list is removed at step 1 of the
attribute pipeline.

### 1.5 `attribute_value_to_remove.json` — value sub-list per internal attribute (5 attrs)

```json
{
  "Об'єм пам'яті": ["-", "немає"],
  "Стандарт 80 Plus": ["-"],
  "Батарея": []
}
```
Values listed for an attribute are removed (DC-Link builder applies this).

### 1.6 `data_from_server/woocommerce_categories.json` — WC category tree export

188 categories: `id`, `parent_id`, `name`, `slug`, `count`, `path`. Generated on the
WordPress server by `export_woocommerce_categories.php`. Used to validate that every
mapped internal category exists and to obtain canonical paths.

## 2. How mappings are applied today (pipeline semantics)

1. **Category:** supplier name → `category_mapping.json` → WC category name →
   `woocommerce_categories.json` path → validated → product.Categories = path.
   Fail fast on any missing/unmapped supplier category (import aborts).
2. **Attribute name:** supplier name → `attributes_final.json` → internal name.
   Missing → dropped and logged (`unknown_attributes*.txt`).
3. **Attribute value:** internal attr lookup in `attribute_value_mapping_final.json`;
   if the table exists → mapped value (missing value = drop + log); else → keep original.
4. **Removals:** whole attributes (`attribute_remove.json`) and values
   (`attribute_value_to_remove.json`) never reach the product.

## 3. Consistent interpretation for the new PostgreSQL model

The JSON structures map directly onto normalized tables (see `DATABASE.md` for DDL):

| File | New table(s) |
|---|---|
| `category_mapping.json` | `supplier_categories` (source names, scoped per supplier) + `category_mappings` (→ `categories`) |
| `attributes_final.json` | `supplier_attributes` + `attribute_mappings` (→ `attributes`, scoped per supplier) |
| `attribute_value_mapping_final.json` | `supplier_attribute_values` (scoped to supplier attribute) + `attribute_value_mappings` (→ `attribute_values`, per attribute) |
| `attribute_remove.json` | `is_removed=true` flag on `supplier_attributes` |
| `attribute_value_to_remove.json` | `is_removed=true` flag on `supplier_attribute_values` |
| `woocommerce_categories.json` | seed for `categories` (legacy id kept; parent links via slug/path) |

> Caution: the current JSON does NOT record per-supplier provenance — keys are shared
> by both suppliers. The DB introduces per-supplier scope; identical source strings
> may map to one shared `supplier_*` row (dedup) or to separate rows (per provenance),
> decided during migration (recommended: separate rows per supplier, equal targets —
> safest and reversible).

> Migration step (reversible): archive each JSON into a `mapping_source_json` table
> (file name + sha-256 + full content) in one transaction, then insert parsed rows
> into the normalized tables in a separate transaction. The JSON files stay untouched.

## 4. Category-specific filters (source of truth — legacy)

From the WordPress DB (`woof_by_category_settings`, 187 entries):

```json
[
  { "category": "/",                  "filters": ["product_cat","product_brand"] },
  { "category": "gps-trackers",       "filters": ["pa_kolir","pa_radius-dii","pa_sumisnist"] },
  { "category": "3d-printers",        "filters": [] },
  …
]
```

- `category` keys are category **slugs** (URL-encoded for Cyrillic slugs; orphan
  duplicates at root level appear too — canonicalization needed).
- Filters list = attribute/taxonomy names; empty list → global fallback
  (`product_brand`, `product_cat`).
- The new model replaces this with a `category_filters` join table
  (category_id ↔ attribute_id, with position + enabled), admin-editable.
## 5. Category SEO data (source of truth for category pages)

`CategoriesSEO_Final.json` (187 entries, keyed by WC category id):

```json
{
  "id": 546,
  "parent_id": 0,
  "name": "Інше",
  "slug": "other",
  "count": 17,
  "path": "Інше",
  "focus_keyphrase": "…",
  "seo_title": "… — купити в Україні | Gadgeto",
  "meta_description": "…",
  "description": "<p>…</p>"   // includes generated FAQ block
}
```

Imported to the live site via `import-category-seo.php` into Yoast `wpseo_taxonomy_meta`.
Per-category SEO columns must exist in the new `categories` table (title,
meta_description, focus_keyphrase, description) — imported by `legacy_id`.

## 6. Migration rules (IMPORTANT — do not violate)

1. **Never regenerate/overwrite these JSON files** from supplier data.
2. Map and preserve every entry; unknown/legacy entries are *marked*, not dropped.
3. The mapping-edit facility (admin UI) runs on PostgreSQL rows only.
4. The original JSON files remain in Git at `legacy/final-mapping/` (copied, read-only)
   as migration/reference sources — their originals on disk are untouched.
5. Rows referencing missing target categories/attributes are imported as
   `is_active=false` with an explicit warning, never discarded.

## 7. Contradictions / ambiguities to verify during migration

- **Supplier provenance is not recorded** in the JSON (both suppliers share the same
  files). The migration creates one `supplier_attributes`/`values` row per source
  string as found; the admin can later reconcile duplicates.
- **Case/punctuation variants** — e.g. `Flash карти пам'яті` vs `Flash карти
  пам`яті`, `ы`/`і` variants — every variant is preserved as a distinct source row
  pointing to one canonical target.
- Some names in `attributes_final.json` map to attributes that do not exist in the
  current product catalog (historical feed artifacts).
- The category tree has **duplicates** (orphans at root) — canonicalization needed,
  see `CURRENT_SYSTEM.md §7`.

## 8. Verification checklist after migration

- [ ] 195 category mapping entries present, targets resolve in the category tree
- [ ] 1,119 attribute mapping entries present, targets exist as attributes
- [ ] 186 value-map tables present, keyed by internal attribute names
- [ ] 395 remove entries → `is_removed=true` rows on `supplier_attributes`
- [ ] 5 attributed value-remove subsets imported
- [ ] category-filters config (187) imported and canonicalized
- [ ] category SEO rows imported (187)
- [ ] admin UI edit → DB round-trip verified for each mapping type