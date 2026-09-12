"""Tests for order traffic-source attribution (checkout flow).

Covers:
- attribution fields accepted by POST /checkout and persisted with the order
- missing attribution does not break order creation (NULL columns)
- purchase/order IDs remain correct (number + order_id returned)
- attribution does not overwrite existing order data (buyer/totals intact)
- overlong values are truncated to column limits

NOTE: the checkout endpoint opens its own DB connection (TestClient), so
fixtures must COMMIT to be visible across connections. Each test uses a
unique session_token/email/slug; the db_connection autouse-adjacent
teardown rolls back only same-connection work, so fixtures clean up their
own rows explicitly via `db_connection` where practical. Leftover-row risk
is mitigated by unique values per test.
"""
import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def checkout_setup(db_connection):
    """Create product+user+cart with COMMIT (visible to the TestClient connection)."""
    cur = db_connection.cursor()
    try:
        slug = _unique("attr-product")
        email = _unique("attr") + "@example.com"
        session_token = _unique("attr-cart")
        token = _unique("attr-token")
        cur.execute(
            "INSERT INTO products (name, slug, price, currency, stock_qty, status, is_active, is_visible,"
            " created_at, updated_at) "
            "VALUES ('Attr Product', %s, 15000, 'UAH', 10, 'PUBLISHED', true, true, NOW(), NOW()) RETURNING id",
            (slug,),
        )
        product_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (email, password_hash, full_name, role, status, created_at, updated_at) "
            "VALUES (%s, 'hash', 'Attr User', 'CUSTOMER', 'ACTIVE', NOW(), NOW()) RETURNING id",
            (email,),
        )
        user_id = cur.fetchone()[0]
        th = hashlib.sha256(token.encode()).hexdigest()
        cur.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at, created_at, updated_at) "
            "VALUES (%s, %s, NOW() + INTERVAL '1 day', NOW(), NOW())",
            (user_id, th),
        )
        cur.execute(
            "INSERT INTO carts (session_token, created_at, updated_at) "
            "VALUES (%s, NOW(), NOW()) RETURNING id",
            (session_token,),
        )
        cart_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO cart_items (cart_id, product_id, qty, price_at_addition, created_at, updated_at) "
            "VALUES (%s, %s, 2, 15000, NOW(), NOW())",
            (cart_id, product_id),
        )
        db_connection.commit()
        yield {"session_token": session_token, "token": token}
        # Best-effort cleanup of cross-connection rows.
        try:
            cur.execute("DELETE FROM cart_items WHERE cart_id = %s", (cart_id,))
            cur.execute("DELETE FROM carts WHERE id = %s", (cart_id,))
            cur.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE email='ivan@example.com')")
            cur.execute("DELETE FROM orders WHERE email='ivan@example.com'")
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
            db_connection.commit()
        except Exception:
            db_connection.rollback()
    finally:
        cur.close()


def _checkout_payload(session_token, token, attribution=None):
    payload = {
        "session_token": session_token,
        "first_name": "Ivan",
        "last_name": "Petrenko",
        "phone": "+380501234567",
        "email": "ivan@example.com",
        "city_ref": "city-ref",
        "city_name": "Kyiv",
        "delivery_method": "warehouse",
        "payment_method": "cod",
        "auth_token": token,
    }
    if attribution:
        payload.update(attribution)
    return payload


FULL_ATTRIBUTION = {
    "first_source": "google",
    "first_medium": "organic",
    "first_campaign": "",
    "first_term": "",
    "first_content": "",
    "first_landing_page": "/product/attr",
    "first_gclid": "",
    "last_source": "google",
    "last_medium": "cpc",
    "last_campaign": "summer_sale",
    "last_term": "phone",
    "last_content": "ad1",
    "last_landing_page": "/product/attr?utm_source=google&utm_medium=cpc&utm_campaign=summer_sale",
    "last_gclid": "TeSter-123",
}


def test_checkout_persists_attribution(db_connection, checkout_setup, test_settings):
    resp = client.post(
        "/api/v1/checkout",
        json=_checkout_payload(checkout_setup["session_token"], checkout_setup["token"], FULL_ATTRIBUTION),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["order_id"] and data["number"].startswith("GDT-")

    cur = db_connection.cursor()
    try:
        cur.execute(
            "SELECT buyer_name, email, total_amount, subtotal_amount,"
            " first_source, first_medium, last_source, last_medium,"
            " last_campaign, last_term, last_content, last_gclid,"
            " first_landing_page, last_landing_page"
            " FROM orders WHERE id = %s",
            (data["order_id"],),
        )
        row = cur.fetchone()
        assert row[0] == "Ivan Petrenko"
        assert row[1] == "ivan@example.com"
        assert row[2] == 30000
        assert row[3] == 30000
        assert row[4] == "google"
        assert row[5] == "organic"
        assert row[6] == "google"
        assert row[7] == "cpc"
        assert row[8] == "summer_sale"
        assert row[9] == "phone"
        assert row[10] == "ad1"
        assert row[11] == "TeSter-123"
        assert row[12] == "/product/attr"
        assert "utm_campaign=summer_sale" in (row[13] or "")
    finally:
        cur.close()


def test_checkout_without_attribution_succeeds(db_connection, checkout_setup, test_settings):
    resp = client.post(
        "/api/v1/checkout",
        json=_checkout_payload(checkout_setup["session_token"], checkout_setup["token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    cur = db_connection.cursor()
    try:
        cur.execute(
            "SELECT first_source, last_source, last_gclid, buyer_name, total_amount"
            " FROM orders WHERE id = %s",
            (data["order_id"],),
        )
        row = cur.fetchone()
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None
        assert row[3] == "Ivan Petrenko"
        assert row[4] == 30000
    finally:
        cur.close()


def test_attribution_truncated_to_column_limits(db_connection, checkout_setup, test_settings):
    long_campaign = "c" * 400
    long_landing = "l" * 700
    attr = dict(FULL_ATTRIBUTION, last_campaign=long_campaign, last_landing_page=long_landing)
    resp = client.post(
        "/api/v1/checkout",
        json=_checkout_payload(checkout_setup["session_token"], checkout_setup["token"], attr),
    )
    assert resp.status_code == 200, resp.text
    cur = db_connection.cursor()
    try:
        cur.execute(
            "SELECT last_campaign, last_landing_page FROM orders WHERE id = %s",
            (resp.json()["order_id"],),
        )
        row = cur.fetchone()
        assert len(row[0]) == 255
        assert len(row[1]) == 500
    finally:
        cur.close()
