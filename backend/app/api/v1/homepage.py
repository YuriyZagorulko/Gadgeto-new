"""Public homepage API — returns configured slider slides and recommended products."""

from fastapi import APIRouter, Depends

from app.core.db_connect import get_cursor_dep

router = APIRouter()


@router.get("/home")
def get_homepage(cur=Depends(get_cursor_dep)):
    """Homepage content: active slider slides + recommended products + new arrivals."""

    # Active slider slides ordered by sort_order
    cur.execute("""
        SELECT id, image, title, subtitle, button_text, url, sort_order
        FROM homepage_slides
        WHERE is_active = true
        ORDER BY sort_order, id
    """)
    slides = [dict(r) for r in cur.fetchall()]

    # Recommended product IDs (ordered)
    cur.execute("""
        SELECT hrp.product_id, hrp.sort_order
        FROM homepage_recommended_products hrp
        ORDER BY hrp.sort_order, hrp.id
        LIMIT 12
    """)
    recommended_ids = [r["product_id"] for r in cur.fetchall()]

    # Load recommended products
    recommended = []
    if recommended_ids:
        cur.execute("""
            SELECT p.id, p.sku, p.name, p.slug, p.price, p.old_price,
                   p.stock_status, p.stock_qty, p.created_at,
                   (SELECT url FROM product_images
                    WHERE product_id = p.id AND is_suppressed = FALSE
                    ORDER BY sort_order, id LIMIT 1) AS image,
                   COALESCE(b.name, '') AS brand
            FROM products p
            LEFT JOIN brands b ON b.id = p.brand_id
            WHERE p.id = ANY(%s) AND p.is_active = true AND p.is_visible = true
        """, (recommended_ids,))
        rows = {r["id"]: dict(r) for r in cur.fetchall()}
        recommended = [rows.get(pid) for pid in recommended_ids if pid in rows]

    # New arrivals (latest 12 visible products)
    cur.execute("""
        SELECT p.id, p.sku, p.name, p.slug, p.price, p.old_price,
               p.stock_status, p.stock_qty, p.created_at,
               (SELECT url FROM product_images
                WHERE product_id = p.id AND is_suppressed = FALSE
                ORDER BY sort_order, id LIMIT 1) AS image,
               COALESCE(b.name, '') AS brand
        FROM products p
        LEFT JOIN brands b ON b.id = p.brand_id
        WHERE p.is_active = true AND p.is_visible = true
          AND p.stock_status = 'in_stock'
        ORDER BY p.created_at DESC
        LIMIT 12
    """)
    new_arrivals = [dict(r) for r in cur.fetchall()]

    return {
        "slides": slides,
        "recommended": recommended,
        "new_arrivals": new_arrivals,
    }