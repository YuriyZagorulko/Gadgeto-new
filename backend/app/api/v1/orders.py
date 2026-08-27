"""Orders + Checkout API."""
import hashlib, secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()
from app.core.db_connect import get_connection_dep, managed_cursor


def get_user_from_token(token: str):
    """Verify auth token and return user.

    Dedicated managed connection so the helper is safe to call both standalone
    and inside other handlers; always closed, even on exceptions.
    """
    with managed_cursor() as cur:
        th = hashlib.sha256(token.encode()).hexdigest()
        cur.execute("""
            SELECT u.id, u.email, u.full_name, u.phone, u.role FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > NOW()
        """, (th,))
        return cur.fetchone()


class CheckoutRequest(BaseModel):
    session_token: str = ""
    first_name: str
    last_name: str
    phone: str
    email: str
    city_ref: str = ""
    city_name: str = ""
    warehouse_ref: str = ""
    warehouse_number: str = ""
    delivery_address: str = ""
    notes: str = ""
    auth_token: str = ""


@router.post("/checkout")
def checkout(req: CheckoutRequest, _db: tuple = Depends(get_connection_dep)):
    conn, cur = _db

    # Validate email
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    # Get cart
    user = None
    if req.auth_token:
        user = get_user_from_token(req.auth_token)

    cart_id = None
    if user:
        cur.execute("SELECT id FROM carts WHERE user_id = %s", (user["id"],))
        r = cur.fetchone()
        if r: cart_id = r["id"]

    if not cart_id and req.session_token:
        cur.execute("SELECT id FROM carts WHERE session_token = %s", (req.session_token,))
        r = cur.fetchone()
        if r: cart_id = r["id"]

    if not cart_id:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Get cart items
    cur.execute("""
        SELECT ci.product_id, ci.qty, ci.price_at_addition, p.name, p.sku, p.price, p.stock_status
        FROM cart_items ci JOIN products p ON p.id=ci.product_id WHERE ci.cart_id=%s
    """, (cart_id,))
    items = cur.fetchall()
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Validate stock
    for item in items:
        if item["stock_status"] == "out_of_stock":
            raise HTTPException(status_code=400, detail=f"Product '{item['name']}' is out of stock")

    # Calculate totals
    subtotal = sum(item["qty"] * (item["price_at_addition"] or item["price"] or 0) for item in items)
    shipping = 0
    total = subtotal + shipping

    # Create order
    buyer_name = f"{req.first_name} {req.last_name}".strip()
    order_number = f"GDT-{secrets.token_hex(4).upper()}"

    cur.execute("""
        INSERT INTO orders (number, user_id, buyer_name, email, phone, status, total_amount, subtotal_amount,
            shipping_amount, city_ref, warehouse_ref, warehouse_number, delivery_address, notes,
            payment_method, payment_status, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,'PENDING',%s,%s,%s,%s,%s,%s,%s,%s,'liqpay','pending',NOW(),NOW())
        RETURNING id
    """, (order_number, user["id"] if user else None, buyer_name, req.email, req.phone,
          total, subtotal, shipping, req.city_ref, req.warehouse_ref, req.warehouse_number,
          req.delivery_address[:500] if req.delivery_address else "", req.notes))
    order_id = cur.fetchone()["id"]

    # Create order items (snapshot)
    for item in items:
        cur.execute("""
            INSERT INTO order_items (order_id, product_id, product_name, product_sku, qty, price, total)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (order_id, item["product_id"], item["name"], item["sku"], item["qty"],
              item["price_at_addition"] or item["price"],
              item["qty"] * (item["price_at_addition"] or item["price"])))

    # Clear cart
    cur.execute("DELETE FROM cart_items WHERE cart_id=%s", (cart_id,))

    return {"order_id": order_id, "number": order_number, "total": total, "status": "PENDING"}


@router.get("/orders")
def get_orders(token: str = "", _db: tuple = Depends(get_connection_dep)):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    conn, cur = _db
    cur.execute("SELECT id, number, status, total_amount, created_at FROM orders WHERE user_id=%s ORDER BY created_at DESC LIMIT 50", (user["id"],))
    orders = cur.fetchall()
    return {"items": orders}


@router.get("/orders/{order_id}")
def get_order(order_id: int, token: str = "", _db: tuple = Depends(get_connection_dep)):
    user = get_user_from_token(token)

    conn, cur = _db
    cur.execute("""
        SELECT o.* FROM orders o WHERE o.id=%s
        AND (%s IS NULL OR o.user_id=%s)
    """, (order_id, user["id"] if user else None, user["id"] if user else 0))
    order = cur.fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    cur.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    items = cur.fetchall()
    return {"order": order, "items": items}