"""Tests for admin order deletion (DELETE /api/v1/admin/orders/{order_id}).

Covers:
- authorized admin can delete an existing order (order + dependents removed)
- order no longer appears in the admin orders query after deletion
- non-admin / unauthenticated requests are rejected (403 / 401)
- deleting a non-existent order returns 404 (and repeat deletes are safe)
- related records (order_items, order_events, payments) are removed
- a failed deletion rolls back — no partially deleted data remains

NOTE: endpoints run through TestClient and open their own DB connections,
so fixtures COMMIT created rows to make them visible across connections and
clean up explicitly in teardown (see test_order_attribution.py convention).
The failure test uses a dedicated FK-blocker table so the final
`DELETE FROM orders` violates the FK — proving the transaction rolls back.
"""
import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
# Used only by the rollback test — behaves like a real HTTP client and
# surfaces server failures as 500 responses instead of raising them.
client_no_raise = TestClient(app, raise_server_exceptions=False)

BLOCKER_TABLE = "zz_test_order_fk_blocker"


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
@pytest.fixture
def order_fixture(db_connection):
    """Create product + admin/customer users + sessions + a full order
    (items, event, payment) and COMMIT so the endpoint sees them."""
    cur = db_connection.cursor()
    try:
        slug = _unique("del-product")
        admin_email = _unique("admin") + "@example.com"
        customer_email = _unique("customer") + "@example.com"
        admin_token = _unique("del-admin-token")
        customer_token = _unique("del-customer-token")
        order_number = _unique("GDT-DEL")

        cur.execute(
            "INSERT INTO products (name, slug, price, currency, stock_qty, status, is_active, is_visible,"
            " created_at, updated_at) "
            "VALUES ('Del Product', %s, 10000, 'UAH', 5, 'PUBLISHED', true, true, NOW(), NOW()) RETURNING id",
            (slug,),
        )
        product_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO users (email, password_hash, full_name, role, status, created_at, updated_at) "
            "VALUES (%s, 'hash', 'Admin', 'ADMIN', 'ACTIVE', NOW(), NOW()) RETURNING id",
            (admin_email,),
        )
        admin_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (email, password_hash, full_name, role, status, created_at, updated_at) "
            "VALUES (%s, 'hash', 'Customer', 'CUSTOMER', 'ACTIVE', NOW(), NOW()) RETURNING id",
            (customer_email,),
        )
        customer_id = cur.fetchone()[0]

        for token, user_id in ((admin_token, admin_id), (customer_token, customer_id)):
            th = hashlib.sha256(token.encode()).hexdigest()
            cur.execute(
                "INSERT INTO sessions (user_id, token_hash, expires_at, created_at, updated_at) "
                "VALUES (%s, %s, NOW() + INTERVAL '1 day', NOW(), NOW())",
                (user_id, th),
            )

        cur.execute(
            "INSERT INTO orders (number, buyer_name, email, phone, status, total_amount,"
            " subtotal_amount, shipping_amount, payment_status, city_ref, created_at, updated_at) "
            "VALUES (%s, 'Del Buyer', 'del@example.com', '+380501112233', 'PENDING', 20000,"
            " 20000, 0, 'pending', 'city-ref', NOW(), NOW()) RETURNING id",
            (order_number,),
        )
        order_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO order_items (order_id, product_id, product_name, product_sku, qty, price, total,"
            " created_at, updated_at) "
            "VALUES (%s, %s, 'Del Product', 'DEL-1', 2, 10000, 20000, NOW(), NOW())",
            (order_id, product_id),
        )
        cur.execute(
            "INSERT INTO order_events (order_id, event, actor, payload_json, created_at, updated_at) "
            "VALUES (%s, 'created', 'system', NULL, NOW(), NOW())",
            (order_id,),
        )
        cur.execute(
            "INSERT INTO payments (order_id, payment_id, status, amount, currency, created_at, updated_at) "
            "VALUES (%s, %s, 'pending', 20000, 'UAH', NOW(), NOW())",
            (order_id, _unique("pay")),
        )
        # Dedicated FK blocker (only used by the rollback test).
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {BLOCKER_TABLE} "
            "(order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE RESTRICT)"
        )
        db_connection.commit()

        yield {
            "order_id": order_id,
            "order_number": order_number,
            "admin_token": admin_token,
            "customer_token": customer_token,
        }
        # Best-effort cleanup of cross-connection rows.
        try:
            cur.execute(f"DROP TABLE IF EXISTS {BLOCKER_TABLE}")
            cur.execute("DELETE FROM order_items WHERE order_id = %s", (order_id,))
            cur.execute("DELETE FROM order_events WHERE order_id = %s", (order_id,))
            cur.execute("DELETE FROM payments WHERE order_id = %s", (order_id,))
            cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
            cur.execute("DELETE FROM sessions WHERE user_id IN (%s, %s)", (admin_id, customer_id))
            cur.execute("DELETE FROM users WHERE id IN (%s, %s)", (admin_id, customer_id))
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
            db_connection.commit()
        except Exception:
            db_connection.rollback()
    finally:
        cur.close()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _count(cur, table: str, order_id: int, column: str = "order_id") -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = %s", (order_id,))
    return cur.fetchone()[0]
def test_admin_can_delete_order_and_dependents(db_connection, order_fixture, test_settings):
    oid = order_fixture["order_id"]
    resp = client.delete(
        f"/api/v1/admin/orders/{oid}", headers=_auth(order_fixture["admin_token"])
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True, "id": oid}

    cur = db_connection.cursor()
    try:
        assert _count(cur, "order_items", oid) == 0
        assert _count(cur, "order_events", oid) == 0
        assert _count(cur, "payments", oid) == 0
        assert _count(cur, "orders", oid, "id") == 0
    finally:
        cur.close()


def test_deleted_order_absent_from_orders_query(db_connection, order_fixture, test_settings):
    oid = order_fixture["order_id"]
    number = order_fixture["order_number"]
    headers = _auth(order_fixture["admin_token"])
    assert client.delete(f"/api/v1/admin/orders/{oid}", headers=headers).status_code == 200

    resp = client.get(f"/api/v1/admin/orders?q={number}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []


def test_non_admin_rejected(db_connection, order_fixture, test_settings):
    oid = order_fixture["order_id"]
    resp = client.delete(
        f"/api/v1/admin/orders/{oid}", headers=_auth(order_fixture["customer_token"])
    )
    assert resp.status_code == 403
    cur = db_connection.cursor()
    try:
        assert _count(cur, "orders", oid, "id") == 1
    finally:
        cur.close()


def test_unauthenticated_rejected(db_connection, order_fixture, test_settings):
    oid = order_fixture["order_id"]
    resp = client.delete(f"/api/v1/admin/orders/{oid}")
    assert resp.status_code == 401
    cur = db_connection.cursor()
    try:
        assert _count(cur, "orders", oid, "id") == 1
    finally:
        cur.close()


def test_delete_missing_order_returns_404_and_double_delete_safe(order_fixture, test_settings):
    headers = _auth(order_fixture["admin_token"])
    resp = client.delete("/api/v1/admin/orders/999999", headers=headers)
    assert resp.status_code == 404
    assert "не знайдено" in resp.json()["detail"]

    oid = order_fixture["order_id"]
    assert client.delete(f"/api/v1/admin/orders/{oid}", headers=headers).status_code == 200
    # Repeat delete of the same order is safe → 404, not an error.
    assert client.delete(f"/api/v1/admin/orders/{oid}", headers=headers).status_code == 404


def test_failed_deletion_rolls_back(db_connection, order_fixture, test_settings):
    """An FK failure on the final DELETE must roll back ALL prior deletes."""
    oid = order_fixture["order_id"]
    cur = db_connection.cursor()
    try:
        cur.execute(f"INSERT INTO {BLOCKER_TABLE} (order_id) VALUES (%s)", (oid,))
        db_connection.commit()
    finally:
        cur.close()

    resp = client_no_raise.delete(
        f"/api/v1/admin/orders/{oid}", headers=_auth(order_fixture["admin_token"])
    )
    assert resp.status_code >= 500  # FK violation blocks the delete

    cur = db_connection.cursor()
    try:
        # Nothing was partially deleted: order + all dependents still exist.
        assert _count(cur, "orders", oid, "id") == 1
        assert _count(cur, "order_items", oid) == 1
        assert _count(cur, "order_events", oid) == 1
        assert _count(cur, "payments", oid) == 1
    finally:
        cur.close()