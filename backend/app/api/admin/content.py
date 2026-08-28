"""Admin API for homepage content management — slider slides and recommended products."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

router = APIRouter()


# ── Slides ───────────────────────────────────────────────────────────────────

class SlideCreate(BaseModel):
    image: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    button_text: Optional[str] = None
    url: str
    is_active: bool = True
    sort_order: int = 0


class SlideUpdate(BaseModel):
    image: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    button_text: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("/content/homepage/slides")
def list_slides(user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            SELECT id, image, title, subtitle, button_text, url,
                   is_active, sort_order, created_at, updated_at
            FROM homepage_slides
            ORDER BY sort_order, id
        """)
        return {"items": [dict(r) for r in cur.fetchall()]}
    finally:
        conn.close()


@router.post("/content/homepage/slides")
def create_slide(body: SlideCreate, user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            INSERT INTO homepage_slides (image, title, subtitle, button_text, url,
                                         is_active, sort_order, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING id
        """, (body.image, body.title, body.subtitle, body.button_text,
              body.url, body.is_active, body.sort_order))
        sid = cur.fetchone()["id"]
        return {"id": sid, "ok": True}
    finally:
        conn.close()


@router.put("/content/homepage/slides/{slide_id}")
def update_slide(slide_id: int, body: SlideUpdate, user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM homepage_slides WHERE id=%s", (slide_id,))
        if not cur.fetchone():
            raise HTTPException(404, detail="Слайд не знайдено")

        sets, args = [], []
        for col in ("image", "title", "subtitle", "button_text", "url",
                    "is_active", "sort_order"):
            val = getattr(body, col, None)
            if val is not None:
                sets.append(f"{col} = %s")
                args.append(val)
        if not sets:
            return {"ok": True}
        args.append(slide_id)
        cur.execute(f"UPDATE homepage_slides SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s", args)
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/content/homepage/slides/{slide_id}")
def delete_slide(slide_id: int, user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("DELETE FROM homepage_slides WHERE id=%s", (slide_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, detail="Слайд не знайдено")
        return {"ok": True}
    finally:
        conn.close()


# ── Recommended Products ────────────────────────────────────────────────────

@router.get("/content/homepage/recommended")
def list_recommended(user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            SELECT hrp.id, hrp.product_id, hrp.sort_order,
                   p.name, p.sku, p.slug, p.price,
                   (SELECT url FROM product_images
                    WHERE product_id = p.id AND is_suppressed = FALSE
                    ORDER BY sort_order, id LIMIT 1) AS image
            FROM homepage_recommended_products hrp
            JOIN products p ON p.id = hrp.product_id
            ORDER BY hrp.sort_order, hrp.id
            LIMIT 12
        """)
        return {"items": [dict(r) for r in cur.fetchall()]}
    finally:
        conn.close()


class RecommendedReorder(BaseModel):
    product_ids: list[int]  # ordered list of up to 12 product IDs


@router.put("/content/homepage/recommended")
def update_recommended(body: RecommendedReorder, user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        if len(body.product_ids) > 12:
            raise HTTPException(422, detail="Максимум 12 товарів")

        # Verify all products exist
        cur.execute("SELECT id FROM products WHERE id = ANY(%s)", (body.product_ids,))
        existing = {r["id"] for r in cur.fetchall()}
        missing = set(body.product_ids) - existing
        if missing:
            raise HTTPException(422, detail=f"Товари не знайдено: {missing}")

        # Replace all recommended products
        cur.execute("DELETE FROM homepage_recommended_products")
        for i, pid in enumerate(body.product_ids):
            cur.execute("""
                INSERT INTO homepage_recommended_products (product_id, sort_order, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
            """, (pid, i))
        return {"ok": True, "count": len(body.product_ids)}
    finally:
        conn.close()