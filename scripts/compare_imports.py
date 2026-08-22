#!/usr/bin/env python3
"""
Import compatibility comparison.

Compares the legacy importer CSV output (from WooCommerce import files)
with the new importer output, for a representative sample of products.

Usage:
    python3 scripts/compare_imports.py [--sample N]
"""

import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

LEGACY_CATALOG_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog"

# ── Data structures ──────────────────────────────────────────────────────

@dataclass
class LegacyProduct:
    """Product from legacy WooCommerce CSV exports."""
    sku: str
    name: str
    price: str
    sale_price: str
    categories: str
    images: str
    brand: str
    stock: str
    supplier_slug: str
    supplier_sku: str
    attributes: dict  # {attr_name: attr_value}


@dataclass
class NewProduct:
    """Product from new importer."""
    sku: str
    name: str
    price: int
    category_path: str
    images: list
    brand: str
    in_stock: bool
    supplier: str
    supplier_sku: str
    attributes: list  # [(name, value), ...]


def load_legacy_itlink_csv(path: str) -> dict:
    """Load legacy IT-Link final CSV."""
    products = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row.get("SKU", "").strip()
            if not sku:
                continue
            # Get attributes
            attrs = {}
            for i in range(1, 23):
                nk = f"Назва {i} атрибуту"
                vk = f"{i} значення атрибуту"
                n = row.get(nk, "").strip()
                v = row.get(vk, "").strip()
                if n:
                    attrs[n] = v
            
            products[sku] = LegacyProduct(
                sku=sku,
                name=row.get("Name", "").strip(),
                price=row.get("Regular price", "").strip(),
                sale_price=row.get("Sale price", "").strip(),
                categories=row.get("Categories", "").strip(),
                images=row.get("Images", "").strip(),
                brand=row.get("Brand", "").strip(),
                stock=row.get("In stock?", "0").strip(),
                supplier_slug=row.get("Meta: supplier_slug", "").strip(),
                supplier_sku=row.get("Meta: supplier_sku", "").strip(),
                attributes=attrs,
            )
    return products


def load_legacy_dclink_csv(path: str) -> dict:
    """Load legacy DC-Link final CSV."""
    return load_legacy_itlink_csv(path)  # Same format


def get_new_itlink_products() -> dict:
    """Import products with new importer."""
    from backend.app.imports.itlink import ITLinkImporter
    imp = ITLinkImporter()
    imp.run()
    # The importer doesn't expose products directly, let's get them
    tree = imp.download_feed()
    products = imp.parse_offers(tree)
    result = {}
    for p in products:
        result[p.sku] = p
    return result


def get_new_dclink_products() -> dict:
    """Import products with new importer."""
    from backend.app.imports.dclink import DCLinkImporter
    imp = DCLinkImporter()
    imp.run()
    feed = imp.download_feed()
    products = imp.parse_products(feed)
    result = {}
    for p in products:
        result[p.sku] = p
    return result


def compare_product(legacy: LegacyProduct, new: NewProduct) -> dict:
    """Compare a single product between legacy and new systems."""
    diffs = []
    
    # Name
    if legacy.name != new.name:
        diffs.append(f"name: '{legacy.name[:50]}' vs '{new.name[:50]}'")
    
    # Price (legacy is string, new is int in kopecks)
    try:
        legacy_price = int(float(legacy.price)) if legacy.price else 0
    except ValueError:
        legacy_price = 0
    
    if legacy_price != new.price:
        diffs.append(f"price: {legacy_price} vs {new.price}")
    
    # Categories
    if legacy.categories != new.category_path:
        diffs.append(f"category: '{legacy.categories[:50]}' vs '{new.category_path[:50]}'")
    
    # Stock
    legacy_stock = legacy.stock == "1"
    if legacy_stock != new.in_stock:
        diffs.append(f"stock: {legacy_stock} vs {new.in_stock}")
    
    # Brand
    if legacy.brand != new.brand:
        diffs.append(f"brand: '{legacy.brand}' vs '{new.brand}'")
    
    # Attributes
    legacy_attr_count = len(legacy.attributes)
    new_attr_count = len(new.attributes)
    if legacy_attr_count != new_attr_count:
        legacy_attrs_set = set(legacy.attributes.keys())
        new_attrs_set = set(a[0] for a in new.attributes)
        missing_in_new = legacy_attrs_set - new_attrs_set
        extra_in_new = new_attrs_set - legacy_attrs_set
        if missing_in_new:
            diffs.append(f"attrs missing in new: {missing_in_new}")
        if extra_in_new:
            diffs.append(f"attrs extra in new: {extra_in_new}")
    
    return {
        "sku": legacy.sku,
        "diff_count": len(diffs),
        "diffs": diffs,
        "matches": len(diffs) == 0,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compare imports")
    parser.add_argument("--sample", type=int, default=20, help="Sample size per supplier")
    args = parser.parse_args()
    
    sample_size = args.sample
    
    # Load legacy CSVs
    itlink_csv = os.path.join(LEGACY_CATALOG_DIR, "IT-link", "woocommerce_import_itlink_final.csv")
    dclink_csv = os.path.join(LEGACY_CATALOG_DIR, "DC-Link", "woocommerce_import_dclink_final.csv")
    
    print("=" * 70)
    print("IMPORT COMPATIBILITY COMPARISON")
    print("=" * 70)
    
    # ── IT-Link comparison ──
    print("\n📦 IT-Link Products")
    print("-" * 50)
    legacy_itlink = load_legacy_itlink_csv(itlink_csv)
    new_itlink = get_new_itlink_products()
    
    print(f"  Legacy CSV products: {len(legacy_itlink)}")
    print(f"  New importer products: {len(new_itlink)}")
    
    # Find common SKUs
    common = set(legacy_itlink.keys()) & set(new_itlink.keys())
    missing_in_new = set(legacy_itlink.keys()) - set(new_itlink.keys())
    extra_in_new = set(new_itlink.keys()) - set(legacy_itlink.keys())
    
    print(f"  Common SKUs: {len(common)}")
    print(f"  Missing in new importer: {len(missing_in_new)}")
    print(f"  Extra in new importer: {len(extra_in_new)}")
    
    if missing_in_new:
        print(f"  Missing samples: {list(missing_in_new)[:5]}")
    
    # Compare sample
    common_list = sorted(common)
    sample = common_list[:sample_size]
    
    comparison_stats = {"matched": 0, "differ": 0, "differences": []}
    
    for sku in sample:
        l = legacy_itlink[sku]
        n = new_itlink[sku]
        result = compare_product(l, n)
        if result["matches"]:
            comparison_stats["matched"] += 1
        else:
            comparison_stats["differ"] += 1
            comparison_stats["differences"].append(result)
    
    print(f"\n  Sampled comparison ({sample_size} products):")
    print(f"    Matched: {comparison_stats['matched']}")
    print(f"    Differ: {comparison_stats['differ']}")
    
    for d in comparison_stats["differences"][:5]:
        print(f"\n    SKU {d['sku']}: {len(d['diffs'])} differences")
        for diff in d['diffs']:
            print(f"      - {diff}")
    
    # ── DC-Link comparison ──
    print("\n📦 DC-Link Products")
    print("-" * 50)
    legacy_dclink = load_legacy_dclink_csv(dclink_csv)
    new_dclink = get_new_dclink_products()
    
    print(f"  Legacy CSV products: {len(legacy_dclink)}")
    print(f"  New importer products: {len(new_dclink)}")
    
    common = set(legacy_dclink.keys()) & set(new_dclink.keys())
    missing_in_new = set(legacy_dclink.keys()) - set(new_dclink.keys())
    extra_in_new = set(new_dclink.keys()) - set(legacy_dclink.keys())
    
    print(f"  Common SKUs: {len(common)}")
    print(f"  Missing in new importer: {len(missing_in_new)}")
    print(f"  Extra in new importer: {len(extra_in_new)}")
    
    common_list = sorted(common)
    sample = common_list[:sample_size]
    
    comparison_stats = {"matched": 0, "differ": 0, "differences": []}
    
    for sku in sample:
        l = legacy_dclink[sku]
        n = new_dclink[sku]
        result = compare_product(l, n)
        if result["matches"]:
            comparison_stats["matched"] += 1
        else:
            comparison_stats["differ"] += 1
            comparison_stats["differences"].append(result)
    
    print(f"\n  Sampled comparison ({sample_size} products):")
    print(f"    Matched: {comparison_stats['matched']}")
    print(f"    Differ: {comparison_stats['differ']}")
    
    for d in comparison_stats["differences"][:5]:
        print(f"\n    SKU {d['sku']}: {len(d['diffs'])} differences")
        for diff in d['diffs']:
            print(f"      - {diff}")


if __name__ == "__main__":
    main()
