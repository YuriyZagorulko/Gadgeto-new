"""Analyze WordPress SQL dump and produce structured data."""
import json, re, os, sys
from collections import defaultdict

DUMP = "/home/yuri/Desktop/my/temp/tempFiles/_wp_analysis/extracted/db_dump.sql"

def read_dump():
    with open(DUMP, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def extract_table(content, table_name):
    # Find all INSERT blocks for this table (they end with -- instead of ;)
    pattern = re.compile(r"INSERT INTO `" + re.escape(table_name) + r"` VALUES(.+?)\n--", re.DOTALL)
    all_rows = []
    for m in pattern.finditer(content):
        rows = parse_values(m.group(1))
        all_rows.extend(rows)
    return all_rows

def parse_values(text):
    rows = []
    cur = []
    val = ""
    inq = False
    i = 0
    while i < len(text):
        c = text[i]
        if inq:
            if c == "\\" and i+1 < len(text):
                val += text[i+1]
                i += 2
                continue
            elif c == "'":
                inq = False
                cur.append(val)
                val = ""
            else:
                val += c
        else:
            if c == "'":
                inq = True
                val = ""
            elif c == "(":
                cur = []
            elif c == ")":
                if cur:
                    rows.append(cur)
                cur = []
        i += 1
    return rows

def main():
    print("Reading WordPress dump...")
    content = read_dump()
    print(f"Size: {len(content)} chars")
    
    # Extract tables
    posts = extract_table(content, "wp_posts")
    postmeta = extract_table(content, "wp_postmeta")
    terms = extract_table(content, "wp_terms")
    term_tax = extract_table(content, "wp_term_taxonomy")
    term_rel = extract_table(content, "wp_term_relationships")
    attr_tax = extract_table(content, "wp_woocommerce_attribute_taxonomies")
    users = extract_table(content, "wp_users")
    wc_orders = extract_table(content, "wp_wc_orders")
    
    print(f"\n=== TABLE COUNTS ===")
    print(f"wp_posts: {len(posts)}")
    print(f"wp_postmeta: {len(postmeta)}")
    print(f"wp_terms: {len(terms)}")
    print(f"wp_term_taxonomy: {len(term_tax)}")
    print(f"wp_term_relationships: {len(term_rel)}")
    print(f"wp_woocommerce_attribute_taxonomies: {len(attr_tax)}")
    print(f"wp_users: {len(users)}")
    print(f"wp_wc_orders: {len(wc_orders)}")
    
    # Categories
    cat_parents = {}
    cat_terms = {}
    for t in term_tax:
        if len(t) >= 5 and t[2] == "product_cat":
            tid = t[1]
            cat_parents[tid] = {"parent": t[4], "count": t[6] if len(t) > 6 else 0}
    for t in terms:
        if len(t) >= 3:
            tid = t[0]
            if tid in cat_parents:
                cat_terms[tid] = {"name": t[1], "slug": t[2], **cat_parents[tid]}
    
    print(f"\n=== CATEGORIES ({len(cat_terms)}) ===")
    for tid in list(cat_terms.keys())[:10]:
        c = cat_terms[tid]
        print(f"  {tid}: {c['name']} (slug={c['slug']}, parent={c['parent']})")
    
    # Products
    products = {}
    for p in posts:
        if len(p) >= 22 and p[5] == "product":
            post_id = p[0]
            products[post_id] = {
                "id": post_id,
                "title": p[8],
                "slug": p[14],
                "status": p[9],
                "content": p[11],
                "excerpt": p[12],
                "meta": {},
            }
    
    # Add meta
    for m in postmeta:
        if len(m) >= 4 and m[1] in products:
            products[m[1]]["meta"][m[2]] = m[3]
    
    print(f"\n=== PRODUCTS ({len(products)}) ===")
    statuses = defaultdict(int)
    for p in products.values():
        statuses[p["status"]] += 1
    for s, c in sorted(statuses.items()):
        print(f"  {s}: {c}")
    
    # Sample
    for pid in list(products.keys())[:3]:
        p = products[pid]
        meta = p.get("meta", {})
        sku = meta.get("_sku", "")
        price = meta.get("_regular_price", "")
        print(f"  ID={pid}: {p['title'][:50]} SKU={sku} Price={price}")
    
    # Output analysis file
    output = {
        "tables": {k: len(v) for k, v in {
            "posts": posts, "postmeta": postmeta, "terms": terms,
            "term_tax": term_tax, "term_rel": term_rel,
            "attr_tax": attr_tax, "users": users, "orders": wc_orders
        }.items()},
        "categories_count": len(cat_terms),
        "products_count": len(products),
        "products_by_status": dict(statuses),
        "attribute_count": len(attr_tax),
    }
    
    outpath = "/home/yuri/Desktop/my/projects/Gadgeto-new/scripts/migration/wp_analysis.json"
    with open(outpath, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nAnalysis saved to {outpath}")
    
    return products, cat_terms

if __name__ == "__main__":
    main()
