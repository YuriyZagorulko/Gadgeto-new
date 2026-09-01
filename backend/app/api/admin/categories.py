# Admin categories API
import re
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor
from app.utils.duplicate_check import find_duplicate_category, normalize_name

router = APIRouter()


def _slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9а-яіїєґё\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s or "category"


class CategoryIn(BaseModel):
    name: str
    parent_id: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0


@router.get("/categories/tree")
def category_tree(user: dict = Depends(require_admin)):
    """Full category hierarchy with product counts."""
    conn, cur = admin_cursor()
    try:
        cur.execute("""SELECT id, parent_id, name, slug, is_active, sort_order,
                       product_count FROM categories ORDER BY sort_order, name""")
        rows = cur.fetchall()
        nodes = {r["id"]: {**r, "children": []} for r in rows}
        tree = []
        for n in nodes.values():
            if n["parent_id"] and n["parent_id"] in nodes:
                nodes[n["parent_id"]]["children"].append(n)
            else:
                tree.append(n)
        return {"items": tree}
    finally:
        conn.close()


@router.get("/categories")
def list_categories(user: dict = Depends(require_admin),
                          search: Optional[str] = None):
    conn, cur = admin_cursor()
    try:
        sql = """SELECT id, parent_id, name, slug, is_active, sort_order, product_count
                 FROM categories"""
        params = []
        if search:
            sql += " WHERE name ILIKE %s"
            params.append(f"%{search}%")
        sql += " ORDER BY sort_order, name"
        cur.execute(sql, params)
        return {"items": cur.fetchall()}
    finally:
        conn.close()


@router.post("/categories")
def create_category(data: CategoryIn, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        dup = find_duplicate_category(cur, data.name, data.parent_id)
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"Категорія з назвою «{data.name.strip()}» вже існує "
                       f"в цій батьківській категорії.",
            )
        slug = _slugify(data.name)
        base = slug
        i = 2
        while True:
            cur.execute("SELECT 1 FROM categories WHERE slug=%s", (slug,))
            if not cur.fetchone():
                break
            slug = f"{base}-{i}"; i += 1
        cur.execute(
            """INSERT INTO categories (name, slug, parent_id, description,
               is_active, sort_order, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,NOW(),NOW()) RETURNING id""",
            (data.name.strip(), slug, data.parent_id, data.description,
             data.is_active, data.sort_order))
        new_id = cur.fetchone()["id"]
        return {"ok": True, "id": new_id, "slug": slug}
    finally:
        conn.close()


@router.put("/categories/{cid}")
def update_category(cid: int, data: CategoryIn, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM categories WHERE id=%s", (cid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Категорію не знайдено")
        if data.parent_id == cid:
            raise HTTPException(status_code=400, detail="Категорія не може бути батьком для себе")
        dup = find_duplicate_category(cur, data.name, data.parent_id, exclude_id=cid)
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"Категорія з назвою «{data.name.strip()}» вже існує "
                       f"в цій батьківській категорії.",
            )
        cur.execute(
            """UPDATE categories SET name=%s, parent_id=%s, description=%s,
               is_active=%s, sort_order=%s, updated_at=NOW() WHERE id=%s""",
            (data.name.strip(), data.parent_id, data.description,
             data.is_active, data.sort_order, cid))
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/categories/{cid}")
def delete_category(cid: int, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT count(*) AS c FROM categories WHERE parent_id=%s", (cid,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409, detail="Спочатку видаліть або перемістіть підкатегорії")
        cur.execute("SELECT count(*) AS c FROM product_categories WHERE category_id=%s", (cid,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409, detail="До категорії прив'язані товари — спочатку приберіть прив'язки")
        cur.execute("SELECT count(*) AS c FROM category_mappings WHERE category_id=%s", (cid,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409, detail="До категорії прив'язані маппінги — спочатку видаліть їх")
        cur.execute("DELETE FROM category_filters WHERE category_id=%s", (cid,))
        cur.execute("DELETE FROM categories WHERE id=%s", (cid,))
        return {"ok": True}
    finally:
        conn.close()

