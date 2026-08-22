"""Orders + Checkout API."""
import json, hashlib, secrets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()
DB = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"

def get_user_from_token(token: str):
    """Verify auth token and return user."""
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    th = hashlib.sha256(token.encode()).hexdigest()
    cur.execute("""
        SELECT u.id, u.email, u.full_name, u.phone, u.role FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = %s AND s.expires_at > NOW()
    """, (th,))
    user = cur.fetchone()
    conn.close()
    return user

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
async def checkout(req: CheckoutRequest):
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Validate email
    if not req.email or "@" not in req.email:
        conn.close()
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
        conn.close()
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Get cart items
    cur.execute("""
        SELECT ci.product_id, ci.qty, ci.price_at_addition, p.name, p.sku, p.price, p.stock_status
        FROM cart_items ci JOIN products p ON p.id=ci.product_id WHERE ci.cart_id=%s
    """, (cart_id,))
    items = cur.fetchall()
    if not items:
        conn.close()
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Validate stock
    for item in items:
        if item["stock_status"] == "out_of_stock":
            conn.close()
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
    
    conn.commit()
    conn.close()
    
    return {"order_id": order_id, "number": order_number, "total": total, "status": "PENDING"}

@router.get("/orders")
async def get_orders(token: str = ""):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, number, status, total_amount, created_at FROM orders WHERE user_id=%s ORDER BY created_at DESC LIMIT 50", (user["id"],))
    orders = cur.fetchall()
    conn.close()
    return {"items": orders}

@router.get("/orders/{order_id}")
async def get_order(order_id: int, token: str = ""):
    user = get_user_from_token(token)
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT o.* FROM orders o WHERE o.id=%s
        AND (%s IS NULL OR o.user_id=%s)
    """, (order_id, user["id"] if user else None, user["id"] if user else 0))
    order = cur.fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="Order not found")
    cur.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    items = cur.fetchall()
    conn.close()
    return {"order": order, "items": items}
