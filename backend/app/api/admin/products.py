"""Admin products API."""
import json, re
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List

from app.api.admin.deps import require_admin
from app.core.db_connect import DB


router = APIRouter()

def db():
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[int] = None
    old_price: Optional[int] = None
    stock_qty: Optional[int] = None
    stock_status: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    brand_id: Optional[int] = None
    category_ids: Optional[List[int]] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    focus_keyphrase: Optional[str] = None


class ProductCreate(ProductUpdate):
    name: str
    sku: Optional[str] = None


# Must match the DB enum productstatus: {DRAFT, PUBLISHED, HIDDEN, ARCHIVED}
PRODUCT_STATUSES = ("DRAFT", "PUBLISHED", "HIDDEN", "ARCHIVED")
STOCK_STATUSES = ("in_stock", "out_of_stock", "pre_order")

# Whitelisted sort keys -> SQL expressions (identifiers only, never user input).
# Used by the admin products table for server-side sorting.
SORT_COLUMNS = {
    "name": "p.name",
    "sku": "NULLIF(p.sku, '')",
    "category": "(SELECT MIN(c.name) FROM product_categories pc JOIN categories c ON c.id = pc.category_id WHERE pc.product_id = p.id)",
    "brand": "b.name",
    "price": "p.price",
    "stock": "p.stock_qty",
    "status": "p.status",
    "updated": "p.updated_at",
}

@router.get("/products")
async def list_products(page: int = Query(1,ge=1), per_page: int = Query(20,ge=1,le=100),
    search: Optional[str] = None, category_id: Optional[int] = None,
    brand_id: Optional[int] = None, status: Optional[str] = None,
    stock: Optional[str] = None,
    no_image: bool = False, no_price: bool = False,
    sort: Optional[str] = Query(None, pattern="^(" + "|".join(SORT_COLUMNS) + ")$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_admin)):
    conn, cur = db()
    conds, params = ["1=1"], []
    if search:
        conds.append("(p.name ILIKE %s OR p.sku ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category_id:
        conds.append("EXISTS (SELECT 1 FROM product_categories pc WHERE pc.product_id=p.id AND pc.category_id=%s)")
        params.append(category_id)
    if brand_id:
        conds.append("p.brand_id=%s"); params.append(brand_id)
    if status:
        conds.append("p.status=%s"); params.append(status)
    if stock == "in_stock": conds.append("p.stock_status='in_stock'")
    elif stock == "out_of_stock": conds.append("p.stock_status='out_of_stock'")
    if no_image:
        conds.append("NOT EXISTS (SELECT 1 FROM product_images pi WHERE pi.product_id=p.id)")
    if no_price:
        conds.append("(p.price IS NULL OR p.price = 0)")
    where = " AND ".join(conds)
    offset = (page - 1) * per_page
    # Server-side sorting on the full dataset (DB-level ORDER BY + LIMIT/OFFSET).
    # p.id is always appended as a stable tiebreaker so OFFSET pagination
    # never skips or repeats rows with equal sort values.
    if sort:
        direction = "ASC" if order == "asc" else "DESC"
        order_by = f"{SORT_COLUMNS[sort]} {direction} NULLS LAST, p.id {direction}"
    else:
        order_by = "p.updated_at DESC, p.id DESC"
    cur.execute(f"SELECT count(*) FROM products p WHERE {where}", params)
    total = cur.fetchone()["count"]
    cur.execute(f"""
        SELECT p.id, p.sku, p.name, p.slug, p.price, p.old_price, p.stock_status,
               p.stock_qty, p.status, p.is_active, p.updated_at,
               b.name as brand_name,
               (SELECT url FROM product_images WHERE product_id=p.id AND is_primary=true LIMIT 1) as image,
               (SELECT string_agg(c.name, ', ') FROM product_categories pc JOIN categories c ON c.id=pc.category_id WHERE pc.product_id=p.id) as categories
        FROM products p LEFT JOIN brands b ON b.id=p.brand_id
        WHERE {where} ORDER BY {order_by} LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    items = cur.fetchall(); conn.close()
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)}

@router.get("/products/{pid}")
async def get_product(pid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    cur.execute("SELECT p.*, b.name as brand_name FROM products p LEFT JOIN brands b ON b.id=p.brand_id WHERE p.id=%s", (pid,))
    p = cur.fetchone()
    if not p: conn.close(); raise HTTPException(status_code=404)
    cur.execute("SELECT c.id, c.name, c.slug FROM product_categories pc JOIN categories c ON c.id=pc.category_id WHERE pc.product_id=%s", (pid,))
    cats = cur.fetchall()
    cur.execute("""
        SELECT a.id, a.name, a.slug, av.value as attr_val, av.id as val_id
        FROM product_attributes pa JOIN attributes a ON a.id=pa.attribute_id
        LEFT JOIN attribute_values av ON av.id=pa.attribute_value_id
        WHERE pa.product_id=%s ORDER BY a.name
    """, (pid,))
    attrs = cur.fetchall()
    cur.execute("SELECT id, url, sort_order, is_primary FROM product_images WHERE product_id=%s ORDER BY sort_order", (pid,))
    imgs = cur.fetchall()
    conn.close()
    return {"product": p, "categories": cats, "attributes": attrs, "images": imgs}

@router.put("/products/{pid}")
async def update_product(pid: int, data: ProductUpdate, user: dict = Depends(require_admin)):
    if data.status is not None and data.status not in PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail="Невірний статус товару")
    if data.stock_status is not None and data.stock_status not in STOCK_STATUSES:
        raise HTTPException(status_code=400, detail="Невірний статус залишку")
    conn, cur = db()
    sets, params = [], []
    for f in ["name","slug","sku","price","old_price","stock_qty","stock_status",
              "status","description","short_description","brand_id",
              "seo_title","seo_description","focus_keyphrase"]:
        v = getattr(data, f, None)
        if v is not None: sets.append(f"{f}=%s"); params.append(v)
    if sets:
        params.append(pid)
        cur.execute(f"UPDATE products SET {','.join(sets)}, updated_at=NOW() WHERE id=%s", params)
    if data.category_ids is not None:
        cur.execute("DELETE FROM product_categories WHERE product_id=%s", (pid,))
        for cid in data.category_ids:
            cur.execute("INSERT INTO product_categories (product_id,category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (pid, cid))
    conn.close()
    return {"ok": True, "id": pid}

@router.delete("/products/{pid}")
async def delete_product(pid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    cur.execute("UPDATE products SET status='ARCHIVED', is_active=false, updated_at=NOW() WHERE id=%s", (pid,))
    conn.close()
    return {"ok": True}


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9а-яіїєґё\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s or "product"


@router.post("/products")
async def create_product(data: ProductCreate, user: dict = Depends(require_admin)):
    """Create a new product (draft by default)."""
    if data.status is not None and data.status not in PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail="Невірний статус товару")
    conn, cur = db()
    try:
        slug = data.slug or _slugify(data.name)
        base, i = slug, 2
        while True:
            cur.execute("SELECT 1 FROM products WHERE slug=%s", (slug,))
            if not cur.fetchone():
                break
            slug = f"{base}-{i}"; i += 1
        cur.execute(
            """INSERT INTO products (name, slug, sku, price, old_price, stock_qty,
               stock_status, status, description, short_description, brand_id,
               seo_title, seo_description, focus_keyphrase)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (data.name.strip(), slug, data.sku, data.price, data.old_price,
             data.stock_qty or 0, data.stock_status or "in_stock",
             data.status or "DRAFT", data.description, data.short_description,
             data.brand_id, data.seo_title, data.seo_description, data.focus_keyphrase),
        )
        pid = cur.fetchone()["id"]
        for cid in (data.category_ids or []):
            cur.execute("INSERT INTO product_categories (product_id,category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (pid, cid))
        return {"ok": True, "id": pid, "slug": slug}
    finally:
        conn.close()


class BulkAction(BaseModel):
    ids: List[int]
    action: str  # publish | hide | archive | activate | deactivate


@router.post("/products/bulk")
async def bulk_action(data: BulkAction, user: dict = Depends(require_admin)):
    """Bulk status change for products."""
    actions = {
        "publish": ("status='PUBLISHED', is_active=true",),
        "hide": ("status='HIDDEN'",),
        "archive": ("status='ARCHIVED', is_active=false",),
        "activate": ("is_active=true",),
        "deactivate": ("is_active=false",),
    }
    if data.action not in actions or not data.ids:
        raise HTTPException(status_code=400, detail="Невірна дія")
    conn, cur = db()
    try:
        cur.execute(
            f"UPDATE products SET {actions[data.action][0]}, updated_at=NOW() WHERE id = ANY(%s)",
            (data.ids,),
        )
        return {"ok": True, "updated": cur.rowcount}
    finally:
        conn.close()

