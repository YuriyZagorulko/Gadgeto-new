#!/usr/bin/env python3
"""Migrate category filters from Zagorulko export to PostgreSQL."""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

EXPORT = "/home/yuri/Desktop/my/temp/tempFiles/category_filters_export_2026-08-22.json"
LABELS = "/home/yuri/Desktop/my/temp/tempFiles/_wp_analysis/extracted/public_html/filter_export/attributes.json"
WC_CATS = "/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping/data_from_server/woocommerce_categories.json"
DB = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"

def slugify(s):
    if not s: return ""
    s = s.strip().lower().replace("'", "-")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9а-яіїєґ '-]", "-", s)).strip("-")[:200]

def load_json(p):
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def main():
    import psycopg2, psycopg2.extras
    
    export = load_json(EXPORT)
    pa_label = {a["taxonomy"]: a["label"] for a in load_json(LABELS)}
    wc_list = load_json(WC_CATS)
    wc_slug_name = {c["slug"]: c["name"] for c in wc_list}
    wc_name_slug = {c["name"]: c["slug"] for c in wc_list}
    
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("SELECT id, name, slug FROM categories")
    our_cats = {r["name"]: r for r in cur.fetchall()}
    
    cur.execute("SELECT id, name FROM attributes")
    our_attrs = {r["name"]: r for r in cur.fetchall()}
    
    print("=" * 70)
    print("CATEGORY FILTER MIGRATION")
    print("=" * 70)
    print(f"\nExport categories: {len(export['categories'])}")
    
    export_filters = sum(len(c.get("filters", [])) for c in export["categories"].values())
    print(f"Export filter assignments: {export_filters}")
    
    # Map categories: export slug -> our category
    mapped_cats = {}
    for eslug, ecfg in export["categories"].items():
        wc_name = wc_slug_name.get(eslug) or ecfg.get("category_name", "")
        if wc_name in our_cats:
            mapped_cats[eslug] = our_cats[wc_name]
    
    print(f"Resolved categories: {len(mapped_cats)}/{len(export['categories'])}")
    unmapped = set(export["categories"].keys()) - set(mapped_cats.keys())
    if unmapped:
        print(f"Unresolved: {len(unmapped)}")
        for u in sorted(unmapped)[:10]:
            print(f"  {u}")
    
    # Clear existing filters
    cat_ids = [c["id"] for c in mapped_cats.values()]
    if cat_ids:
        cur.execute("DELETE FROM category_filters WHERE category_id = ANY(%s)", (cat_ids,))
        print(f"\nCleared old filters: {cur.rowcount}")
    
    # Create missing attributes
    all_pa = set()
    for ecfg in export["categories"].values():
        for f in ecfg.get("filters", []):
            all_pa.add(f if isinstance(f, str) else f.get("slug", ""))
    
    new_attrs = []
    for pa in sorted(all_pa):
        label = pa_label.get(pa, pa.replace("pa_", "").replace("-", " ").title())
        if label not in our_attrs:
            aslug = slugify(label) or "attr"
            cur.execute("INSERT INTO attributes (slug,name,type,is_global,is_filterable,created_at,updated_at) VALUES(%s,%s,'text',true,true,NOW(),NOW()) ON CONFLICT (slug) DO NOTHING", (aslug, label))
            if cur.rowcount > 0:
                new_attrs.append(label)
                cur.execute("SELECT id,name FROM attributes WHERE slug=%s", (aslug,))
                r = cur.fetchone()
                if r: our_attrs[r["name"]] = r
    
    print(f"\nCreated {len(new_attrs)} new attributes: {new_attrs}")
    
    # Migrate filters
    migrated = 0
    unresolved_attrs = []
    
    for eslug, ecfg in export["categories"].items():
        if eslug not in mapped_cats: continue
        cat = mapped_cats[eslug]
        filters = ecfg.get("filters", [])
        if not filters: continue
        
        for pos, f in enumerate(filters):
            pa = f if isinstance(f, str) else f.get("slug", "")
            enabled = True if isinstance(f, str) else f.get("enabled", True)
            label = pa_label.get(pa, "")
            if not label: label = pa.replace("pa_", "").replace("-", " ").title()
            
            attr = our_attrs.get(label)
            if not attr:
                unresolved_attrs.append(pa)
                continue
            
            ftype = "multi-select"
            cur.execute("""
                INSERT INTO category_filters (category_id, attribute_id, position, enabled, filter_type, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,NOW(),NOW())
                ON CONFLICT (category_id, attribute_id) DO UPDATE SET position=EXCLUDED.position, enabled=EXCLUDED.enabled
            """, (cat["id"], attr["id"], pos, enabled, ftype))
            migrated += 1
    
    print(f"\nMigrated: {migrated} filters")
    if unresolved_attrs:
        print(f"Unresolved attrs ({len(unresolved_attrs)}): {unresolved_attrs[:15]}")
    
    # Verify
    cur.execute("SELECT count(*) FROM category_filters")
    print(f"\nFinal DB count: {cur.fetchone()['count']}")
    
    cur.execute("""
        SELECT c.name, count(*) as cnt FROM category_filters cf
        JOIN categories c ON c.id=cf.category_id
        GROUP BY c.name ORDER BY cnt DESC LIMIT 10
    """)
    print("Top categories:")
    for r in cur.fetchall():
        print(f"  {r['name']}: {r['cnt']}")
    
    conn.close()
    print("\n[DONE]")

if __name__ == "__main__":
    main()
