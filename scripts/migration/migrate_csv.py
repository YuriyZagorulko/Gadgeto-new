#!/usr/bin/env python3
"""CSV migration: load WooCommerce CSV into PostgreSQL staging and analyze."""
import csv, json, os, re, sys, uuid
from collections import defaultdict

LEGACY = "/home/yuri/Desktop/my/projects/gedgeto/catalog"
CSV_PATH = os.path.join(LEGACY, "woocommerce_export.csv")
MAPPING_DIR = os.path.join(LEGACY, "final data mapping")
CAT_MAP_PATH = os.path.join(MAPPING_DIR, "category_mapping.json")
ATTR_FINAL_PATH = os.path.join(MAPPING_DIR, "attributes_final.json")
ATTR_REMOVE_PATH = os.path.join(MAPPING_DIR, "attribute_remove.json")
WC_CATS_PATH = os.path.join(MAPPING_DIR, "data_from_server", "woocommerce_categories.json")

DB_URL = os.getenv("DATABASE_URL", "postgresql:gadgeto:gadgeto@localhost:5432/gadgeto")

def dsn():
    u = DB_URL
    for pfx in ["postgresql+asyncpg://", "postgresql://", "postgres://"]:
        if u.startswith(pfx):
            return "postgresql://gadgeto:gadgeto@localhost:5432/gadgeto"
    return u

def num_val(v):
    try: return int(float(str(v).replace(",",".").replace(" ","")))
    except: return None

def slugify(text):
    if not text: return "untitled"
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")[:200]

def main():
    dry_run = "--execute" not in sys.argv
    print("="*70)
    print(f"{'DRY RUN' if dry_run else 'EXECUTION'} - Gadgeto CSV Catalog Migration")
    print("="*70)

    # Load CSV
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"\n[CSV] Rows: {len(rows)}, Columns: {len(reader.fieldnames)}")

    # Stats
    stats = {
        "total": len(rows), "with_sku": 0, "with_price": 0, "with_cat": 0,
        "with_img": 0, "published": 0, "by_supplier": defaultdict(int)
    }
    for r in rows:
        if r.get("\u0410\u0440\u0442\u0438\u043a\u0443\u043b","").strip(): stats["with_sku"] += 1
        if r.get("\u0417\u0432\u0438\u0447\u0430\u0439\u043d\u0430 \u0446\u0456\u043d\u0430","").strip(): stats["with_price"] += 1
        if r.get("\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457","").strip(): stats["with_cat"] += 1
        if r.get("\u0417\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u043d\u044f","").strip(): stats["with_img"] += 1
        if r.get("\u041e\u043f\u0443\u0431\u043b\u0456\u043a\u043e\u0432\u0430\u043d\u043e","").strip() == "1": stats["published"] += 1
        sup = r.get("\u041c\u0435\u0442\u0430: supplier_slug","").strip() or "unknown"
        stats["by_supplier"][sup] += 1

    print(f"[CSV] With SKU: {stats['with_sku']}")
    print(f"[CSV] With price: {stats['with_price']}")
    print(f"[CSV] With categories: {stats['with_cat']}")
    print(f"[CSV] With images: {stats['with_img']}")
    print(f"[CSV] Published: {stats['published']}/{len(rows)}")
    print(f"[CSV] By supplier: {dict(stats['by_supplier'])}")

    # Category analysis
    csv_paths = set()
    for r in rows:
        c = r.get("\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457","").strip()
        if c: csv_paths.add(c)
    csv_names = set()
    for p in csv_paths:
        for seg in p.split(" > "):
            s = seg.strip()
            if s: csv_names.add(s)
    print(f"\n[CAT] CSV paths: {len(csv_paths)}, names: {len(csv_names)}")

    with open(WC_CATS_PATH) as f:
        wc_cats = json.load(f)
    wc_names = {c["name"] for c in wc_cats}
    only_in_csv = csv_names - wc_names
    only_in_wc = wc_names - csv_names
    print(f"[CAT] WC cats: {len(wc_cats)}, Not in WC: {len(only_in_csv)}, Not in CSV: {len(only_in_wc)}")
    for n in sorted(only_in_csv)[:15]:
        print(f"  CSV-only: {n}")

    # Attribute analysis
    with open(ATTR_FINAL_PATH) as f: attr_final = json.load(f)
    with open(ATTR_REMOVE_PATH) as f: attr_remove = set(json.load(f).keys())
    attr_unmapped = set()
    attr_mapped = 0; attr_skipped = 0; attr_unknown = 0
    for r in rows:
        for i in range(1, 23):
            n = r.get(f"\u041d\u0430\u0437\u0432\u0430 {i} \u0430\u0442\u0440\u0438\u0431\u0443\u0442\u0443")
            if not n or not n.strip(): continue
            n = n.strip()
            if n in attr_final: attr_mapped += 1
            elif n in attr_remove: attr_skipped += 1
            else: attr_unmapped.add(n); attr_unknown += 1
    print(f"\n[ATTR] Mapped: {attr_mapped}, Removed: {attr_skipped}, Unknown: {len(attr_unmapped)}")
    for n in sorted(attr_unmapped)[:20]:
        print(f"  Unmapped: {n}")

    print("\n[DONE] Analysis complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
