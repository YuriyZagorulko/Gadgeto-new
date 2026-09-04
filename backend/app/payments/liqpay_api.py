"""LiqPay payment integration API."""
import json, hashlib, base64
from fastapi import APIRouter, HTTPException

router = APIRouter()
from app.core.db_connect import admin_cursor
from app.core.config import settings


def _get_keys() -> tuple[str, str]:
    """Return (public_key, private_key) respecting LIQPAY_TEST_MODE."""
    if settings.LIQPAY_TEST_MODE:
        return settings.LIQPAY_TEST_PUBLIC_KEY, settings.LIQPAY_TEST_PRIVATE_KEY
    return settings.LIQPAY_PUBLIC_KEY, settings.LIQPAY_PRIVATE_KEY


def liqpay_sign(base64_data: str, private_key: str) -> str:
    """LiqPay signature: base64(sha1(private_key + base64_data + private_key))."""
    str_to_sign = private_key + base64_data + private_key
    return base64.b64encode(hashlib.sha1(str_to_sign.encode()).digest()).decode()


def generate_liqpay_payment(order_id: int, order_number: str, total_amount: int) -> dict:
    """Create a LiqPay payment record and return {data, signature} for the checkout form.

    Reused by both the standalone /payments/liqpay/create endpoint and the
    integrated checkout flow (payment_method=liqpay).
    """
    public_key, private_key = _get_keys()
    frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
    backend_url = frontend_url.replace("3000", "8000")

    liqpay_order_id = f"gdt_{order_number}_{order_id}"
    # LiqPay expects amount in UAH (total_amount is in kopecks). Use 2 decimal places.
    amount_uah = round(total_amount / 100, 2)
    data = {
        "public_key": public_key,
        "version": "3",
        "action": "pay",
        "amount": f"{amount_uah:.2f}",
        "currency": "UAH",
        "description": f"Оплата замовлення #{order_number}",
        "order_id": liqpay_order_id,
        "result_url": f"{frontend_url}/checkout/success?order_id={order_id}",
        "server_url": f"{backend_url}/api/v1/payments/liqpay/callback",
    }
    data_b64 = base64.b64encode(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode()).decode()
    signature = liqpay_sign(data_b64, private_key)
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            INSERT INTO payments (order_id, payment_id, liqpay_order_id, status, amount, currency, created_at, updated_at)
            VALUES (%s, %s, %s, 'pending', %s, 'UAH', NOW(), NOW())
            ON CONFLICT (payment_id) DO NOTHING
        """, (order_id, liqpay_order_id, liqpay_order_id, total_amount))
    finally:
        conn.close()
    return {
        "data": data_b64,
        "signature": signature,
        "public_key": public_key,
        "action_url": "https://www.liqpay.ua/api/3/checkout",
    }


@router.post("/payments/liqpay/create")
def create_payment(order_id: int, token: str = ""):
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT number, total_amount, status FROM orders WHERE id=%s", (order_id,))
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return generate_liqpay_payment(order_id, order["number"], order["total_amount"])
    finally:
        conn.close()

@router.post("/payments/liqpay/callback")
def liqpay_callback(data: str = "", signature: str = ""):
    expected_sig = liqpay_sign(data)
    if signature != expected_sig:
        raise HTTPException(status_code=400, detail="Invalid signature")

    decoded = json.loads(base64.b64decode(data).decode())
    liqpay_order_id = decoded.get("order_id", "")
    status = decoded.get("status", "")
    amount = decoded.get("amount", "0")

    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id, order_id, status FROM payments WHERE liqpay_order_id=%s", (liqpay_order_id,))
        payment = cur.fetchone()
        if not payment:
            return {"status": "payment_not_found"}

        if payment["status"] == "paid":
            return {"status": "already_processed"}

        new_status = "paid" if status == "success" else "failed" if status in ("failure", "error") else status
        cur.execute("UPDATE payments SET status=%s, raw_callback_json=%s, updated_at=NOW() WHERE id=%s",
                    (new_status, json.dumps(decoded), payment["id"]))

        if new_status == "paid":
            cur.execute("UPDATE orders SET status='PAID', payment_status='paid', updated_at=NOW() WHERE id=%s",
                        (payment["order_id"],))
        return {"status": "ok", "payment_status": new_status}
    finally:
        conn.close()
