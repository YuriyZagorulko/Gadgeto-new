"""Admin orders API."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


ORDER_STATUSES = ("PENDING", "PROCESSING", "PAID", "SHIPPED", "DELIVERED", "CANCELLED", "REFUNDED")


def _db_status(status: str) -> str:
    """Order statuses are stored as enum NAMES (uppercase) in PostgreSQL."""
    return (status or "").strip().upper()


class OrderStatusUpdate(BaseModel):
    status: str


@router.get("/orders")
def list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Paginated order list with search and filters."""
    conn, cur = admin_cursor()
    try:
        conds, params = ["1=1"], []
        if q:
            conds.append("(o.number ILIKE %s OR o.email ILIKE %s OR o.phone ILIKE %s OR o.buyer_name ILIKE %s)")
            like = f"%{q}%"
            params.extend([like, like, like, like])
        if status:
            conds.append("o.status = %s")
            params.append(_db_status(status))
        if payment_status:
            conds.append("o.payment_status = %s")
            params.append(payment_status)
        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) AS c FROM orders o WHERE {where}", params)
        total = cur.fetchone()["c"]

        offset = (page - 1) * per_page
        cur.execute(
            f"""
            SELECT o.id, o.number, o.buyer_name, o.email, o.phone, o.status,
                   o.payment_status, o.payment_method, o.total_amount,
                   o.shipping_amount, o.created_at,
                   (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.id) AS items_count
            FROM orders o
            WHERE {where}
            ORDER BY o.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/orders/{order_id}")
def get_order(order_id: int, user: dict = Depends(require_admin)):
    """Full order details: items, events, payments, shipping info."""
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")

        cur.execute(
            """
            SELECT oi.id, oi.product_id, oi.product_name, oi.product_sku,
                   oi.qty, oi.price, oi.total, p.slug AS product_slug
            FROM order_items oi
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id = %s
            """,
            (order_id,),
        )
        items = cur.fetchall()

        cur.execute(
            "SELECT id, event, actor, payload_json, created_at FROM order_events "
            "WHERE order_id = %s ORDER BY created_at ASC",
            (order_id,),
        )
        events = cur.fetchall()
        for ev in events:
            if ev.get("payload_json"):
                try:
                    ev["payload"] = json.loads(ev.pop("payload_json"))
                except (ValueError, TypeError):
                    ev["payload"] = None

        cur.execute(
            "SELECT id, payment_id, status, amount, currency, card_mask, card_type, created_at "
            "FROM payments WHERE order_id = %s ORDER BY created_at ASC",
            (order_id,),
        )
        payments = cur.fetchall()

        shipping = None
        if order.get("shipping_address_json"):
            try:
                shipping = json.loads(order["shipping_address_json"])
            except (ValueError, TypeError):
                shipping = None

        return {
            "order": order,
            "items": items,
            "events": events,
            "payments": payments,
            "shipping": shipping,
        }
    finally:
        conn.close()


@router.patch("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    user: dict = Depends(require_admin),
):
    """Change order status; records an event for the audit trail."""
    if data.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Невірний статус замовлення")

    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id, status FROM orders WHERE id = %s", (order_id,))
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")

        cur.execute(
            "UPDATE orders SET status = %s, updated_at = NOW() WHERE id = %s",
            (data.status, order_id),
        )
        payload = json.dumps({"from": str(order["status"]), "to": data.status})
        cur.execute(
            "INSERT INTO order_events (order_id, event, actor, payload_json, created_at) "
            "VALUES (%s, 'status_changed', %s, %s, NOW())",
            (order_id, user.get("email") or "admin", payload),
        )
        cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        return {"ok": True, "status": cur.fetchone()["status"]}
    finally:
        conn.close()

