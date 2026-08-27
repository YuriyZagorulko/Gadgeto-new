# Admin brands API
import re
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

router = APIRouter()


class BrandIn(BaseModel):
    name: str
    description: Optional[str] = None
    logo: Optional[str] = None
    is_active: bool = True


@router.get("/brands")
def list_brands(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                      search: Optional[str] = None, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        conds, params = ["1=1"], []
        if search:
            conds.append("b.name ILIKE %s"); params.append(f"%{search}%")
        where = " AND ".join(conds)
        cur.execute(f"SELECT count(*) AS c FROM brands b WHERE {where}", params)
        total = cur.fetchone()["c"]
        offset = (page - 1) * per_page
        cur.execute(f"""
            SELECT b.id, b.name, b.slug, b.description, b.logo, b.is_active,
                   (SELECT count(*) FROM products p WHERE p.brand_id=b.id) AS products_count
            FROM brands b WHERE {where}
            ORDER BY b.name LIMIT %s OFFSET %s
        """, params + [per_page, offset])
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page,
                "total_pages": max(1, (total + per_page - 1) // per_page)}
    finally:
        conn.close()


@router.post("/brands")
def create_brand(data: BrandIn, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        slug = re.sub(r"[^a-z0-9]+", "-", data.name.lower()).strip("-") or "brand"
        base, i = slug, 2
        while True:
            cur.execute("SELECT 1 FROM brands WHERE slug=%s", (slug,))
            if not cur.fetchone():
                break
            slug = f"{base}-{i}"; i += 1
        cur.execute("""INSERT INTO brands (name, slug, description, logo, is_active)
                       VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                    (data.name.strip(), slug, data.description, data.logo, data.is_active))
        return {"ok": True, "id": cur.fetchone()["id"]}
    finally:
        conn.close()


@router.put("/brands/{bid}")
def update_brand(bid: int, data: BrandIn, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("UPDATE brands SET name=%s, description=%s, logo=%s, is_active=%s, updated_at=NOW() WHERE id=%s",
                    (data.name.strip(), data.description, data.logo, data.is_active, bid))
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/brands/{bid}")
def delete_brand(bid: int, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT count(*) AS c FROM products WHERE brand_id=%s", (bid,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409, detail="До бренду прив'язані товари — деактивуйте його замість видалення.")
        cur.execute("DELETE FROM brands WHERE id=%s", (bid,))
        return {"ok": True}
    finally:
        conn.close()

