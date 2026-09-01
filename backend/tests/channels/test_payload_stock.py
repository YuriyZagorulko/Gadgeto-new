"""Tests for Rozetka payload stock_quantity mapping.

Verifies the business rule:
  in_stock     → stock_quantity = 10
  out_of_stock → stock_quantity = 0
"""

from app.channels.rozetka.payload import (
    ROZETKA_IN_STOCK_QUANTITY,
    build_create_payload,
)

ATTR_SPECS = {}


def _transformed(**overrides):
    base = {
        "title": "Test Product",
        "description": "Test description",
        "price": 2400,
        "export_price": 2400,
        "currency": "UAH",
        "stock_qty": 0,
        "stock_status": "in_stock",
        "sku": "DCL-R80 Plus (Black)",
        "brand": "Bloody",
        "category": {"external_id": "80172", "name": "Комп'ютерні миші"},
        "attributes": [],
        "images": [{"url": "https://example.com/img.jpg", "alt": "", "sort_order": 0, "is_primary": True}],
    }
    base.update(overrides)
    return base


def test_create_payload_in_stock_uses_10():
    """in_stock product → stock_quantity=10."""
    payload, _ = build_create_payload(_transformed(stock_status="in_stock"), ATTR_SPECS)
    assert payload["stock_quantity"] == ROZETKA_IN_STOCK_QUANTITY
    assert payload["stock_quantity"] == 10
    assert payload["available"] is True


def test_create_payload_out_of_stock_uses_0():
    """out_of_stock product → stock_quantity=0."""
    payload, _ = build_create_payload(_transformed(stock_status="out_of_stock"), ATTR_SPECS)
    assert payload["stock_quantity"] == 0
    assert payload["available"] is False


def test_create_payload_keeps_existing_stock_qty_for_in_stock():
    """in_stock with a real positive stock_qty keeps that quantity."""
    payload, _ = build_create_payload(
        _transformed(stock_status="in_stock", stock_qty=25), ATTR_SPECS)
    assert payload["stock_quantity"] == 25


def test_create_payload_missing_stock_status_defaults_zero():
    """Missing stock_status (unknown) → stock_quantity=0."""
    payload, _ = build_create_payload(_transformed(stock_status=""), ATTR_SPECS)
    assert payload["stock_quantity"] == 0
    assert payload["available"] is False


def test_create_payload_price_pipeline_untouched():
    """export_price flows through unchanged; price uses export_price."""
    payload, _ = build_create_payload(
        _transformed(stock_status="in_stock", price=2400, export_price=2400),
        ATTR_SPECS)
    assert payload["price"] == 2400
    assert payload["stock_quantity"] == 10


# ── UPDATE (PUT /items/mass-update) payload ────────────────────────────


def _update_stock_quantity(stock_status, stock_qty, product_status="PUBLISHED"):
    """Mirror export_run.rozetka_stock_quantity for the transformed dict."""
    from app.channels.export_run import rozetka_stock_quantity
    return rozetka_stock_quantity({"stock_status": stock_status,
                                   "stock_qty": stock_qty,
                                   "product_status": product_status})


def test_update_stock_in_stock_uses_10():
    """update_price_stock for in_stock product sends stock_quantity=10."""
    from unittest.mock import MagicMock
    from app.channels.base import RozetkaAdapter

    api = MagicMock()
    adapter = RozetkaAdapter(api_client=api)
    adapter.update_price_stock({
        "sku": "DCL-R80 Plus (Black)",
        "external_ref": {"rz_item_id": 123},
        "price": 2400.0,
        "stock_quantity": _update_stock_quantity("in_stock", 0),
    })
    items = api.mass_update_price_stock.call_args[0][0]
    assert items[0]["item_rz_id"] == 123
    assert items[0]["price"] == 2400
    assert items[0]["stock_quantity"] == 10


def test_update_stock_out_of_stock_uses_0():
    """update_price_stock for out_of_stock product sends stock_quantity=0."""
    from unittest.mock import MagicMock
    from app.channels.base import RozetkaAdapter

    api = MagicMock()
    adapter = RozetkaAdapter(api_client=api)
    adapter.update_price_stock({
        "sku": "DCL-R80 Plus (Black)",
        "external_ref": {"rz_item_id": 123},
        "price": 2400.0,
        "stock_quantity": _update_stock_quantity("out_of_stock", 0),
    })
    items = api.mass_update_price_stock.call_args[0][0]
    assert items[0]["item_rz_id"] == 123
    assert items[0]["price"] == 2400
    assert items[0]["stock_quantity"] == 0


def test_update_stock_lifecycle_10_0_10():
    """Lifecycle: in_stock → 10, out_of_stock → 0, in_stock → 10."""
    assert _update_stock_quantity("in_stock", 0) == 10
    assert _update_stock_quantity("out_of_stock", 0) == 0
    assert _update_stock_quantity("in_stock", 0) == 10


def test_update_stock_preserves_positive_exact_qty():
    """A supplier-provided exact positive stock_qty is preserved."""
    assert _update_stock_quantity("in_stock", 25) == 25
    assert _update_stock_quantity("in_stock", 0) == 10


def test_update_stock_hidden_product_returns_0():
    """A HIDDEN product (e.g. after supplier removal) gets stock_quantity=0
    regardless of stock_status, so its existing Rozetka listing is deactivated."""
    assert _update_stock_quantity("in_stock", 0, product_status="HIDDEN") == 0
    assert _update_stock_quantity("in_stock", 25, product_status="HIDDEN") == 0
    assert _update_stock_quantity("out_of_stock", 0, product_status="HIDDEN") == 0
    assert _update_stock_quantity("in_stock", 10, product_status="DRAFT") == 0
    assert _update_stock_quantity("in_stock", 10, product_status="ARCHIVED") == 0