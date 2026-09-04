"""Orders + Checkout API."""
import hashlib, json, secrets
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
    # Nova Poshta delivery: "warehouse" (branch/postamat, default for
    # backward compatibility) or "courier" (address delivery).
    delivery_method: str = "warehouse"
    street_ref: str = ""
    street_name: str = ""
    building: str = ""
    apartment: str = ""
    notes: str = ""
    auth_token: str = ""
    # Payment method: "cod" (cash on delivery / накладений платіж),
    # "liqpay" (card payment via LiqPay), "bank_transfer" (банківський переказ).
    payment_method: str = "cod"


_PAYMENT_METHODS = ("cod", "liqpay", "bank_transfer")


def _build_delivery_info(req: CheckoutRequest) -> tuple[str, dict | None]:
    """Validate Nova Poshta delivery fields and build (delivery_address,
    shipping_address_json_dict).

    Pure function (no DB) so it is unit-testable. Raises HTTPException(400)
    on an invalid delivery combination. For the legacy "warehouse" method
    the client-provided delivery_address is preserved as-is; for "courier"
    the canonical address is built server-side from the selected refs.
    """
    method = (req.delivery_method or "warehouse").strip().lower()
    if method not in ("warehouse", "courier"):
        raise HTTPException(status_code=400, detail="Недійсний спосіб доставки")
    city = (req.city_name or "").strip()

    if method == "warehouse":
        # Legacy behaviour — no extra validation beyond what the client sends.
        return (req.delivery_address or "")[:500], None

    # Courier delivery — the address must come from NP reference data.
    street = (req.street_name or "").strip()
    building = (req.building or "").strip()
    if not city or not (req.city_ref or "").strip():
        raise HTTPException(status_code=400, detail="Оберіть місто доставки")
    if not (req.street_ref or "").strip() or not street:
        raise HTTPException(status_code=400, detail="Оберіть вулицю доставки")
    if not building:
        raise HTTPException(status_code=400, detail="Вкажіть номер будинку")

    apartment = (req.apartment or "").strip()
    address = f"{city}, {street} {building}"
    if apartment:
        address += f", кв. {apartment}"
    shipping = {
        "delivery_method": "Кур'єр",
        "city": city,
        "city_ref": (req.city_ref or "").strip(),
        "street": street,
        "street_ref": (req.street_ref or "").strip(),
        "building": building,
    }
    if apartment:
        shipping["apartment"] = apartment
    return address[:500], shipping


@router.post("/checkout")
def checkout(req: CheckoutRequest, _db: tuple = Depends(get_connection_dep)):
    conn, cur = _db

    # Validate email
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    # Validate delivery input and build the canonical delivery address
    # (fails fast with 400 on an invalid city/street/building combination).
    # Validate payment method
    payment_method = (req.payment_method or "cod").strip().lower()
    if payment_method not in _PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Недійсний спосіб оплати")

    delivery_address, shipping_json = _build_delivery_info(req)

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
            shipping_amount, city_ref, warehouse_ref, warehouse_number, delivery_address, shipping_address_json,
            notes, payment_method, payment_status, created_at, updated_at)
        VALUES (%s,%s,%s,%s,%s,'PENDING',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',NOW(),NOW())
        RETURNING id
    """, (order_number, user["id"] if user else None, buyer_name, req.email, req.phone,
          total, subtotal, shipping, req.city_ref, req.warehouse_ref, req.warehouse_number,
          delivery_address,
          json.dumps(shipping_json, ensure_ascii=False) if shipping_json else None,
          req.notes, payment_method))
    order_id = cur.fetchone()["id"]

    # Create order items (snapshot)
    for item in items:
        cur.execute("""
            INSERT INTO order_items (order_id, product_id, product_name, product_sku, qty, price, total, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
        """, (order_id, item["product_id"], item["name"], item["sku"], item["qty"],
              item["price_at_addition"] or item["price"],
              item["qty"] * (item["price_at_addition"] or item["price"])))

    # Clear cart
    cur.execute("DELETE FROM cart_items WHERE cart_id=%s", (cart_id,))

    response = {"order_id": order_id, "number": order_number, "total": total,
                "status": "PENDING", "payment_method": payment_method}

    # If LiqPay, generate payment data for frontend redirect
    if payment_method == "liqpay":
        from app.payments.liqpay_api import generate_liqpay_payment
        response["payment"] = generate_liqpay_payment(order_id, order_number, total)

    return response


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