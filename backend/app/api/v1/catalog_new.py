"""Production catalog API with PostgreSQL search and filters."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

from app.core.db_connect import get_cursor, DB


@router.get("/categories")
async def list_categories():
    """Return category tree."""
    cur = get_cursor()
    cur.execute("""
        SELECT id, name, slug, parent_id, product_count, COALESCE(seo_title, '') as seo_title
        FROM categories WHERE is_active = true
        ORDER BY COALESCE(sort_order, 0), name
    """)
    cats = cur.fetchall()
    cur.connection.close()
    
    # Build tree
    by_id = {}
    for c in cats:
        by_id[c["id"]] = dict(c, children=[])
    
    roots = []
    for c in by_id.values():
        if c["parent_id"] and c["parent_id"] in by_id:
            by_id[c["parent_id"]]["children"].append(c)
        else:
            roots.append(c)
    
    return {"items": roots, "total": len(cats)}


@router.get("/categories/{slug}")
async def get_category(slug: str):
    """Get category detail with breadcrumbs."""
    cur = get_cursor()
    cur.execute("""
        SELECT id, name, slug, parent_id, description, product_count,
               seo_title, seo_description
        FROM categories WHERE slug = %s
    """, (slug,))
    cat = cur.fetchone()
    if not cat:
        cur.connection.close()
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Children
    cur.execute("""
        SELECT id, name, slug, product_count FROM categories WHERE parent_id = %s
        ORDER BY name
    """, (cat["id"],))
    children = cur.fetchall()
    
    # Breadcrumbs
    breadcrumbs = []
    pid = cat["parent_id"]
    while pid:
        cur.execute("SELECT id, name, slug FROM categories WHERE id = %s", (pid,))
        p = cur.fetchone()
        if p:
            breadcrumbs.insert(0, {"id": p["id"], "name": p["name"], "slug": p["slug"]})
            pid = p["id"] if p["id"] != pid else None
        else:
            break
    
    cur.connection.close()
    
    return {
        "id": cat["id"],
        "name": cat["name"],
        "slug": cat["slug"],
        "description": cat["description"] or "",
        "parent_id": cat["parent_id"],
        "children": children,
        "product_count": cat["product_count"],
        "seo_title": cat["seo_title"] or "",
        "seo_description": cat["seo_description"] or "",
        "breadcrumbs": breadcrumbs,
    }


@router.get("/categories/{slug}/filters")
async def get_category_filters(slug: str):
    """Get filter configuration for a category."""
    cur = get_cursor()
    cur.execute("SELECT id, name FROM categories WHERE slug = %s", (slug,))
    cat = cur.fetchone()
    if not cat:
        cur.connection.close()
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Primary: use category_attributes (new architecture)
    # Fallback: use category_filters (legacy, kept for compatibility)
    cur.execute("""
        SELECT a.id, a.name, a.slug as attr_slug,
               COALESCE(ca.sort_order, cf.position, 0) AS position,
               COALESCE(ca.filter_type, cf.filter_type, NULL) AS filter_type
        FROM category_attributes ca
        JOIN attributes a ON a.id = ca.attribute_id
        LEFT JOIN category_filters cf
            ON cf.category_id = ca.category_id AND cf.attribute_id = ca.attribute_id
        WHERE ca.category_id = %s AND ca.filterable = true
        ORDER BY ca.sort_order, a.name
    """, (cat["id"],))
    filters = cur.fetchall()
    
    # If no category_attributes found, fall back to legacy category_filters
    if not filters:
        cur.execute("""
            SELECT a.id, a.name, a.slug as attr_slug, cf.position, cf.filter_type
            FROM category_filters cf
            JOIN attributes a ON a.id = cf.attribute_id
            WHERE cf.category_id = %s AND cf.enabled = true
            ORDER BY cf.position, a.name
        """, (cat["id"],))
        filters = cur.fetchall()
    
    result = []
    for f in filters:
        # Get available values with counts for this category
        cur.execute("""
            SELECT COALESCE(av.value, pa.value_text, '') AS value,
                   count(*) as cnt
            FROM product_attributes pa
            LEFT JOIN attribute_values av ON av.id = pa.attribute_value_id
            JOIN product_categories pc ON pc.product_id = pa.product_id
            WHERE pa.attribute_id = %s AND pc.category_id = %s
            GROUP BY COALESCE(av.value, pa.value_text, '')
            ORDER BY cnt DESC
            LIMIT 50
        """, (f["id"], cat["id"]))
        values = cur.fetchall()
        
        result.append({
            "attribute_id": f["id"],
            "attribute_name": f["name"],
            "attribute_slug": f["attr_slug"],
            "filter_type": f["filter_type"] or "multi-select",
            "position": f["position"],
            "values": [{"value": v["value"], "count": v["cnt"]} for v in values],
        })
    
    cur.connection.close()
    
    return {
        "category_id": cat["id"],
        "category_name": cat["name"],
        "category_slug": slug,
        "filters": result,
    }


@router.get("/products")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    brand: Optional[str] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    in_stock: Optional[bool] = None,
    sort: Optional[str] = None,
):
    """List products with filtering."""
    cur = get_cursor()
    
    conditions = ["p.is_active = true", "p.is_visible = true", "p.stock_status = 'in_stock'"]
    params = []
    
    if category:
        cur.execute("SELECT id FROM categories WHERE slug = %s", (category,))
        c = cur.fetchone()
        if c:
            # Include subcategories via closure
            conditions.append("""
                (pc.category_id IN (
                    SELECT descendant_id FROM category_closure WHERE ancestor_id = %s
                    UNION SELECT %s
                ))
            """)
            params.extend([c["id"], c["id"]])
        else:
            cur.connection.close()
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
    
    if brand:
        conditions.append("EXISTS (SELECT 1 FROM brands b WHERE lower(b.name) = lower(%s) AND b.id = p.brand_id)")
        params.append(brand)
    
    if price_min is not None:
        conditions.append("p.price >= %s")
        params.append(price_min)
    if price_max is not None:
        conditions.append("p.price <= %s")
        params.append(price_max)
    if in_stock:
        conditions.append("p.stock_status = 'in_stock'")
    
    order = "p.created_at DESC"
    if sort == "price_asc":
        order = "p.price ASC"
    elif sort == "price_desc":
        order = "p.price DESC"
    elif sort == "name":
        order = "p.name ASC"
    elif sort == "newest":
        order = "p.created_at DESC"
    
    # Default: prefer products with images first, then newest
    # This ensures homepage and first listing pages show products that have images
    if not sort:
        order = "(SELECT count(*) FROM product_images WHERE product_id = p.id AND is_suppressed = FALSE) DESC, p.created_at DESC"
    
    where = " AND ".join(conditions)
    offset = (page - 1) * page_size
    
    count_query = f"""
        SELECT count(DISTINCT p.id) FROM products p
        LEFT JOIN product_categories pc ON pc.product_id = p.id
        LEFT JOIN brands b ON b.id = p.brand_id
        WHERE {where}
    """
    cur.execute(count_query, params)
    total = cur.fetchone()["count"]
    
    query = f"""
        SELECT DISTINCT p.id, p.sku, p.name, p.slug, p.price, p.old_price,
               p.stock_status, p.stock_qty, p.created_at,
               (SELECT url FROM product_images WHERE product_id = p.id AND is_suppressed = FALSE ORDER BY sort_order, id LIMIT 1) as image,
               (SELECT c.name FROM product_categories pc2 JOIN categories c ON c.id = pc2.category_id WHERE pc2.product_id = p.id LIMIT 1) as category,
               COALESCE(b.name, '') as brand_name,
               (SELECT count(*) FROM product_images WHERE product_id = p.id AND is_suppressed = FALSE) as img_count
        FROM products p
        LEFT JOIN product_categories pc ON pc.product_id = p.id
        LEFT JOIN brands b ON b.id = p.brand_id
        WHERE {where}
        ORDER BY {order}
        LIMIT %s OFFSET %s
    """
    cur.execute(query, params + [page_size, offset])
    items = cur.fetchall()
    
    cur.connection.close()
    
    return {
        "items": [{
            "id": i["id"],
            "sku": i["sku"] or "",
            "name": i["name"] or "",
            "slug": i["slug"] or "",
            "price": i["price"] or 0,
            "old_price": i["old_price"],
            "stock_status": i["stock_status"] or "out_of_stock",
            "brand": i["brand_name"] or "",  
            "image": i["image"] or "",
            "category": i["category"] or "",
        } for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/products/{slug}")
async def get_product(slug: str):
    """Get product detail with attributes, images, breadcrumbs."""
    cur = get_cursor()
    cur.execute("""
        SELECT p.*, b.name as brand_name
        FROM products p
        LEFT JOIN brands b ON b.id = p.brand_id
        WHERE p.slug = %s
    """, (slug,))
    p = cur.fetchone()
    if not p:
        cur.connection.close()
        raise HTTPException(status_code=404, detail="Product not found")
    if not p["is_active"] or not p["is_visible"]:
        cur.connection.close()
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Attributes
    cur.execute("""
        SELECT a.id, a.name, av.value
        FROM product_attributes pa
        JOIN attributes a ON a.id = pa.attribute_id
        JOIN attribute_values av ON av.id = pa.attribute_value_id
        WHERE pa.product_id = %s
        ORDER BY a.name
    """, (p["id"],))
    attrs = cur.fetchall()
    
    # Images
    cur.execute("""
        SELECT id, url, sort_order, is_primary
        FROM product_images WHERE product_id = %s AND is_suppressed = FALSE
        ORDER BY sort_order
    """, (p["id"],))
    images = cur.fetchall()
    
    # Categories + breadcrumbs
    cur.execute("""
        SELECT c.id, c.name, c.slug
        FROM product_categories pc
        JOIN categories c ON c.id = pc.category_id
        WHERE pc.product_id = %s
    """, (p["id"],))
    categories = cur.fetchall()
    
    breadcrumbs = []
    if categories:
        c = categories[0]
        breadcrumbs.append({"id": c["id"], "name": c["name"], "slug": c["slug"]})
        pid = None
        cur.execute("SELECT parent_id FROM categories WHERE id = %s", (c["id"],))
        r = cur.fetchone()
        if r: pid = r["parent_id"]
        while pid:
            cur.execute("SELECT id, name, slug FROM categories WHERE id = %s", (pid,))
            parent = cur.fetchone()
            if parent:
                breadcrumbs.insert(0, {"id": parent["id"], "name": parent["name"], "slug": parent["slug"]})
                pid = parent["id"]
            else:
                break
    
    cur.connection.close()
    
    seo_title = p.get("seo_title") or f"{p['name']} — купити в Україні | Gadgeto" if p.get("name") else ""
    
    return {
        "id": p["id"],
        "sku": p["sku"] or "",
        "name": p["name"],
        "slug": p["slug"],
        "description": p.get("description") or "",
        "short_description": p.get("short_description") or "",
        "price": p["price"] or 0,
        "old_price": p.get("old_price"),
        "currency": "UAH",
        "stock_status": p.get("stock_status") or "out_of_stock",
        "stock_qty": p.get("stock_qty"),
        "brand": p.get("brand_name") or "",
        "category": breadcrumbs[-1]["name"] if breadcrumbs else "",
        "breadcrumbs": breadcrumbs,
        "images": [{"id": i["id"], "url": i["url"], "sort_order": i.get("sort_order", 0), "is_primary": i.get("is_primary", False)} for i in images],
        "attributes": [{"id": a["id"], "name": a["name"], "value": a["value"]} for a in attrs],
        "seo_title": seo_title,
        "seo_description": p.get("seo_description") or "",
    }


@router.get("/search")
async def search_products(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Search products by full-text search."""
    cur = get_cursor()
    offset = (page - 1) * page_size
    
    # Use full-text search
    cur.execute("""
        SELECT count(*) FROM products
        WHERE search_vector_tsv @@ plainto_tsquery('simple', %s)
          AND is_active = true AND is_visible = true AND stock_status = 'in_stock'
    """, (q,))
    total = cur.fetchone()["count"]
    
    if total == 0:
        # Fallback to trigram
        cur.execute("""
            SELECT count(*) FROM products
            WHERE lower(name) LIKE lower('%%' || %s || '%%')
              AND is_active = true AND is_visible = true AND stock_status = 'in_stock'
        """, (q,))
        total = cur.fetchone()["count"]
        
        cur.execute("""
            SELECT p.id, p.sku, p.name, p.slug, p.price, p.old_price, p.stock_status,
                   (SELECT url FROM product_images WHERE product_id = p.id ORDER BY sort_order, id LIMIT 1) as image
            FROM products p
            WHERE lower(p.name) LIKE lower('%%' || %s || '%%')
              AND p.is_active = true AND p.is_visible = true AND p.stock_status = 'in_stock'
            ORDER BY p.price ASC
            LIMIT %s OFFSET %s
        """, (q, page_size, offset))
    else:
        cur.execute("""
            SELECT p.id, p.sku, p.name, p.slug, p.price, p.old_price, p.stock_status,
                   ts_rank(p.search_vector_tsv, plainto_tsquery('simple', %s)) as rank,
                   (SELECT url FROM product_images WHERE product_id = p.id ORDER BY sort_order, id LIMIT 1) as image
            FROM products p
            WHERE p.search_vector_tsv @@ plainto_tsquery('simple', %s)
              AND p.is_active = true AND p.is_visible = true AND p.stock_status = 'in_stock'
            ORDER BY rank DESC
            LIMIT %s OFFSET %s
        """, (q, q, page_size, offset))
    
    items = cur.fetchall()
    cur.connection.close()
    
    return {
        "query": q,
        "items": [{
            "id": i["id"],
            "sku": i["sku"] or "",
            "name": i["name"] or "",
            "slug": i["slug"] or "",
            "price": i["price"] or 0,
            "old_price": i.get("old_price"),
            "stock_status": i.get("stock_status") or "out_of_stock",
            "image": i.get("image") or "",
        } for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }
