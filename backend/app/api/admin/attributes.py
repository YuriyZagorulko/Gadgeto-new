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
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_id=a.id) AS products_count
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


@router.delete("/attributes/{aid}/values/{vid}")
async def delete_value(aid: int, vid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT count(*) AS c FROM product_attributes WHERE attribute_value_id=%s", (vid,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409, detail="Значення використовується товарами — деактивуйте його замість видалення.")
        cur.execute("DELETE FROM attribute_values WHERE id=%s AND attribute_id=%s", (vid, aid))
        return {"ok": True}
    finally:
        conn.close()

