"""Admin category-filters API (manages the EXISTING category_filters system)."""
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class FilterIn(BaseModel):
    category_id: Optional[int] = None
    attribute_id: int
    position: int = 0


class FilterUpdate(BaseModel):
    category_id: Optional[int] = None
    position: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/filters")
async def list_filters(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    category_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    q: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    conn, cur = db()
    try:
        conds, params = ["1=1"], []
        if category_id is not None:
            conds.append("cf.category_id = %s")
            params.append(category_id)
        if enabled is not None:
            conds.append("cf.enabled = %s")
            params.append(enabled)
        if q:
            conds.append("a.name ILIKE %s")
            params.append(f"%{q}%")
        where = " AND ".join(conds)

        cur.execute(f"""
            SELECT COUNT(*) AS c FROM category_filters cf
            JOIN attributes a ON a.id = cf.attribute_id WHERE {where}
        """, params)
        total = cur.fetchone()["c"]

        cur.execute(f"""
            SELECT cf.id, cf.category_id, cf.attribute_id, cf.position, cf.enabled,
                   a.name AS attribute_name,
                   c.name AS category_name
            FROM category_filters cf
            JOIN attributes a ON a.id = cf.attribute_id
            LEFT JOIN categories c ON c.id = cf.category_id
            WHERE {where}
            ORDER BY COALESCE(c.name,''), cf.position, cf.id
            LIMIT %s OFFSET %s
        """, params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.post("/filters")
async def create_filter(data: FilterIn, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT 1 FROM attributes WHERE id=%s", (data.attribute_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Атрибут не знайдено")
        if data.category_id is not None:
            cur.execute("SELECT 1 FROM categories WHERE id=%s", (data.category_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Категорію не знайдено")
        try:
            cur.execute(
                "INSERT INTO category_filters (category_id, attribute_id, position, enabled)"
                " VALUES (%s,%s,%s,true) RETURNING id",
                (data.category_id, data.attribute_id, data.position),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="Такий фільтр вже додано до категорії")
        return {"ok": True, "id": cur.fetchone()["id"]}
    finally:
        conn.close()


@router.patch("/filters/{fid}")
async def update_filter(fid: int, data: FilterUpdate, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT id FROM category_filters WHERE id=%s", (fid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Фільтр не знайдено")
        sets, params = [], []
        if data.category_id is not None:
            sets.append("category_id=%s"); params.append(data.category_id)
        if data.position is not None:
            sets.append("position=%s"); params.append(data.position)
        if data.enabled is not None:
            sets.append("enabled=%s"); params.append(data.enabled)
        if sets:
            params.append(fid)
            cur.execute(f"UPDATE category_filters SET {', '.join(sets)} WHERE id=%s", params)
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/filters/{fid}")
async def delete_filter(fid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("DELETE FROM category_filters WHERE id=%s", (fid,))
        return {"ok": True}
    finally:
        conn.close()

