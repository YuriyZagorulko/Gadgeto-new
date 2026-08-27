# Admin attributes API
import re
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class AttributeIn(BaseModel):
    name: str
    type: str = "select"
    is_filterable: bool = True


class AttributeValueIn(BaseModel):
    value: str
    is_active: bool = True


@router.get("/attributes")
async def list_attributes(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
                          search: Optional[str] = None,
                          user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        conds, params = ["1=1"], []
        if search:
            conds.append("a.name ILIKE %s"); params.append(f"%{search}%")
        where = " AND ".join(conds)
        cur.execute(f"SELECT count(*) AS c FROM attributes a WHERE {where}", params)
        total = cur.fetchone()["c"]
        offset = (page - 1) * per_page
        cur.execute(f"""
            SELECT a.id, a.name, a.slug, a.type, a.is_filterable, a.sort_order,
                   (SELECT count(*) FROM attribute_values av WHERE av.attribute_id=a.id) AS values_count,
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_id=a.id) AS products_count,
                   (SELECT count(*) FROM category_attributes ca WHERE ca.attribute_id=a.id) AS categories_count
            FROM attributes a WHERE {where}
            ORDER BY a.sort_order, a.name LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page,
                "total_pages": max(1, (total + per_page - 1) // per_page)}
    finally:
        conn.close()


@router.post("/attributes")
async def create_attribute(data: AttributeIn, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        slug = re.sub(r"[^a-z0-9]+", "-", data.name.lower()).strip("-") or "attr"
        cur.execute("""INSERT INTO attributes (name, slug, type, is_filterable)
                       VALUES (%s,%s,%s,%s) RETURNING id""",
                    (data.name.strip(), slug, data.type, data.is_filterable))
        return {"ok": True, "id": cur.fetchone()["id"]}
    finally:
        conn.close()


@router.put("/attributes/{aid}")
async def update_attribute(aid: int, data: AttributeIn, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("UPDATE attributes SET name=%s, type=%s, is_filterable=%s, updated_at=NOW() WHERE id=%s",
                    (data.name.strip(), data.type, data.is_filterable, aid))
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/attributes/{aid}")
async def delete_attribute(aid: int, user: dict = Depends(require_admin)):
    """Delete an attribute. Blocked when products reference it — deactivate instead."""
    conn, cur = db()
    try:
        cur.execute("SELECT count(*) AS c FROM product_attributes WHERE attribute_id=%s", (aid,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409,
                                detail="Атрибут використовується товарами. Зніміть прапорець «Фільтр» замість видалення.")
        cur.execute("DELETE FROM category_filters WHERE attribute_id=%s", (aid,))
        cur.execute("DELETE FROM attribute_values WHERE attribute_id=%s", (aid,))
        cur.execute("DELETE FROM attributes WHERE id=%s", (aid,))
        return {"ok": True}
    finally:
        conn.close()


@router.get("/attributes/{aid}/values")
async def list_values(aid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("""
            SELECT av.id, av.value, av.slug, av.is_active, av.sort,
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_value_id=av.id) AS products_count
            FROM attribute_values av WHERE av.attribute_id=%s ORDER BY av.sort, av.value
        """, (aid,))
        return {"items": cur.fetchall()}
    finally:
        conn.close()


@router.post("/attributes/{aid}/values")
async def create_value(aid: int, data: AttributeValueIn, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        slug = re.sub(r"[^a-z0-9]+", "-", data.value.lower()).strip("-") or "value"
        cur.execute("""INSERT INTO attribute_values (attribute_id, value, slug, is_active)
                       VALUES (%s,%s,%s,%s) RETURNING id""", (aid, data.value.strip(), slug, data.is_active))
        return {"ok": True, "id": cur.fetchone()["id"]}
    finally:
        conn.close()


@router.put("/attributes/{aid}/values/{vid}")
async def update_value(aid: int, vid: int, data: AttributeValueIn, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("UPDATE attribute_values SET value=%s, is_active=%s, updated_at=NOW() WHERE id=%s AND attribute_id=%s",
                    (data.value.strip(), data.is_active, vid, aid))
        return {"ok": True}
    finally:
        conn.close()


@router.get("/attributes/{aid}/values/{vid}/usage")
async def check_value_usage(aid: int, vid: int, user: dict = Depends(require_admin)):
    """Check where an AttributeValue is referenced."""
    conn, cur = db()
    try:
        cur.execute("SELECT count(*) AS c FROM product_attributes WHERE attribute_value_id=%s", (vid,))
        products = cur.fetchone()["c"]
        cur.execute("SELECT count(*) AS c FROM category_attribute_values WHERE attribute_value_id=%s", (vid,))
        categories = cur.fetchone()["c"]
        cur.execute("SELECT count(*) AS c FROM attribute_value_mappings WHERE attribute_value_id=%s", (vid,))
        mappings = cur.fetchone()["c"]
        return {
            "product_count": products,
            "category_count": categories,
            "mapping_count": mappings,
            "can_delete": products == 0 and mappings == 0,
        }
    finally:
        conn.close()


@router.delete("/attributes/{aid}/values/{vid}")
async def delete_value(aid: int, vid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT count(*) AS c FROM product_attributes WHERE attribute_value_id=%s", (vid,))
        prod_usage = cur.fetchone()["c"]
        cur.execute("SELECT count(*) AS c FROM attribute_value_mappings WHERE attribute_value_id=%s", (vid,))
        map_usage = cur.fetchone()["c"]

        if prod_usage > 0 or map_usage > 0:
            parts = []
            if prod_usage > 0:
                parts.append(f"{prod_usage} товарами")
            if map_usage > 0:
                parts.append(f"{map_usage} маппінгами")
            raise HTTPException(
                status_code=409,
                detail=("Значення використовується "
                        f"{' і '.join(parts)} — деактивуйте замість видалення."),
            )
        # Clean up category_attribute_values for this value
        cur.execute("DELETE FROM category_attribute_values WHERE attribute_value_id=%s", (vid,))
        cur.execute("DELETE FROM attribute_values WHERE id=%s AND attribute_id=%s", (vid, aid))
        return {"ok": True}
    finally:
        conn.close()



@router.get("/attributes/{aid}/categories")
async def attribute_categories(aid: int, user: dict = Depends(require_admin)):
    """Get all categories that use this attribute."""
    conn, cur = db()
    try:
        cur.execute("""
            SELECT c.id, c.name, c.slug, ca.filterable, ca.required,
                   ca.multiple, ca.sort_order
            FROM category_attributes ca
            JOIN categories c ON c.id = ca.category_id
            WHERE ca.attribute_id = %s
            ORDER BY c.name
        """, (aid,))
        return {"items": cur.fetchall()}
    finally:
        conn.close()


@router.post("/attributes/{aid}/categories")
async def assign_attribute_categories(aid: int, category_ids: list[int],
                                       filterable: bool = True,
                                       user: dict = Depends(require_admin)):
    """Assign this attribute to multiple categories."""
    conn, cur = db()
    try:
        cur.execute("SELECT id FROM attributes WHERE id=%s", (aid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="\u0410\u0442\u0440\u0438\u0431\u0443\u0442 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")
        created = 0
        for cid in category_ids:
            cur.execute(
                """INSERT INTO category_attributes
                    (category_id, attribute_id, filterable, required, multiple,
                     searchable, sort_order, filter_type, created_at, updated_at)
                VALUES (%s,%s,%s,false,false,false,0,NULL,NOW(),NOW())
                ON CONFLICT (category_id, attribute_id) DO NOTHING""",
                (cid, aid, filterable),
            )
            if cur.rowcount > 0:
                created += 1
        return {"ok": True, "created": created, "skipped": len(category_ids) - created}
    finally:
        conn.close()


@router.delete("/attributes/{aid}/categories/{cid}")
async def remove_attribute_from_category(aid: int, cid: int, user: dict = Depends(require_admin)):
    """Remove an attribute from a specific category."""
    conn, cur = db()
    try:
        cur.execute(
            "DELETE FROM category_attributes WHERE attribute_id=%s AND category_id=%s",
            (aid, cid),
        )
        return {"ok": True, "deleted": cur.rowcount > 0}
    finally:
        conn.close()
