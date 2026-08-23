"""Cart API - guest and authenticated."""
import json, secrets
from fastapi import APIRouter, HTTPException, Cookie, Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter()
from app.core.db_connect import DB, connect
import psycopg2
import psycopg2.extras

class CartItemRequest(BaseModel):
    product_id: int
    qty: int = 1

class CartItemUpdate(BaseModel):
    qty: int

def get_or_create_cart(cur, session_token: Optional[str] = None, user_id: Optional[int] = None):
    if not session_token:
        session_token = "guest_" + secrets.token_hex(16)
    cur.execute("SELECT id FROM carts WHERE session_token = %s OR (user_id = %s AND user_id IS NOT NULL)", (session_token, user_id or 0))
    cart = cur.fetchone()
    if cart:
        return cart["id"], session_token
    cur.execute("INSERT INTO carts (session_token, user_id, created_at, updated_at) VALUES (%s, %s, NOW(), NOW()) RETURNING id", (session_token, user_id))
    return cur.fetchone()["id"], session_token

@router.get("/cart")
async def get_cart(session_token: str = ""):
    
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cart_id, token = get_or_create_cart(cur, session_token)
    cur.execute("""
        SELECT ci.id, ci.product_id, ci.qty, ci.price_at_addition, p.name, p.sku, p.slug, p.price, p.stock_status,
               (SELECT url FROM product_images WHERE product_id=p.id AND is_primary=true LIMIT 1) as image
        FROM cart_items ci JOIN products p ON p.id=ci.product_id WHERE ci.cart_id=%s ORDER BY ci.id
    """, (cart_id,))
    items = cur.fetchall()
    subtotal = sum(i["qty"] * (i["price_at_addition"] or i["price"] or 0) for i in items)
    conn.close()
    return {"cart_id": cart_id, "session_token": token, "items": items, "subtotal": subtotal}

@router.post("/cart/items")
async def add_to_cart(req: CartItemRequest, session_token: str = ""):
    
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cart_id, token = get_or_create_cart(cur, session_token)
    cur.execute("SELECT id, price, stock_status FROM products WHERE id=%s AND is_active=true", (req.product_id,))
    product = cur.fetchone()
    if not product:
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    if product["stock_status"] == "out_of_stock":
        conn.close()
        raise HTTPException(status_code=400, detail="Product is out of stock")
    cur.execute("SELECT id, qty FROM cart_items WHERE cart_id=%s AND product_id=%s", (cart_id, req.product_id))
    existing = cur.fetchone()
    if existing:
        new_qty = existing["qty"] + req.qty
        cur.execute("UPDATE cart_items SET qty=%s, updated_at=NOW() WHERE id=%s", (new_qty, existing["id"]))
    else:
        cur.execute("INSERT INTO cart_items (cart_id, product_id, qty, price_at_addition, created_at, updated_at) VALUES (%s, %s, %s, %s, NOW(), NOW())", (cart_id, req.product_id, req.qty, product["price"]))
    conn.commit()
    conn.close()
    return {"ok": True, "session_token": token}

@router.put("/cart/items/{item_id}")
async def update_cart_item(item_id: int, req: CartItemUpdate):
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor()
    if req.qty <= 0:
        cur.execute("DELETE FROM cart_items WHERE id=%s", (item_id,))
    else:
        cur.execute("UPDATE cart_items SET qty=%s WHERE id=%s", (req.qty, item_id))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.delete("/cart/items/{item_id}")
async def remove_cart_item(item_id: int):
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id=%s", (item_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
