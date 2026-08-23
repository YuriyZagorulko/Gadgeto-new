"""WooCommerce-style product editor API.

All routes are nested under /products/{product_id}/... so they never clash
with the flat CRUD routes in products.py.
"""
import json
import os
import hashlib
import uuid
import re
from itertools import product as cartesian
from typing import Optional, List

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body as FBody
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


def _get_or_404(cur, pid: int):
    cur.execute("SELECT id FROM products WHERE id=%s", (pid,))
    if not cur.fetchone():
        raise HTTPException(404, "Товар не знайдено")


def _clean(val):
    """Empty string -> NULL (for optional text/date inputs)."""
    return None if val == "" else val


PRODUCT_COLS = """id, legacy_id, supplier_id, supplier_sku, sku, name, slug, description,
    short_description, brand_id, price, old_price, currency, stock_status, stock_qty,
    is_active, is_visible, status, meta_json, seo_title, seo_description, focus_keyphrase,
    sale_start_at, sale_end_at, barcode, low_stock_threshold, manage_stock,
    allow_backorders, purchase_cost, warehouse, created_at, updated_at"""


@router.get("/products/{product_id}/editor")
def get_editor(product_id: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        _get_or_404(cur, product_id)
        cur.execute(
            f"SELECT {PRODUCT_COLS} FROM products WHERE id=%s", (product_id,))
        product = cur.fetchone()
        meta = product.pop("meta_json", None) or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        cur.execute(
            """SELECT id, url, alt, sort_order, is_primary FROM product_images
               WHERE product_id=%s ORDER BY sort_order, id""", (product_id,))
        images = cur.fetchall()

        cur.execute(
            "SELECT category_id FROM product_categories WHERE product_id=%s",
            (product_id,))
        category_ids = [r["category_id"] for r in cur.fetchall()]

        cur.execute(
            """SELECT pa.id, pa.attribute_id, a.name AS attribute_name,
                      pa.attribute_value_id, av.value AS attribute_value,
                      pa.value_text
               FROM product_attributes pa
               LEFT JOIN attributes a ON a.id = pa.attribute_id
               LEFT JOIN attribute_values av ON av.id = pa.attribute_value_id
               WHERE pa.product_id=%s ORDER BY pa.id""", (product_id,))
        attributes = cur.fetchall()

        cur.execute(
            """SELECT * FROM product_reviews WHERE product_id=%s
               ORDER BY created_at DESC LIMIT 200""", (product_id,))
        reviews = cur.fetchall()

        cur.execute(
            "SELECT * FROM product_variations WHERE product_id=%s ORDER BY id",
            (product_id,))
        variations = cur.fetchall()

        return {
            "product": product,
            "images": images,
            "category_ids": category_ids,
            "attributes": attributes,
            "reviews": reviews,
            "variations": variations,
            "custom_fields": meta.get("custom_fields", []),
        }
    finally:
        conn.close()


# ======== Editor mutation endpoints (self-contained, introspection-based) ========
import os as _os
import json as _json
import psycopg2 as _pg
from fastapi import Body as _Body
from app.api.admin.deps import require_admin


def _ed_conn():
    url = _os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")
    c = _pg.connect(url)
    c.autocommit = True
    return c


def _tcols(cur, table):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
    return {r[0] for r in cur.fetchall()}


def _pick(cands, cols):
    for c in cands:
        if c in cols:
            return c
    return None


def _rows_dict(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _apply_update(product_id: int, mapping: dict, payload: dict):
    con = _ed_conn()
    cur = con.cursor()
    cols = _tcols(cur, "products")
    sets, args = [], []
    for key, col in mapping.items():
        if col in cols and key in payload and payload[key] is not None:
            sets.append(f"{col} = %s")
            args.append(payload[key])
    if sets:
        args.append(product_id)
        cur.execute(f"UPDATE products SET {', '.join(sets)} WHERE id = %s", args)
    cur.close()
    con.close()


@router.put("/products/{product_id}/pricing")
async def ed_pricing(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    _apply_update(product_id, {
        "price": "price", "regularPrice": "price",
        "old_price": "old_price", "oldPrice": "old_price",
        "sale_price": "sale_price", "salePrice": "sale_price",
        "sale_starts_at": "sale_starts_at", "saleStartsAt": "sale_starts_at",
        "sale_ends_at": "sale_ends_at", "saleEndsAt": "sale_ends_at",
    }, payload)
    return {"ok": True}


@router.put("/products/{product_id}/inventory")
async def ed_inventory(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    _apply_update(product_id, {
        "stock": "stock", "quantity": "stock",
        "stock_status": "stock_status", "stockStatus": "stock_status",
        "manage_stock": "manage_stock", "manageStock": "manage_stock",
        "allow_backorders": "allow_backorders", "allowBackorders": "allow_backorders",
        "low_stock_threshold": "low_stock_threshold", "lowStockThreshold": "low_stock_threshold",
        "barcode": "barcode", "warehouse_location": "warehouse_location", "warehouseLocation": "warehouse_location",
        "purchase_cost": "purchase_cost", "purchaseCost": "purchase_cost",
        "supplier_id": "supplier_id", "supplierId": "supplier_id",
        "supplier_sku": "supplier_sku", "supplierSku": "supplier_sku",
    }, payload)
    return {"ok": True}


@router.put("/products/{product_id}/seo")
async def ed_seo(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    _apply_update(product_id, {
        "seo_title": "seo_title", "seoTitle": "seo_title",
        "seo_description": "seo_description", "seoDescription": "seo_description",
        "focus_keyphrase": "focus_keyphrase", "focusKeyphrase": "focus_keyphrase",
        "canonical_url": "canonical_url", "canonicalUrl": "canonical_url",
        "og_title": "og_title", "ogTitle": "og_title",
        "og_description": "og_description", "ogDescription": "og_description",
        "og_image": "og_image", "ogImage": "og_image",
    }, payload)
    return {"ok": True}


@router.put("/products/{product_id}/general")
async def ed_general(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    _apply_update(product_id, {
        "name": "name", "slug": "slug", "sku": "sku",
        "brand_id": "brand_id", "brandId": "brand_id",
        "status": "status", "product_type": "product_type", "productType": "product_type",
        "catalog_visibility": "catalog_visibility", "catalogVisibility": "catalog_visibility",
        "short_description": "short_description", "shortDescription": "short_description",
        "description": "description",
    }, payload)
    return {"ok": True}


@router.put("/products/{product_id}/categories")
async def ed_categories(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    ids = payload.get("category_ids") or payload.get("ids") or []
    con = _ed_conn()
    cur = con.cursor()
    cur.execute("SELECT to_regclass('public.product_categories'), to_regclass('public.category_products')")
    a, b = cur.fetchone()
    tbl = "product_categories" if a else ("category_products" if b else None)
    if tbl:
        cur.execute(f"DELETE FROM {tbl} WHERE product_id=%s", (product_id,))
        for cid in ids:
            cur.execute(
                f"INSERT INTO {tbl} (product_id, category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                (product_id, int(cid)),
            )
    cur.close()
    con.close()
    return {"ok": True, "count": len(ids)}


@router.put("/products/{product_id}/attributes")
async def ed_attributes(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    rows = payload.get("rows") or []
    con = _ed_conn()
    cur = con.cursor()
    cols = _tcols(cur, "product_attributes")
    fk = _pick(["attribute_value_id", "value_id"], cols)
    txt = _pick(["value", "value_text", "value_custom", "raw_value"], cols)
    cur.execute("DELETE FROM product_attributes WHERE product_id=%s", (product_id,))
    n = 0
    for r in rows:
        aid = r.get("attribute_id") or r.get("attributeId")
        if not aid:
            continue
        collist = ["product_id", "attribute_id"]
        vals = [product_id, int(aid)]
        if fk and r.get("value_id"):
            collist.append(fk)
            vals.append(int(r["value_id"]))
        if txt and (r.get("value") or r.get("valueText")):
            collist.append(txt)
            vals.append(str(r.get("value") or r.get("valueText")))
        ph = ",".join(["%s"] * len(collist))
        cur.execute(f"INSERT INTO product_attributes ({','.join(collist)}) VALUES ({ph})", vals)
        n += 1
    cur.close()
    con.close()
    return {"ok": True, "count": n}


@router.put("/products/{product_id}/images")
async def ed_images(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    rows = payload.get("images") or []
    con = _ed_conn()
    cur = con.cursor()
    cur.execute("SELECT id, url FROM product_images WHERE product_id=%s", (product_id,))
    existing = {u: i for i, u in cur.fetchall()}
    keep_urls = []
    order = 0
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        keep_urls.append(url)
        eid = existing.get(url)
        if eid:
            cur.execute("UPDATE product_images SET sort_order=%s WHERE id=%s", (order, eid))
        else:
            cur.execute(
                "INSERT INTO product_images (product_id, url, sort_order, is_primary) VALUES (%s,%s,%s,FALSE)",
                (product_id, url, order),
            )
        order += 1
    cur.execute("UPDATE product_images SET is_primary=FALSE WHERE product_id=%s", (product_id,))
    prim = next((r.get("url").strip() for r in rows if r.get("is_primary") and r.get("url")), None)
    if prim:
        cur.execute("UPDATE product_images SET is_primary=TRUE WHERE product_id=%s AND url=%s", (product_id, prim))
    elif order:
        cur.execute("SELECT id FROM product_images WHERE product_id=%s ORDER BY sort_order, id LIMIT 1", (product_id,))
        first = cur.fetchone()
        if first:
            cur.execute("UPDATE product_images SET is_primary=TRUE WHERE id=%s", (first[0],))
    if keep_urls:
        cur.execute("DELETE FROM product_images WHERE product_id=%s AND NOT (url = ANY(%s))", (product_id, keep_urls))
    cur.close()
    con.close()
    return {"ok": True}


@router.get("/products/{product_id}/custom-fields")
async def cf_get(product_id: int, _u=Depends(require_admin)):
    con = _ed_conn()
    cur = con.cursor()
    cols = _tcols(cur, "products")
    out = []
    if "meta_json" in cols:
        cur.execute("SELECT meta_json FROM products WHERE id=%s", (product_id,))
        row = cur.fetchone()
        if row and row[0]:
            try:
                out = (_json.loads(row[0]) or {}).get("custom_fields", [])
            except Exception:
                out = []
    cur.close()
    con.close()
    return {"items": out}


@router.put("/products/{product_id}/custom-fields")
async def cf_put(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    fields = payload.get("fields") or []
    clean = [{"name": str(f.get("name", "")).strip(), "value": str(f.get("value", ""))} for f in fields if str(f.get("name", "")).strip()]
    con = _ed_conn()
    cur = con.cursor()
    cur.execute("SELECT meta_json FROM products WHERE id=%s", (product_id,))
    row = cur.fetchone()
    try:
        meta = (_json.loads(row[0]) if row and row[0] else {}) or {}
    except Exception:
        meta = {}
    meta["custom_fields"] = clean
    cur.execute("UPDATE products SET meta_json=%s WHERE id=%s", (_json.dumps(meta, ensure_ascii=False), product_id))
    cur.close()
    con.close()
    return {"ok": True, "count": len(clean)}


_RV_NAME = ["author_name", "reviewer_name", "name"]
_RV_EMAIL = ["author_email", "email"]
_RV_TEXT = ["content", "body", "review_text", "text"]
_VR_SKU = ["sku"]
_VR_PRICE = ["price"]
_VR_SALE = ["sale_price"]
_VR_STOCK = ["stock", "qty", "stock_quantity"]
_VR_IMG = ["image_url", "image", "img"]
_VR_ATTRS = ["attributes_json", "attrs_json", "attributes"]


def _rv_norm(cols, r):
    nc = _pick(_RV_NAME, cols)
    ec = _pick(_RV_EMAIL, cols)
    tc = _pick(_RV_TEXT, cols)
    return {
        "id": r["id"],
        "author": r.get(nc) if nc else None,
        "email": r.get(ec) if ec else None,
        "rating": r.get("rating"),
        "text": r.get(tc) if tc else None,
        "status": r.get("status"),
        "createdAt": str(r.get("created_at")) if r.get("created_at") else None,
    }


# ---- Review CRUD (see below for moderation endpoints) ----


def _vr_norm(cols, r):
    sc = _pick(_VR_STOCK, cols)
    ic = _pick(_VR_IMG, cols)
    ac = _pick(_VR_ATTRS, cols)
    attrs = {}
    if ac and r.get(ac):
        try:
            attrs = _json.loads(r[ac]) if isinstance(r[ac], str) else r[ac]
        except Exception:
            attrs = {}
    return {
        "id": r["id"],
        "sku": r.get(_pick(_VR_SKU, cols)) if _pick(_VR_SKU, cols) else None,
        "price": r.get(_pick(_VR_PRICE, cols)) if _pick(_VR_PRICE, cols) else None,
        "salePrice": r.get(_pick(_VR_SALE, cols)) if _pick(_VR_SALE, cols) else None,
        "stock": r.get(sc) if sc else None,
        "imageUrl": r.get(ic) if ic else None,
        "attributes": attrs,
    }


@router.get("/products/{product_id}/variations")
async def vr_list(product_id: int, _u=Depends(require_admin)):
    con = _ed_conn()
    cur = con.cursor()
    cols = _tcols(cur, "product_variations")
    cur.execute("SELECT * FROM product_variations WHERE product_id=%s ORDER BY id", (product_id,))
    items = [_vr_norm(cols, r) for r in _rows_dict(cur)]
    cur.close()
    con.close()
    return {"items": items}


@router.put("/products/{product_id}/variations")
async def vr_put(product_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    rows = payload.get("rows") or []
    con = _ed_conn()
    cur = con.cursor()
    cols = _tcols(cur, "product_variations")
    sc = _pick(_VR_STOCK, cols)
    ic = _pick(_VR_IMG, cols)
    ac = _pick(_VR_ATTRS, cols)
    spc = _pick(_VR_SALE, cols)
    cur.execute("DELETE FROM product_variations WHERE product_id=%s", (product_id,))
    for r in rows:
        collist, vals = ["product_id"], [product_id]
        skuc = _pick(_VR_SKU, cols)
        pc = _pick(_VR_PRICE, cols)
        if skuc and r.get("sku"):
            collist.append(skuc)
            vals.append(r["sku"])
        if pc and r.get("price") is not None:
            collist.append(pc)
            vals.append(int(r["price"]))
        if spc and r.get("salePrice") is not None:
            collist.append(spc)
            vals.append(int(r["salePrice"]))
        if sc and r.get("stock") is not None:
            collist.append(sc)
            vals.append(int(r["stock"]))
        if ic and r.get("imageUrl"):
            collist.append(ic)
            vals.append(r["imageUrl"])
        if ac:
            collist.append(ac)
            vals.append(_json.dumps(r.get("attributes") or {}, ensure_ascii=False))
        ph = ",".join(["%s"] * len(collist))
        cur.execute(f"INSERT INTO product_variations ({','.join(collist)}) VALUES ({ph})", vals)
# ---- Image upload ----

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/products/{product_id}/images/upload")
async def upload_image(
    product_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(400, "Дозволено лише JPG, PNG, WEBP")
    body = await file.read()
    if len(body) > MAX_SIZE:
        raise HTTPException(400, "Файл завеликий (макс. 10 MB)")

    from app.core.config import settings
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = f"products/{filename}"
    abs_path = os.path.join(settings.MEDIA_DIR, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(body)

    base_url = (settings.MEDIA_BASE_URL or "/media").rstrip("/")
    url = f"{base_url}/{rel_path}"

    conn, cur = db()
    try:
        _get_or_404(cur, product_id)
        cur.execute("SELECT MAX(sort_order) FROM product_images WHERE product_id=%s", (product_id,))
        max_order = (cur.fetchone()["max"] or 0)
        cur.execute("SELECT COUNT(*) AS cnt FROM product_images WHERE product_id=%s AND is_primary=true", (product_id,))
        has_primary = cur.fetchone()["cnt"] > 0
        cur.execute(
            "INSERT INTO product_images (product_id, url, sort_order, is_primary) VALUES (%s,%s,%s,%s) RETURNING id",
            (product_id, url, max_order + 1, not has_primary),
        )
        img_id = cur.fetchone()["id"]
        return {"ok": True, "id": img_id, "url": url}
    finally:
        conn.close()


# ---- Review moderation ----


@router.get("/products/{product_id}/reviews")
async def rv_list(product_id: int, _u=Depends(require_admin)):
    con = _ed_conn(); cur = con.cursor()
    cur.execute(
        "SELECT id, product_id, user_id, author_name, author_email, rating, content, status, created_at, updated_at "
        "FROM product_reviews WHERE product_id=%s ORDER BY created_at DESC LIMIT 500", (product_id,))
    items = _rows_dict(cur); cur.close(); con.close()
    return {"items": items}


@router.put("/products/{product_id}/reviews/{review_id}/moderate")
async def rv_moderate(product_id: int, review_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    status = payload.get("status", "").strip()
    if status not in ("published", "pending", "hidden"):
        raise HTTPException(400, "Невірний статус")
    con = _ed_conn(); cur = con.cursor()
    cur.execute("UPDATE product_reviews SET status=%s, updated_at=NOW() WHERE id=%s AND product_id=%s", (status, review_id, product_id))
    cur.close(); con.close()
    return {"ok": True}


@router.put("/products/{product_id}/reviews/{review_id}")
async def rv_update(product_id: int, review_id: int, payload: dict = _Body(...), _u=Depends(require_admin)):
    allowed = {"author_name", "author_email", "rating", "content", "status"}
    sets, params = [], []
    for key in allowed:
        val = payload.get(key)
        if val is not None:
            sets.append(f"{key}=%s"); params.append(val)
    if not sets:
        return {"ok": True}
    params.extend([review_id, product_id])
    con = _ed_conn(); cur = con.cursor()
    cur.execute(f"UPDATE product_reviews SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s AND product_id=%s", params)
    cur.close(); con.close()
    return {"ok": True}


# ---- Storefront reviews API (no auth required) ----


@router.post("/products/{product_id}/storefront-reviews")
async def storefront_create_review(product_id: int, payload: dict = FBody(...)):
    rating = payload.get("rating")
    text = (payload.get("content") or payload.get("text") or "").strip()
    user_id = payload.get("user_id")
    if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
        raise HTTPException(400, "Оцінка має бути від 1 до 5")
    if not text:
        raise HTTPException(400, "Текст відгуку обов'язковий")
    if not user_id:
        raise HTTPException(400, "Необхідна автентифікація")
    con = _ed_conn(); cur = con.cursor()
    _get_or_404(cur, product_id)
    cur.execute("SELECT full_name, email FROM users WHERE id=%s", (user_id,))
    u = cur.fetchone()
    if not u:
        raise HTTPException(400, "Користувача не знайдено")
    cur.execute(
        "INSERT INTO product_reviews (product_id, user_id, author_name, author_email, rating, content, status, created_at, updated_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,'pending',NOW(),NOW()) RETURNING id",
        (product_id, user_id, u["full_name"], u["email"] or "", rating, text))
    rid = cur.fetchone()[0]
    cur.close(); con.close()
    return {"ok": True, "id": rid, "status": "pending"}


@router.get("/products/{product_id}/storefront-reviews")
async def storefront_list_reviews(product_id: int):
    con = _ed_conn(); cur = con.cursor()
    cur.execute(
        "SELECT id, author_name, rating, content, created_at FROM product_reviews "
        "WHERE product_id=%s AND status='published' ORDER BY created_at DESC LIMIT 200", (product_id,))
    items = _rows_dict(cur); cur.close(); con.close()
    return {"items": items, "count": len(items)}
    cur.close()
    con.close()
    return {"ok": True, "count": len(rows)}
