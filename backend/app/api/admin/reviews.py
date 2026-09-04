"""Admin reviews API.

Endpoints:
- GET    /admin/reviews — list with filters (status, rating, search)
- GET    /admin/reviews/{review_id} — detail
- PATCH  /admin/reviews/{review_id} — moderate (approve/reject/unpublish/republish)
- DELETE /admin/reviews/{review_id} — delete
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

logger = logging.getLogger(__name__)

router = APIRouter()

# Valid status transitions:
#   PENDING -> APPROVED, PENDING -> REJECTED  (initial moderation)
#   APPROVED -> REJECTED  (unpublish)
#   REJECTED -> APPROVED  (republish)
VALID_TRANSITIONS = {
    "PENDING": ("APPROVED", "REJECTED"),
    "APPROVED": ("REJECTED",),
    "REJECTED": ("APPROVED",),
}


class ReviewModerateRequest(BaseModel):
    status: str  # APPROVED or REJECTED


@router.get("/reviews")
def list_reviews(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    rating: Optional[int] = None,
    q: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Paginated review list with status, rating, and search filters."""
    conn, cur = admin_cursor()
    try:
        conds, params = ["1=1"], []

        if status:
            conds.append("r.status = %s")
            params.append(status.upper())

        if rating is not None:
            conds.append("r.rating = %s")
            params.append(rating)

        if q:
            conds.append(
                "(p.name ILIKE %s OR p.sku ILIKE %s OR u.email ILIKE %s OR u.full_name ILIKE %s OR r.content ILIKE %s)"
            )
            like = f"%{q}%"
            params.extend([like, like, like, like, like])

        where = " AND ".join(conds)

        # Count total
        cur.execute(
            f"SELECT COUNT(*) AS c FROM product_reviews r "
            f"LEFT JOIN products p ON p.id = r.product_id "
            f"LEFT JOIN users u ON u.id = r.user_id "
            f"WHERE {where}",
            params,
        )
        total = cur.fetchone()["c"]

        # Fetch page
        offset = (page - 1) * per_page
        cur.execute(
            f"""
            SELECT r.id, r.product_id, p.name AS product_name, p.sku AS product_sku,
                   r.user_id, u.full_name AS user_name, u.email AS user_email,
                   r.author_name, r.author_email, r.rating, r.content, r.status,
                   r.created_at, r.updated_at, r.moderated_at, r.moderated_by,
                   m.full_name AS moderator_name
            FROM product_reviews r
            LEFT JOIN products p ON p.id = r.product_id
            LEFT JOIN users u ON u.id = r.user_id
            LEFT JOIN users m ON m.id = r.moderated_by
            WHERE {where}
            ORDER BY r.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        items = cur.fetchall()

        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/reviews/{review_id}")
def get_review(
    review_id: int,
    user: dict = Depends(require_admin),
):
    """Get full review details."""
    conn, cur = admin_cursor()
    try:
        cur.execute(
            """
            SELECT r.id, r.product_id, p.name AS product_name, p.sku AS product_sku,
                   r.user_id, u.full_name AS user_name, u.email AS user_email,
                   r.author_name, r.author_email, r.rating, r.content, r.status,
                   r.created_at, r.updated_at, r.moderated_at, r.moderated_by,
                   m.full_name AS moderator_name
            FROM product_reviews r
            LEFT JOIN products p ON p.id = r.product_id
            LEFT JOIN users u ON u.id = r.user_id
            LEFT JOIN users m ON m.id = r.moderated_by
            WHERE r.id = %s
            """,
            (review_id,),
        )
        review = cur.fetchone()
        if not review:
            raise HTTPException(status_code=404, detail="Відгук не знайдено")
        return review
    finally:
        conn.close()


@router.patch("/reviews/{review_id}")
def moderate_review(
    review_id: int,
    data: ReviewModerateRequest,
    user: dict = Depends(require_admin),
):
    """Moderate a review: change status.

    Transitions supported:
      PENDING -> APPROVED   (publish)
      PENDING -> REJECTED   (reject)
      APPROVED -> REJECTED  (unpublish)
      REJECTED -> APPROVED  (republish)
    """
    new_status = data.status.upper()

    if new_status not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=400,
            detail="Невірний статус. Допустимі значення: APPROVED, REJECTED",
        )

    conn, cur = admin_cursor()
    try:
        # Get current status
        cur.execute("SELECT status FROM product_reviews WHERE id = %s", (review_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Відгук не знайдено")

        current_status = row["status"]

        # Validate transition
        allowed = VALID_TRANSITIONS.get(current_status, ())
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Неможливо змінити статус з {current_status} на {new_status}",
            )

        # Update with moderation info
        cur.execute(
            """
            UPDATE product_reviews
            SET status = %s, moderated_at = NOW(), moderated_by = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (new_status, user["id"], review_id),
        )

        logger.info(
            "Admin %s moderated review %d: %s -> %s",
            user["email"],
            review_id,
            current_status,
            new_status,
        )

        return {"ok": True, "status": new_status}
    finally:
        conn.close()


@router.delete("/reviews/{review_id}")
def delete_review(
    review_id: int,
    user: dict = Depends(require_admin),
):
    """Delete a review."""
    conn, cur = admin_cursor()
    try:
        cur.execute("DELETE FROM product_reviews WHERE id = %s", (review_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Відгук не знайдено")
        return {"ok": True}
    finally:
        conn.close()


