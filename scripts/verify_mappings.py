#!/usr/bin/env python3
"""
Mapping verification script.
Reads the authoritative final mapping files from the legacy importer,
normalizes them into DB concepts, and produces a detailed report.

Usage:
    python3 scripts/verify_mappings.py

Output:
    - Console report
    - docs/MAPPING_MIGRATION_REPORT.md (machine-generated)
"""

import json
import os
import sys
from collections import defaultdict, Counter
from pathlib import Path

LEGACY_MAPPING_DIR = Path("/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping")
WC_CATEGORIES_PATH = LEGACY_MAPPING_DIR / "data_from_server" / "woocommerce_categories.json"
CATEGORIES_SEO_PATH = Path("/home/yuri/Desktop/my/temp/tempFiles/CategoriesSEO_Final.json")
OUTPUT_DIR = Path(os.path.dirname(__file__)).parent / "docs"


def load_json(path: Path, name: str):
    """Load JSON file with error handling."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  WARNING: {name} not found at {path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"  ERROR: {name} has invalid JSON: {e}")
        return {}


def verify_category_mappings(cat_map: dict, wc_cats: list, seo_cats: list) -> dict:
    """Verify category_mapping.json against WC categories."""
    report = {}
    report["source_file"] = "category_mapping.json"
    report["total_entries"] = len(cat_map)
    
    # Build WC category index
    wc_by_name = {}
    wc_by_slug = {}
    wc_by_id = {}
    for c in wc_cats:
        wc_by_name[c["name"]] = c
        wc_by_slug[c["slug"]] = c
        wc_by_id[c["id"]] = c
    
    # Check each mapping
    mapped_names = set(cat_map.values())
    missing_internal = []
    found_internal = []
    identity_mappings = 0
    
    for supplier_cat, internal_cat in cat_map.items():
        if internal_cat in wc_by_name:
            found_internal.append(internal_cat)
        else:
            missing_internal.append(internal_cat)
        if supplier_cat == internal_cat:
            identity_mappings += 1
    
    # Find unmapped WC categories (not used as target)
    wc_mapped_targets = set(cat_map.values())
    unmapped_wc_categories = []
    for c in wc_cats:
        if c["name"] not in wc_mapped_targets and c["name"] != "Uncategorized":
            unmapped_wc_categories.append(c["name"])
    
    # Detect supplier-side duplicates (multiple supplier names → same internal cat)
    supplier_duplicates = defaultdict(list)
    for supplier_cat, internal_cat in cat_map.items():
        supplier_duplicates[internal_cat].append(supplier_cat)
    multi_source = {k: v for k, v in supplier_duplicates.items() if len(v) > 1}
    
    # Check SEO coverage
    seo_id_to_slug = {}
    if seo_cats:
        for sc in seo_cats:
            seo_id_to_slug[sc["id"]] = {"slug": sc["slug"], "name": sc["name"], "has_seo": bool(sc.get("seo_title"))}
    
    cat_seo_count = 0
    for internal_cat in found_internal:
        wc_obj = wc_by_name.get(internal_cat)
        if wc_obj and wc_obj.get("id") in seo_id_to_slug:
            if seo_id_to_slug[wc_obj["id"]]["has_seo"]:
                cat_seo_count += 1
    
    report["mapped_to_existing_wc_category"] = len(set(found_internal))
    report["mapped_to_missing_wc_category"] = len(missing_internal)
    report["missing_internal_categories"] = missing_internal[:20]  # first 20
    report["identity_mappings"] = identity_mappings
    report["supplier_side_multi_source_categories"] = len(multi_source)
    report["multi_source_examples"] = dict(list(multi_source.items())[:10])
    report["unmapped_wc_categories"] = unmapped_wc_categories[:20]
    report["wc_categories_with_seo"] = cat_seo_count
    report["total_wc_categories"] = len(wc_cats)
    
    return report


def verify_attribute_mappings(attr_final: dict, attr_remove: dict,
                              attr_value_map: dict, attr_value_remove: dict) -> dict:
    """Verify attribute mapping files."""
    report = {}
    report["source_file"] = "attributes_final.json"
    report["total_entries"] = len(attr_final)
    
    # Collect internal attribute names
    internal_names = set(attr_final.values())
    internal_name_counts = Counter(attr_final.values())
    
    # Find internal names with multiple supplier sources
    multi_source_attrs = {k: v for k, v in internal_name_counts.items() if v > 1}
    
    # Check for unmapped internal names (no target attribute exists)
    # In the legacy system, any name that appears is a valid internal name
    
    # Attribute removal
    report["attribute_remove_file"] = "attribute_remove.json"
    report["attributes_to_remove"] = len(attr_remove)
    removed_in_final = [k for k in attr_remove if k in attr_final]
    report["removed_entries_also_in_final"] = len(removed_in_final)
    report["removed_examples_in_final"] = removed_in_final[:10]
    
    # Value mapping
    report["attribute_value_mapping_file"] = "attribute_value_mapping_final.json"
    report["value_mapped_attrs"] = len(attr_value_map)
    
    # For each value-mapped attribute, count value mappings
    value_map_sizes = {}
    for attr_name, values in attr_value_map.items():
        value_map_sizes[attr_name] = len(values)
    
    report["value_map_sizes_summary"] = {
        "min": min(value_map_sizes.values()) if value_map_sizes else 0,
        "max": max(value_map_sizes.values()) if value_map_sizes else 0,
        "total_values": sum(value_map_sizes.values()),
        "avg": sum(value_map_sizes.values()) / len(value_map_sizes) if value_map_sizes else 0,
    }
    
    # Identity vs non-identity value mappings
    identity_values = 0
    total_value_entries = 0
    for attr_name, values in attr_value_map.items():
        for k, v in values.items():
            total_value_entries += 1
            if k == v:
                identity_values += 1
    
    report["identity_value_mappings"] = identity_values
    report["total_value_mapping_entries"] = total_value_entries
    
    # Value removal rules
    report["attribute_value_remove_file"] = "attribute_value_to_remove.json"
    report["attrs_with_value_removal"] = len(attr_value_remove)
    total_removed_values = sum(len(v) if isinstance(v, list) else 0 for v in attr_value_remove.values())
    report["total_removed_values"] = total_removed_values
    
    # Check attribute names that appear in remove but not in final map
    not_in_final = [k for k in attr_remove if k not in attr_final]
    report["removed_not_in_final"] = len(not_in_final)
    report["removed_not_in_final_examples"] = not_in_final[:10]
    
    report["multi_source_internal_attributes"] = len(multi_source_attrs)
    report["multi_source_attr_examples"] = dict(list(multi_source_attrs.items())[:10])
    
    # Cross-reference: value-mapped attrs that don't exist as internal names
    value_mapped_not_internal = [k for k in attr_value_map if k not in internal_names]
    report["value_mapped_attrs_not_in_internal"] = len(value_mapped_not_internal)
    report["value_mapped_not_internal_examples"] = value_mapped_not_internal[:10]
    
    return report


def verify_legacy_woocommerce_catalog(csv_path: Path, wc_cats: list) -> dict:
    """Verify the legacy WooCommerce CSV export against categories."""
    report = {}
    
    if not csv_path.exists():
        report["error"] = f"CSV export not found at {csv_path}"
        return report
    
    import csv
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    report["total_products_in_csv"] = len(rows)
    
    # Count by supplier
    suppliers = defaultdict(int)
    for r in rows:
        sup = r.get("Мета: supplier_slug", "").strip()
        if not sup:
            sup = "unknown"
        suppliers[sup] += 1
    
    report["products_by_supplier"] = dict(suppliers)
    
    # Count categories used
    category_paths = Counter()
    for r in rows:
        cat = r.get("Категорії", "").strip()
        if cat:
            category_paths[cat] += 1
    
    report["unique_category_paths_in_csv"] = len(category_paths)
    report["top_categories"] = dict(category_paths.most_common(20))
    
    return report


def main():
    print("=" * 70)
    print("GADGETO MAPPING VERIFICATION")
    print("=" * 70)
    
    # Load mapping files
    print("\nLoading mapping files...")
    cat_map = load_json(LEGACY_MAPPING_DIR / "category_mapping.json", "category_mapping.json")
    attr_final = load_json(LEGACY_MAPPING_DIR / "attributes_final.json", "attributes_final.json")
    attr_value_map = load_json(LEGACY_MAPPING_DIR / "attribute_value_mapping_final.json", "attribute_value_mapping_final.json")
    attr_remove = load_json(LEGACY_MAPPING_DIR / "attribute_remove.json", "attribute_remove.json")
    attr_value_remove = load_json(LEGACY_MAPPING_DIR / "attribute_value_to_remove.json", "attribute_value_to_remove.json")
    wc_cats = load_json(WC_CATEGORIES_PATH, "woocommerce_categories.json")
    seo_cats = load_json(CATEGORIES_SEO_PATH, "CategoriesSEO_Final.json")
    
    if not isinstance(wc_cats, list):
        wc_cats = []
    
    # Verify mappings
    cat_report = verify_category_mappings(cat_map, wc_cats, seo_cats)
    attr_report = verify_attribute_mappings(attr_final, attr_remove, attr_value_map, attr_value_remove)
    
    # Verify legacy catalog
    csv_path = LEGACY_MAPPING_DIR.parent / "woocommerce_export.csv"
    catalog_report = verify_legacy_woocommerce_catalog(csv_path, wc_cats)
    
    # Build report
    full_report = {
        "summary": {
            "category_mappings_total": cat_report["total_entries"],
            "attribute_mappings_total": attr_report["total_entries"],
            "attribute_remove_total": attr_report["attributes_to_remove"],
            "attribute_value_mapped_attrs": attr_report["value_mapped_attrs"],
            "attribute_value_remove_attrs": attr_report["attrs_with_value_removal"],
            "wc_categories_total": cat_report["total_wc_categories"],
            "wc_categories_with_seo": cat_report["wc_categories_with_seo"],
        },
        "category_mappings": cat_report,
        "attribute_mappings": attr_report,
        "woocommerce_catalog": catalog_report,
    }
    
    # Print report
    print("\n" + "=" * 70)
    print("VERIFICATION REPORT")
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"  Category mappings: {full_report['summary']['category_mappings_total']}")
    print(f"  Attribute mappings: {full_report['summary']['attribute_mappings_total']}")
    print(f"  Attributes to remove: {full_report['summary']['attribute_remove_total']}")
    print(f"  Value-mapped attributes: {full_report['summary']['attribute_value_mapped_attrs']}")
    print(f"  Value remove rules: {full_report['summary']['attribute_value_remove_attrs']}")
    print(f"  WooCommerce categories: {full_report['summary']['wc_categories_total']}")
    print(f"  Categories with SEO: {full_report['summary']['wc_categories_with_seo']}")
    
    print(f"\n📁 Category Mappings:")
    print(f"  Total entries: {cat_report['total_entries']}")
    print(f"  Mapped to existing WC category: {cat_report['mapped_to_existing_wc_category']}")
    print(f"  Mapped to missing WC category: {cat_report['mapped_to_missing_wc_category']}")
    print(f"  Identity mappings: {cat_report['identity_mappings']}")
    print(f"  Multi-source categories (1 target, many suppliers): {cat_report['supplier_side_multi_source_categories']}")
    print(f"  WC categories with SEO data: {cat_report['wc_categories_with_seo']}/{cat_report['total_wc_categories']}")
    
    if cat_report['missing_internal_categories']:
        print(f"\n  ⚠️ Missing internal categories (not in WC): {len(cat_report['missing_internal_categories'])}")
        for c in cat_report['missing_internal_categories'][:5]:
            print(f"    - {c}")
    
    if cat_report['unmapped_wc_categories']:
        print(f"\n  ℹ️ Unmapped WC categories (no mapping targets them): {len(cat_report['unmapped_wc_categories'])}")
        for c in cat_report['unmapped_wc_categories'][:5]:
            print(f"    - {c}")
    
    print(f"\n⚙️ Attribute Mappings:")
    print(f"  Total entries: {attr_report['total_entries']}")
    print(f"  Unique internal attribute names: {len(set(attr_final.values()))}")
    print(f"  Attributes to remove: {attr_report['attributes_to_remove']}")
    print(f"  Removed also in final map: {attr_report['removed_entries_also_in_final']}")
    print(f"  Value-mapped attributes: {attr_report['value_mapped_attrs']}")
    print(f"  Total value mapping entries: {attr_report['total_value_mapping_entries']}")
    print(f"  Identity value mappings: {attr_report['identity_value_mappings']}")
    print(f"  Attrs with value removal: {attr_report['attrs_with_value_removal']}")
    print(f"  Total removed values: {attr_report['total_removed_values']}")
    print(f"  Multi-source internal attributes: {attr_report['multi_source_internal_attributes']}")
    print(f"  Value-mapped attrs NOT in internal set: {attr_report['value_mapped_attrs_not_in_internal']}")
    
    if attr_report['removed_not_in_final_examples']:
        print(f"\n  ℹ️ Removed attrs not in final map (legacy): {attr_report['removed_not_in_final']}")
    
    print(f"\n📦 WooCommerce Catalog:")
    if "total_products_in_csv" in catalog_report:
        print(f"  Total products in CSV: {catalog_report['total_products_in_csv']}")
        print(f"  By supplier: {catalog_report['products_by_supplier']}")
        print(f"  Unique categories used: {catalog_report['unique_category_paths_in_csv']}")
    
    # Write report to docs
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_path = OUTPUT_DIR / "MAPPING_MIGRATION_REPORT.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Mapping Migration Report\n\n")
        f.write(f"Generated: 2026-08-22\n\n")
        f.write("## Summary\n\n")
        f.write(f"| Metric | Count |\n")
        f.write(f"|---|---|\n")
        for k, v in full_report["summary"].items():
            f.write(f"| {k} | {v} |\n")
        
        f.write("\n## Category Mappings\n\n")
        f.write(f"- Source: `category_mapping.json`\n")
        f.write(f"- Total entries: {cat_report['total_entries']}\n")
        f.write(f"- Mapped to existing WC categories: {cat_report['mapped_to_existing_wc_category']}\n")
        f.write(f"- Mapped to missing WC categories: {cat_report['mapped_to_missing_wc_category']}\n")
        f.write(f"- Identity mappings: {cat_report['identity_mappings']}\n")
        f.write(f"- Multi-source categories: {cat_report['supplier_side_multi_source_categories']}\n")
        f.write(f"- WC categories with SEO: {cat_report['wc_categories_with_seo']}/{cat_report['total_wc_categories']}\n")
        
        if cat_report['missing_internal_categories']:
            f.write(f"\n### Missing Internal Categories (not found in WC categories)\n\n")
            for c in cat_report['missing_internal_categories']:
                f.write(f"- `{c}`\n")
        
        f.write("\n## Attribute Mappings\n\n")
        f.write(f"- Source: `attributes_final.json`\n")
        f.write(f"- Total entries: {attr_report['total_entries']}\n")
        f.write(f"- Unique internal names: {len(set(attr_final.values()))}\n")
        f.write(f"- Attributes to remove: {attr_report['attributes_to_remove']}\n")
        f.write(f"- Removed attrs also in final map: {attr_report['removed_entries_also_in_final']}\n")
        f.write(f"- Value-mapped attributes: {attr_report['value_mapped_attrs']}\n")
        f.write(f"- Total value mapping entries: {attr_report['total_value_mapping_entries']}\n")
        f.write(f"- Identity value mappings: {attr_report['identity_value_mappings']}\n")
        f.write(f"- Attrs with value removal: {attr_report['attrs_with_value_removal']}\n")
        f.write(f"- Multi-source internal attrs: {attr_report['multi_source_internal_attributes']}\n")
    
    print(f"\n✅ Report written to {report_path}")
    return full_report


if __name__ == "__main__":
    main()
