"""LiqPay payment integration API."""
import json, hashlib, base64, os
from fastapi import APIRouter, HTTPException

router = APIRouter()
from app.core.db_connect import admin_cursor

LIQPAY_PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY", "sandbox_i1234567890")
LIQPAY_PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY", "")

def liqpay_sign(data: dict) -> str:
    str_to_sign = LIQPAY_PRIVATE_KEY + base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode()
    return base64.b64encode(hashlib.sha1(str_to_sign.encode()).digest()).decode()

@router.post("/payments/liqpay/create")
def create_payment(order_id: int, token: str = ""):
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT number, total_amount, status, email FROM orders WHERE id=%s", (order_id,))
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        liqpay_order_id = f"gdt_{order['number']}_{order_id}"

        data = {
            "public_key": LIQPAY_PUBLIC_KEY,
            "version": "3",
            "action": "pay",
            "amount": str(order["total_amount"] / 100),
            "currency": "UAH",
            "description": f"Payment for order #{order['number']}",
            "order_id": liqpay_order_id,
            "result_url": f"http://localhost:3000/checkout/success?order_id={order_id}",
            "server_url": f"http://localhost:8000/api/v1/payments/liqpay/callback",
        }
        data["signature"] = liqpay_sign(data)
        cur.execute("""
            INSERT INTO payments (order_id, payment_id, liqpay_order_id, status, amount, currency, created_at, updated_at)
            VALUES (%s, %s, %s, 'pending', %s, 'UAH', NOW(), NOW())
            ON CONFLICT (payment_id) DO NOTHING
        """, (order_id, liqpay_order_id, liqpay_order_id, order["total_amount"]))
        return {"data": base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode(), "signature": data["signature"]}
    finally:
        conn.close()

@router.post("/payments/liqpay/callback")
def liqpay_callback(data: str = "", signature: str = ""):
    expected_sig = liqpay_sign({"data": data})
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
