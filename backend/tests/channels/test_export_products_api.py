"""Tests for the Rozetka Product Listing and Export Preview APIs.

Covers:
  1. GET /export/channels/{code}/products — listing, pagination, filters
  2. POST /export/channels/{code}/export/preview — preview, selection, validation

DB access is mocked via FakeConn/FakeCursor (same pattern as
*_taxonomy_api tests).
"""

from unittest.mock import patch

import psycopg2.extras
import pytest
from starlette.testclient import TestClient

from app.api.admin.deps import require_admin
from app.main import app

RealDictRow = psycopg2.extras.RealDictRow


# ── Fake database helpers (matching existing test pattern) ─────────────────


def _product_row(**kw):
    """Convenience: product row with sensible defaults."""
    row = {
        "id": 1, "sku": "SKU-001", "name": "Test Product",
        "price": 1000.0, "currency": "UAH", "stock_qty": 10,
        "stock_status": "in_stock", "product_status": "PUBLISHED",
        "category_name": "Ноутбуки", "category_id": 5,
        "listing_id": 1, "publication_status": "ready",
        "sync_status": "idle", "external_id": None,
        "last_error_type": None, "last_error_message": None,
        "last_synced_at": None,
        "has_mapping": True,
    }
    row.update(kw)
    return row


class FakeCursor:
    """A cursor that dispatches based on SQL shape."""

    def __init__(self, rows=None):
        self.queries = []
        self.params = []
        self._pending = None
        self._rows = rows or []

    def execute(self, sql, params=()):
        self.queries.append(sql)
        self.params.append(params)
        self._pending = self._produce(sql, params)

    def _produce(self, sql, params=()):
        low = sql.lower().strip()
        # Channel lookup — ONLY return channel for "rozetka"
        if "from channels" in low and "where code" in low:
            code = params[-1] if params else None
            if code == "rozetka":
                return [RealDictRow({
                    "id": 1, "code": "rozetka", "name": "Rozetka",
                    "is_enabled": False, "created_at": None, "updated_at": None,
                })]
            return []
        # Count query
        if low.startswith("select count"):
            if self._rows:
                return [RealDictRow({"c": len(self._rows)})]
            return [RealDictRow({"c": 0})]
        # Data query or product ID resolution
        return self._rows or []

    def fetchone(self):
        if not self._pending:
            return None
        return self._pending[0] if self._pending else None

    def fetchall(self):
        return self._pending or []

    def close(self):
        pass


class FakeConn:
    autocommit = True

    def __init__(self, cursor_obj=None):
        self.cursor_obj = cursor_obj or FakeCursor()

    def cursor(self, cursor_factory=None):
        return self.cursor_obj

    def close(self):
        pass


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    def _fake_admin():
        return {"id": 1, "email": "admin@test.com", "role": "admin"}
    app.dependency_overrides[require_admin] = _fake_admin
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# =====================================================================
# PRODUCT LISTING TESTS
# =====================================================================


def test_products_pagination(client):
    """Returns paginated results with correct count."""
    rows = [_product_row(id=i) for i in range(1, 11)]
    conn = FakeConn(FakeCursor(rows))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"page": 1, "per_page": 5})
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "per_page" in body
    assert body["page"] == 1
    assert body["per_page"] == 5
    assert body["total"] == 10


def test_products_search_by_sku(client):
    """Search q parameter filters by SKU."""
    rows = [_product_row(id=1, sku="ABC-123")]
    conn = FakeConn(FakeCursor(rows))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"q": "ABC-123"})
    assert res.status_code == 200


def test_products_search_by_name(client):
    """Search q parameter filters by product name."""
    rows = [_product_row(id=42, name="Ноутбук Lenovo")]
    conn = FakeConn(FakeCursor(rows))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"q": "Lenovo"})
    assert res.status_code == 200


def test_products_category_filter(client):
    """Filter by internal category id."""
    conn = FakeConn(FakeCursor([_product_row(category_id=5)]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"category_id": 5})
    assert res.status_code == 200


def test_products_publication_status_filter(client):
    """Filter by publication status."""
    conn = FakeConn(FakeCursor([_product_row(publication_status="published")]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"publication_status": "published"})
    assert res.status_code == 200


def test_products_sync_status_filter(client):
    """Filter by sync status."""
    conn = FakeConn(FakeCursor([_product_row(sync_status="error")]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"sync_status": "error"})
    assert res.status_code == 200


def test_products_has_mapping_filter(client):
    """Filter by has_mapping flag."""
    conn = FakeConn(FakeCursor([_product_row(has_mapping=True)]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"has_mapping": "true"})
    assert res.status_code == 200


def test_products_stock_status_filter(client):
    """Filter by stock_status."""
    conn = FakeConn(FakeCursor([_product_row(stock_status="in_stock")]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"stock_status": "in_stock"})
    assert res.status_code == 200


def test_products_per_page_max_enforced(client):
    """per_page above 500 must be rejected."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"per_page": 999})
    assert res.status_code == 422


def test_products_empty_result(client):
    """Empty result returns zero total and empty items."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products",
                         params={"q": "zzz_nonexistent_zzz"})
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_products_unauthorized(client):
    """Non-admin user is rejected."""
    app.dependency_overrides[require_admin] = lambda: None
    # Force a 403 by making require_admin raise
    from fastapi import HTTPException
    async def _deny():
        raise HTTPException(status_code=403, detail="Not authenticated")
    app.dependency_overrides[require_admin] = _deny
    res = client.get("/api/v1/admin/export/channels/rozetka/products")
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_products_unknown_channel(client):
    """Unknown channel code returns 404."""
    # Directly test _resolve_channel behavior
    from app.api.admin.export import _resolve_channel
    from fastapi import HTTPException
    import psycopg2
    conn = psycopg2.connect(app.core.db_connect.DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        _resolve_channel(cur, "unknown_channel_that_does_not_exist")
        assert False, "Should have raised 404"
    except HTTPException as e:
        assert e.status_code == 404
    finally:
        conn.close()


def test_products_response_shape(client):
    """Product item has expected fields."""
    rows = [_product_row(id=7, sku="TST-007", name="Test Item 7",
                         price=500.0, stock_qty=3,
                         stock_status="in_stock",
                         product_status="PUBLISHED",
                         category_name="Монітори",
                         has_mapping=True,
                         publication_status="ready",
                         sync_status="idle")]
    conn = FakeConn(FakeCursor(rows))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.get("/api/v1/admin/export/channels/rozetka/products")
    assert res.status_code == 200
    item = res.json()["items"][0]
    assert item["id"] == 7
    assert item["sku"] == "TST-007"
    assert item["name"] == "Test Item 7"
    assert item["price"] == 500.0
    assert item["stock_qty"] == 3
    assert item["has_mapping"] is True
    assert item["publication_status"] == "ready"
    assert "validation_summary" in item


# =====================================================================
# EXPORT PREVIEW TESTS
# =====================================================================


def test_preview_by_product_ids(client):
    """Preview accepts explicit product IDs."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)), \
         patch("app.channels.mapping_resolver.ChannelMappingResolver") as MockResolver, \
         patch("app.channels.validation.validate_product") as MockValidate, \
         patch("app.channels.validation._load_product_data") as MockLoad, \
         patch("app.channels.validation._build_transform_payload") as MockBuild:

        MockResolver.return_value.resolve_category.return_value = {
            "external_category_id": "1001",
            "external_category_name": "Ноутбуки",
        }
        MockResolver.return_value.resolve_attribute.return_value = None
        MockLoad.return_value = {
            "id": 1, "sku": "TST-1", "name": "Test",
            "price": 100, "currency": "UAH",
            "stock_qty": 5, "stock_status": "in_stock",
            "status": "PUBLISHED", "description": "desc",
            "brand": {"id": 1, "name": "Brand"},
            "categories": [{"category_id": 5,
                            "category_name": "Ноутбуки"}],
            "attributes": [], "images": [], "brand_id": 1,
        }
        MockValidate.return_value = {
            "ready": True, "issues": [],
        }

        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={"selection": {"product_ids": [1, 2]}},
        )
    assert res.status_code == 200
    body = res.json()
    assert "products" in body
    assert "summary" in body
    assert body["summary"]["total"] == 2


def test_preview_all_matching_filters(client):
    """Preview accepts all_matching_filters selection."""
    row = RealDictRow({"id": 42})
    cursor = FakeCursor([row])
    conn = FakeConn(cursor)
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)), \
         patch("app.channels.mapping_resolver.ChannelMappingResolver") as MockResolver, \
         patch("app.channels.validation.validate_product") as MockValidate, \
         patch("app.channels.validation._load_product_data") as MockLoad, \
         patch("app.channels.validation._build_transform_payload") as MockBuild:

        MockResolver.return_value.resolve_category.return_value = {
            "external_category_id": "1001",
            "external_category_name": "Ноутбуки",
        }
        MockResolver.return_value.resolve_attribute.return_value = None
        MockLoad.return_value = {
            "id": 42, "sku": "ALL-1", "name": "All Match",
            "price": 100, "currency": "UAH",
            "stock_qty": 5, "stock_status": "in_stock",
            "status": "PUBLISHED", "description": "desc",
            "brand": {"id": 1, "name": "Brand"},
            "categories": [{"category_id": 5,
                            "category_name": "Ноутбуки"}],
            "attributes": [], "images": [], "brand_id": 1,
        }
        MockValidate.return_value = {
            "ready": True, "issues": [],
        }

        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={
                "selection": {
                    "all_matching_filters": True,
                    "filters": {"q": "laptop",
                                "publication_status": "ready"},
                },
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert len(body["products"]) >= 1


def test_preview_with_exclude_ids(client):
    """Preview excludes product IDs from all_matching_filters."""
    row = RealDictRow({"id": 1})
    cursor = FakeCursor([row])
    conn = FakeConn(cursor)
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)), \
         patch("app.channels.validation.validate_product") as MockV, \
         patch("app.channels.mapping_resolver.ChannelMappingResolver") as MockR, \
         patch("app.channels.validation._load_product_data") as MockL, \
         patch("app.channels.validation._build_transform_payload") as MockB:
        MockR.return_value.resolve_category.return_value = {
            "external_category_id": "1001",
            "external_category_name": "Cat",
        }
        MockR.return_value.resolve_attribute.return_value = None
        MockL.return_value = {
            "id": 1, "sku": "X", "name": "X",
            "price": 10, "currency": "UAH",
            "stock_qty": 1, "stock_status": "in_stock",
            "status": "PUBLISHED", "description": "x",
            "brand": None,
            "categories": [{"category_id": 5,
                            "category_name": "Cat"}],
            "attributes": [], "images": [], "brand_id": None,
        }
        MockV.return_value = {"ready": True, "issues": []}

        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={
                "selection": {
                    "all_matching_filters": True,
                    "filters": {},
                    "exclude_ids": [99],
                },
            },
        )
    assert res.status_code == 200


def test_preview_empty_selection_rejected(client):
    """Empty product_ids with all_matching_filters=False is rejected."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={"selection": {"all_matching_filters": False,
                                "product_ids": []}},
        )
    assert res.status_code == 422


def test_preview_missing_product_ids_rejected(client):
    """Missing product_ids field raises 422."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)):
        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={"selection": {"all_matching_filters": False}},
        )
    assert res.status_code == 422


def test_preview_limit_exceeded(client):
    """More than 50 products is rejected."""
    rows = [RealDictRow({"id": i}) for i in range(51)]
    cursor = FakeCursor(rows)
    conn = FakeConn(cursor)
    with patch("app.api.admin.export.db",
               return_value=(conn, conn.cursor_obj)):
        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={
                "selection": {
                    "all_matching_filters": True,
                    "filters": {},
                },
            },
        )
    assert res.status_code == 422
    assert "50" in res.json()["detail"]


def test_preview_resolved_category(client):
    """Preview returns resolved Rozetka category info."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)), \
         patch("app.channels.mapping_resolver.ChannelMappingResolver") as MockR, \
         patch("app.channels.validation.validate_product") as MockV, \
         patch("app.channels.validation._load_product_data") as MockL, \
         patch("app.channels.validation._build_transform_payload") as MockB:

        MockR.return_value.resolve_category.return_value = {
            "external_category_id": "80004",
            "external_category_name": "Ноутбуки",
        }
        MockR.return_value.resolve_attribute.return_value = None
        MockL.return_value = {
            "id": 1, "sku": "T", "name": "T",
            "price": 100, "currency": "UAH",
            "stock_qty": 5, "stock_status": "in_stock",
            "status": "PUBLISHED", "description": "d",
            "brand": None,
            "categories": [{"category_id": 5,
                            "category_name": "Ноутбуки"}],
            "attributes": [], "images": [], "brand_id": None,
        }
        MockV.return_value = {"ready": True, "issues": []}

        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={"selection": {"product_ids": [1]}},
        )
    assert res.status_code == 200
    cat = res.json()["products"][0]["category"]
    assert cat["mapped"] is True
    assert cat["external_id"] == "80004"
    assert cat["external_name"] == "Ноутбуки"


def test_preview_validation_issues(client):
    """Preview returns validation issues from validate_product."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)), \
         patch("app.channels.mapping_resolver.ChannelMappingResolver") as MockR, \
         patch("app.channels.validation.validate_product") as MockV, \
         patch("app.channels.validation._load_product_data") as MockL, \
         patch("app.channels.validation._build_transform_payload") as MockB:

        MockR.return_value.resolve_category.return_value = None
        MockR.return_value.resolve_attribute.return_value = None
        MockL.return_value = {
            "id": 1, "sku": "ERR", "name": "Error Product",
            "price": 100, "currency": "UAH",
            "stock_qty": 5, "stock_status": "in_stock",
            "status": "PUBLISHED", "description": "d",
            "brand": None,
            "categories": [{"category_id": 5,
                            "category_name": "Ноутбуки"}],
            "attributes": [], "images": [], "brand_id": None,
        }
        MockV.return_value = {
            "ready": False,
            "issues": [
                {"code": "MISSING_CATEGORY_MAPPING",
                 "severity": "error",
                 "message": "Не знайдено відповідності категорії"},
            ],
        }

        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={"selection": {"product_ids": [1]}},
        )
    assert res.status_code == 200
    prod = res.json()["products"][0]
    assert prod["exportable"] is False
    assert len(prod["issues"]) == 1
    assert prod["issues"][0]["code"] == "MISSING_CATEGORY_MAPPING"


def test_preview_unknown_channel(client, db_connection):
    """Preview with unknown channel code returns 404.

    Uses the ``db_connection`` fixture so the test runs against the
    dedicated ``gadgeto_test`` database and the test transaction is
    rolled back at teardown.
    """
    from app.api.admin.export import _resolve_channel
    from fastapi import HTTPException

    cur = db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        _resolve_channel(cur, "unknown_channel_that_does_not_exist")
        assert False, "Should have raised 404"
    except HTTPException as e:
        assert e.status_code == 404


def test_preview_unauthorized(client):
    """Non-admin cannot access preview."""
    from fastapi import HTTPException
    async def _deny():
        raise HTTPException(status_code=403, detail="Not authenticated")
    app.dependency_overrides[require_admin] = _deny
    res = client.post(
        "/api/v1/admin/export/channels/rozetka/export/preview",
        json={"selection": {"product_ids": [1]}},
    )
    assert res.status_code == 403
    app.dependency_overrides.clear()


def test_preview_no_rozetka_call(client):
    """Preview NEVER calls Rozetka API."""
    conn = FakeConn(FakeCursor([]))
    with patch("app.api.admin.export.db", return_value=(conn, conn.cursor_obj)), \
         patch("app.channels.mapping_resolver.ChannelMappingResolver") as MockR, \
         patch("app.channels.validation.validate_product") as MockV, \
         patch("app.channels.validation._load_product_data") as MockL, \
         patch("app.channels.validation._build_transform_payload") as MockB, \
         patch("app.channels.rozetka.client.RozetkaAuthClient") as MockAuth:

        MockR.return_value.resolve_category.return_value = {
            "external_category_id": "1001",
            "external_category_name": "Cat",
        }
        MockR.return_value.resolve_attribute.return_value = None
        MockL.return_value = {
            "id": 1, "sku": "T", "name": "T",
            "price": 100, "currency": "UAH",
            "stock_qty": 5, "stock_status": "in_stock",
            "status": "PUBLISHED", "description": "d",
            "brand": None,
            "categories": [{"category_id": 5,
                            "category_name": "Cat"}],
            "attributes": [], "images": [], "brand_id": None,
        }
        MockV.return_value = {"ready": True, "issues": []}

        res = client.post(
            "/api/v1/admin/export/channels/rozetka/export/preview",
            json={"selection": {"product_ids": [1]}},
        )
    assert res.status_code == 200
    MockAuth.assert_not_called()
