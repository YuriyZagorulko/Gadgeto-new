"""Regression tests for the EMPTY_PARAMS hard guard in export_run.

This file tests the hard guard that prevents products with empty params from
reaching the Rozetka API, regardless of validation results.
"""

from unittest.mock import MagicMock, patch

from app.channels.export_run import _push_product_ops


class _FakeCursor:
    """Minimal fake cursor for the hard guard tests."""
    def __init__(self):
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append(("execute", args, kwargs))

    def fetchone(self):
        return None


class _FakeAdapter:
    """Fake RozetkaAdapter that tracks push_product calls."""
    def __init__(self):
        self.push_product_calls = []
        self.update_price_stock_calls = []
        self._client = MagicMock()

    def push_product(self, listing):
        self.push_product_calls.append(listing)
        return {"external_id": "12345", "operation": listing.get("operation")}

    def update_price_stock(self, listing):
        self.update_price_stock_calls.append(listing)


def _make_ctx(adapter):
    return {
        "cur": _FakeCursor(),
        "channel_id": 1,
        "adapter": adapter,
        "classify": lambda exc: ("validation", False),
        "settings": {},
    }


def _make_transform(with_params=True, category_id="80099"):
    attrs = []
    if with_params:
        attrs.append({"external_attribute_id": "100", "value": "Test value"})
    return {
        "title": "Test Product",
        "description": "Test description",
        "category": {"external_id": category_id},
        "attributes": attrs,
        "export_price": 1000,
        "stock_status": "in_stock",
        "stock_qty": 10,
        "images": [{"url": "https://example.com/img.jpg"}],
    }


def test_update_with_params_allowed():
    """An existing product with non-empty params should reach Rozetka."""
    adapter = _FakeAdapter()
    result = _push_product_ops(
        _make_ctx(adapter), adapter, "update",
        _make_transform(with_params=True),
        {"100": {"name": "Test", "type": "text"}},
        {"rz_item_id": 12345}, False, {"id": 1},
        "abc", "def", 1000, 10, "TEST-SKU", {"product_id": 1},
    )
    assert result["status"] == "updated"
    assert len(adapter.push_product_calls) == 1


def test_update_with_empty_params_blocked():
    """An existing product with empty params must NOT call Rozetka."""
    adapter = _FakeAdapter()
    result = _push_product_ops(
        _make_ctx(adapter), adapter, "update",
        _make_transform(with_params=False),
        {}, {"rz_item_id": 12345}, False, {"id": 1},
        "abc", "def", 1000, 10, "TEST-SKU", {"product_id": 1},
    )
    assert result["status"] == "skipped"
    assert "EMPTY_PARAMS" in result.get("reason", "")
    assert len(adapter.push_product_calls) == 0


def test_create_with_params_allowed():
    """A new product with non-empty params should reach Rozetka."""
    adapter = _FakeAdapter()
    result = _push_product_ops(
        _make_ctx(adapter), adapter, "create",
        _make_transform(with_params=True),
        {"100": {"name": "Test", "type": "text"}},
        {}, False, {"id": 1},
        "abc", "def", 1000, 10, "TEST-SKU", {"product_id": 1},
    )
    assert result["status"] == "created"
    assert len(adapter.push_product_calls) == 1


def test_create_with_empty_params_blocked():
    """A new product with empty params must NOT call Rozetka."""
    adapter = _FakeAdapter()
    result = _push_product_ops(
        _make_ctx(adapter), adapter, "create",
        _make_transform(with_params=False),
        {}, {}, False, {"id": 1},
        "abc", "def", 1000, 10, "TEST-SKU", {"product_id": 1},
    )
    assert result["status"] == "skipped"
    assert "EMPTY_PARAMS" in result.get("reason", "")
    assert len(adapter.push_product_calls) == 0


def test_unmapped_select_attrs_blocked():
    """Select attrs without value ID produce empty params."""
    adapter = _FakeAdapter()
    transformed = {
        "title": "Test Product",
        "description": "Test description",
        "category": {"external_id": "80099"},
        "attributes": [{"external_attribute_id": "100"}],
        "export_price": 1000, "stock_status": "in_stock", "stock_qty": 10,
        "images": [{"url": "https://example.com/img.jpg"}],
    }
    attr_specs = {"100": {"name": "Select", "type": "combobox"}}
    result = _push_product_ops(
        _make_ctx(adapter), adapter, "update",
        transformed, attr_specs, {"rz_item_id": 12345},
        False, {"id": 1}, "abc", "def", 1000, 10, "TEST-SKU",
        {"product_id": 1},
    )
    assert result["status"] == "skipped"
    assert len(adapter.push_product_calls) == 0


def test_select_with_value_id_allowed():
    """Select attr with external_value_id should export."""
    adapter = _FakeAdapter()
    transformed = {
        "title": "Test Product",
        "description": "Test description",
        "category": {"external_id": "80099"},
        "attributes": [{"external_attribute_id": "100", "external_value_id": "200"}],
        "export_price": 1000, "stock_status": "in_stock", "stock_qty": 10,
        "images": [{"url": "https://example.com/img.jpg"}],
    }
    attr_specs = {"100": {"name": "Color", "type": "combobox"}}
    result = _push_product_ops(
        _make_ctx(adapter), adapter, "create",
        transformed, attr_specs, {}, False, {"id": 1},
        "abc", "def", 1000, 10, "TEST-SKU", {"product_id": 1},
    )
    assert result["status"] == "created"
    assert len(adapter.push_product_calls) == 1


def test_hard_guard_logs_category():
    """The hard guard should log the category ID."""
    adapter = _FakeAdapter()
    with patch("app.channels.export_run.logger") as mock_logger:
        _push_product_ops(
            _make_ctx(adapter), adapter, "create",
            _make_transform(with_params=False, category_id="80099"),
            {}, {}, False, {"id": 1},
            "abc", "def", 1000, 10, "TEST-SKU", {"product_id": 1},
        )
        mock_logger.warning.assert_called_once()
        # Log uses %s placeholders: format, arg1, arg2, arg3, arg4
        log_format = mock_logger.warning.call_args[0][0]
        log_args = mock_logger.warning.call_args[0][1:]
        # Category is the 3rd argument (index 2)
        assert log_format == "EMPTY_PARAMS hard guard triggered: product_id=%s sku=%s category=%s operation=%s — skipping API request"
        assert log_args[2] == "80099"


def test_status_format_consistent():
    """Hard guard returns same status format as normal path."""
    adapter = _FakeAdapter()
    result = _push_product_ops(
        _make_ctx(adapter), adapter, "create",
        _make_transform(with_params=False),
        {}, {}, False, {"id": 1},
        "abc", "def", 1000, 10, "TEST-SKU", {"product_id": 1},
    )
    assert "status" in result
    assert "reason" in result
    assert "operation" in result
    assert result["status"] == "skipped"
