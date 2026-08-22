#!/usr/bin/env python3
"""Stage 1: Load WooCommerce CSV into PostgreSQL staging table."""
import csv, json, os, re, sys, uuid
from collections import defaultdict

LEGACY = "/home/yuri/Desktop/my/projects/gedgeto/catalog"
CSV_PATH = os.path.join(LEGACY, "woocommerce_export.csv")
DB = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"

def num_val(v):
    if not v: return None
    try: return int(float(str(v).replace(",", ".").replace(" ", "")))
    except: return None

def load_mappings():
    """Load and return mapping data."""
    cat_map = {}
    attr_final = {}
    attr_remove = set()
    wc_cats = []
    d = os.path.join(LEGACY, "final data mapping")
    if os.path.exists(os.path.join(d, "category_mapping.json")):
        with open(os.path.join(d, "category_mapping.json")) as f: cat_map = json.load(f)
    if os.path.exists(os.path.join(d, "attributes_final.json")):
        with open(os.path.join(d, "attributes_final.json")) as f: attr_final = json.load(f)
    if os.path.exists(os.path.join(d, "attribute_remove.json")):
        with open(os.path.join(d, "attribute_remove.json")) as f: attr_remove = set(json.load(f).keys())
    if os.path.exists(os.path.join(d, "data_from_server", "woocommerce_categories.json")):
        with open(os.path.join(d, "data_from_server", "woocommerce_categories.json")) as f: wc_cats = json.load(f)
    return cat_map, attr_final, attr_remove, wc_cats

def main():
    dry_run = "--dry-run" in sys.argv
    verify = "--verify" in sys.argv or "--verify-only" in sys.argv
    execute = "--execute" in sys.argv
    
    print("=" * 70)
    print("GADGETO CSV STAGE 1 - LOAD INTO POSTGRESQL")
    print("=" * 70)
    
    if not os.path.exists(CSV_PATH):
        print(f"[ERR] CSV not found: {CSV_PATH}")
        return 1
    
    cat_map, attr_final, attr_remove, wc_cats = load_mappings()
    print(f"[MAP] Category mappings: {len(cat_map)}")
    print(f"[MAP] Attribute mappings: {len(attr_final)}")
    print(f"[MAP] Attribute remove: {len(attr_remove)}")
    print(f"[MAP] WC categories: {len(wc_cats)}")
    
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"\n[CSV] Total rows: {len(rows)}")
    print(f"[CSV] Columns: {len(reader.fieldnames)}")
    
    # Stats
    stats = {"total": 0, "with_sku": 0, "no_sku": 0, "with_price": 0,
             "with_cat": 0, "with_images": 0, "published": 0,
             "attr_instances": 0}
    supplier_counts = defaultdict(int)
    cat_paths = set()
    unmapped_attrs = set()
    
    for row in rows:
        name = (row.get("Назва") or row.get("Name") or "").strip()
        if not name: continue
        
        sku = (row.get("Артикул") or row.get("SKU") or "").strip()
        stats["total"] += 1
        if sku: stats["with_sku"] += 1
        else: stats["no_sku"] += 1
        
        price = (row.get("Звичайна ціна") or row.get("Regular price") or "").strip()
        if price: stats["with_price"] += 1
        
        cat = (row.get("Категорії") or row.get("Categories") or "").strip()
        if cat:
            stats["with_cat"] += 1
            cat_paths.add(cat)
        
        imgs = (row.get("Зображення") or row.get("Images") or "").strip()
        if imgs: stats["with_images"] += 1
        
        pub = (row.get("Опубліковано") or row.get("Published") or "").strip()
        if pub == "1": stats["published"] += 1
        
        sup = (row.get("Мета: supplier_slug") or row.get("Meta: supplier_slug") or "").strip()
        supplier_counts[sup if sup else "unknown"] += 1
        
        for i in range(1, 23):
            n = (row.get(f"Назва {i} атрибуту") or row.get(f"Attribute {i} name") or "").strip()
            v = (row.get(f"{i} значення атрибуту") or row.get(f"Attribute {i} value(s)") or "").strip()
            if n:
                stats["attr_instances"] += 1
                if attr_final and n not in attr_final:
                    unmapped_attrs.add(n)
    
    print(f"\n[STATS] Total: {stats['total']}")
    print(f"[STATS] With SKU: {stats['with_sku']} (no SKU: {stats['no_sku']})")
    print(f"[STATS] With price: {stats['with_price']}")
    print(f"[STATS] With categories: {stats['with_cat']}")
    print(f"[STATS] With images: {stats['with_images']}")
    print(f"[STATS] Published: {stats['published']}")
    print(f"[STATS] By supplier: {dict(supplier_counts)}")
    print(f"[STATS] Unique category paths: {len(cat_paths)}")
    print(f"[STATS] Attribute instances: {stats['attr_instances']}")
    print(f"[STATS] Unmapped unique attrs ({len(unmapped_attrs)}): {sorted(unmapped_attrs)[:15]}")
    
    if dry_run:
        print("\n[DRY RUN] No database changes")
        return 0
    
    if execute or (not dry_run and not verify):
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(DB)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        batch = str(uuid.uuid4())
        print(f"\n[DB] Connected, batch={batch[:12]}...")
        
        cur.execute("DELETE FROM _staging_csv_import")
        
        loaded = 0
        for row in rows:
            name = (row.get("Назва") or row.get("Name") or "").strip()
            if not name: continue
            
            sku = (row.get("Артикул") or row.get("SKU") or "").strip()
            raw_attrs = {}
            raw_list = []
            for i in range(1, 23):
                n = (row.get(f"Назва {i} атрибуту") or "").strip()
                v = (row.get(f"{i} значення атрибуту") or "").strip()
                if n:
                    raw_attrs[n] = v
                    raw_list.append({"name": n, "value": v})
            
            price = num_val(row.get("Звичайна ціна") or row.get("Regular price"))
            sale = num_val(row.get("Ціна зі знижкою") or row.get("Sale price"))
            stock_qty = None
            stock_str = (row.get("В наявності?") or row.get("In stock?") or "0").strip()
            stock_status = "in_stock" if stock_str == "1" else "out_of_stock"
            cat_path = (row.get("Категорії") or row.get("Categories") or "").strip()
            images = (row.get("Зображення") or row.get("Images") or "").strip()[:1000]
            brand = (row.get("Бренди") or row.get("Brand") or "").strip()
            sup_slug = (row.get("Мета: supplier_slug") or "").strip()
            sup_sku = (row.get("Мета: supplier_sku") or "").strip()
            desc = (row.get("Опис") or row.get("Description") or "").strip()[:50000]
            short_desc = (row.get("Короткий опис") or row.get("Short description") or "").strip()[:2000]
            seo_title = (row.get("Мета: _yoast_wpseo_title") or "").strip()[:500]
            seo_desc = (row.get("Мета: _yoast_wpseo_metadesc") or "").strip()[:500]
            seo_kw = (row.get("Мета: _yoast_wpseo_focuskw") or "").strip()[:500]
            
            cur.execute("""
                INSERT INTO _staging_csv_import
                    (source_row, sku, name, price, old_price, stock_qty, stock_status,
                     category_path, images, brand, supplier_slug, supplier_sku,
                     description, short_description, seo_title, seo_description,
                     focus_keyphrase, raw_attrs, raw_attr_array, import_batch)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                json.dumps(row, ensure_ascii=False), sku, name,
                price, sale, stock_qty, stock_status,
                cat_path, images, brand, sup_slug, sup_sku,
                desc, short_desc,
                seo_title, seo_desc, seo_kw,
                json.dumps(raw_attrs, ensure_ascii=False),
                json.dumps(raw_list, ensure_ascii=False) if raw_list else None,
                batch))
            loaded += 1
        
        print(f"[DB] Loaded {loaded} rows into staging")
        
        cur.execute("""
            SELECT count(*) AS cnt, 
                   count(DISTINCT sku) AS unique_sku,
                   count(*) FILTER (WHERE sku IS NULL OR sku = '') AS null_sku
            FROM _staging_csv_import
        """)
        v = cur.fetchone()
        print(f"[DB] Verified: {v['cnt']} rows, {v['unique_sku']} unique SKUs, {v['null_sku']} empty SKUs")
        conn.close()
        print("[DB] Disconnected")
    
    if verify:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT count(*) AS cnt FROM _staging_csv_import")
        v = cur.fetchone()
        print(f"\n[VERIFY] Staging rows: {v['cnt']}")
        conn.close()
    
    print("\n[DONE]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
