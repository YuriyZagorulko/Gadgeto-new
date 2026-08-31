"""Tests for the channel adapter interface."""

from unittest.mock import MagicMock

import pytest

from app.channels.base import (
    ChannelAdapter,
    RozetkaAdapter,
    get_adapter,
)


class TestRozetkaAdapter:
    """Verify RozetkaAdapter is a valid ChannelAdapter subclass."""

    def test_is_channel_adapter(self):
        assert issubclass(RozetkaAdapter, ChannelAdapter)

    def test_has_channel_code(self):
        assert RozetkaAdapter.channel_code == "rozetka"

    def test_can_be_instantiated(self):
        from app.channels.rozetka.api import RozetkaApiClient
        adapter = RozetkaAdapter(api_client=MagicMock(spec=(["create_item",
                                                              "get_item_details"])))
        assert isinstance(adapter, RozetkaAdapter)

    def test_has_required_methods(self):
        """Adapter must have the 5 API-specific methods."""
        adapter = RozetkaAdapter(api_client=MagicMock())
        assert hasattr(adapter, "push_product")
        assert hasattr(adapter, "update_price_stock")
        assert hasattr(adapter, "unpublish")
        assert hasattr(adapter, "fetch_listing_status")
        assert hasattr(adapter, "classify_error")

    def test_does_not_require_generic_methods(self):
        """Adapter should NOT require methods that are generic services."""
        adapter = RozetkaAdapter(api_client=MagicMock())
        # These methods live in validation.py, transformer.py, taxonomy.py
        assert not hasattr(adapter, "validate_product")
        assert not hasattr(adapter, "transform_product")
        assert not hasattr(adapter, "refresh_taxonomy")

    def test_push_product_create(self):
        """push_product('create') calls POST /items-create/create and returns
        the marketplace item id."""
        api = MagicMock()
        api.create_item.return_value = {"item_id": 131415, "sync_source_id": 199}
        adapter = RozetkaAdapter(api_client=api)
        listing = {"operation": "create", "sku": "SKU-1", "payload": {"name": "x"}}
        result = adapter.push_product(listing)
        api.create_item.assert_called_once_with({"name": "x"})
        assert result["external_id"] == "131415"
        assert result["operation"] == "create"
        assert result["created"] is True

    def test_push_product_update(self):
        """push_product('update') calls mass-update-basic-data."""
        api = MagicMock()
        api.update_items_basic_data.return_value = {"items_updated": 1}
        adapter = RozetkaAdapter(api_client=api)
        listing = {
            "operation": "update", "sku": "SKU-1", "payload": {"name": "x"},
            "external_ref": {"item_id": 111, "rz_item_id": 222},
        }
        result = adapter.push_product(listing)
        api.update_items_basic_data.assert_called_once()
        assert result["external_id"] == "222"
        assert result["operation"] == "update"

    def test_update_price_stock(self):
        api = MagicMock()
        adapter = RozetkaAdapter(api_client=api)
        listings = {
            "sku": "SKU-1", "external_ref": {"rz_item_id": 222},
            "price": 1150.0, "stock_quantity": 7,
        }
        adapter.update_price_stock(listings)
        api.mass_update_price_stock.assert_called_once()

    def test_classify_transient_timeout(self):
        adapter = RozetkaAdapter(api_client=MagicMock())
        etype, retryable = adapter.classify_error(TimeoutError("timeout"))
        assert etype == "timeout" and retryable is True

    def test_classify_auth(self):
        adapter = RozetkaAdapter(api_client=MagicMock())
        from app.channels.rozetka.client import RozetkaAuthError
        etype, retryable = adapter.classify_error(
            RozetkaAuthError("Неправильний логін"))
        assert etype == "auth" and retryable is False

# ── resolve_external_ref lifecycle ─────────────────────────────────


    def test_resolve_external_ref_with_item_id_only(self):
        """When only item_id exists (no rz_item_id yet), returns both with
        rz_item_id=None, preventing duplicate creation."""
        api = MagicMock()
        api.get_item_details.side_effect = [
            None,  # rz_item_id=179074814 → 404
            {"item_id": 179074814, "rz_item_id": None},
        ]
        adapter = RozetkaAdapter(api_client=api)
        refs = adapter.resolve_external_ref({"external_id": "179074814"})
        assert refs == {"item_id": 179074814, "rz_item_id": None}
        assert api.get_item_details.call_count == 2
        assert api.get_item_details.call_args_list[0] == \
            ((), {"rz_item_id": 179074814})
        assert api.get_item_details.call_args_list[1] == \
            ((), {"item_id": 179074814})

    def test_resolve_external_ref_with_both_ids(self):
        """When rz_item_id becomes available, resolve_external_ref returns both."""
        api = MagicMock()
        api.get_item_details.return_value = {
            "item_id": 179074814, "rz_item_id": 123456789,
        }
        adapter = RozetkaAdapter(api_client=api)
        refs = adapter.resolve_external_ref({"external_id": "179074814"})
        assert refs == {"item_id": 179074814, "rz_item_id": 123456789}

    def test_resolve_external_ref_unknown_id(self):
        """When neither rz_item_id nor item_id resolves, returns empty dict."""
        api = MagicMock()
        api.get_item_details.return_value = None
        adapter = RozetkaAdapter(api_client=api)
        refs = adapter.resolve_external_ref({"external_id": "999999999"})
        assert refs == {}

    def test_resolve_external_ref_non_digit_id(self):
        """Non-numeric external_id returns empty dict without API call."""
        api = MagicMock()
        adapter = RozetkaAdapter(api_client=api)
        refs = adapter.resolve_external_ref({"external_id": "abc"})
        assert refs == {}
        api.get_item_details.assert_not_called()

    def test_resolve_external_ref_empty_listing(self):
        """Empty listing returns empty dict without API call."""
        api = MagicMock()
        adapter = RozetkaAdapter(api_client=api)
        refs = adapter.resolve_external_ref({})
        assert refs == {}
        api.get_item_details.assert_not_called()

    def test_resolve_external_ref_rz_item_id_first(self):
        """When stored external_id is an rz_item_id, the first lookup succeeds."""
        api = MagicMock()
        api.get_item_details.return_value = {
            "item_id": 100, "rz_item_id": 200,
        }
        adapter = RozetkaAdapter(api_client=api)
        refs = adapter.resolve_external_ref({"external_id": "200"})
        assert refs == {"item_id": 100, "rz_item_id": 200}
        api.get_item_details.assert_called_once_with(rz_item_id=200)

    def test_resolve_external_ref_rz_item_id_resolved_later(self):
        """Simulate a product that had only item_id, then rz_item_id
        becomes available after moderation. The stored external_id is
        still the item_id, but the API now returns rz_item_id."""
        api = MagicMock()
        api.get_item_details.side_effect = [
            None,  # rz_item_id=179074814 → 404 (not yet assigned)
            {"item_id": 179074814, "rz_item_id": 123456789},
        ]
        adapter = RozetkaAdapter(api_client=api)
        refs = adapter.resolve_external_ref({"external_id": "179074814"})
        assert refs == {"item_id": 179074814, "rz_item_id": 123456789}

    def test_update_price_stock_requires_rz_item_id(self):
        """update_price_stock raises ValueError when rz_item_id is missing."""
        api = MagicMock()
        adapter = RozetkaAdapter(api_client=api)
        with pytest.raises(ValueError, match="rz_item_id"):
            adapter.update_price_stock({
                "sku": "SKU-1",
                "external_ref": {"item_id": 111, "rz_item_id": None},
                "price": 1000.0, "stock_quantity": 5,
            })
        api.mass_update_price_stock.assert_not_called()

    def test_update_price_stock_sends_current_price(self):
        """update_price_stock sends the exact current price, not a stale one."""
        api = MagicMock()
        adapter = RozetkaAdapter(api_client=api)
        adapter.update_price_stock({
            "sku": "SKU-1",
            "external_ref": {"rz_item_id": 222},
            "price": 2000.0,
            "stock_quantity": 5,
        })
        api.mass_update_price_stock.assert_called_once()
        items = api.mass_update_price_stock.call_args[0][0]
        assert items[0]["item_rz_id"] == 222
        assert items[0]["price"] == 2000
        assert items[0]["stock_quantity"] == 5

class TestGetAdapter:
    """Verify the adapter registry/factory."""

    def test_rozetka_resolved(self):
        adapter = get_adapter("rozetka")
        assert isinstance(adapter, RozetkaAdapter)
        assert adapter.channel_code == "rozetka"

    def test_unknown_channel_raises(self):
        import pytest
        with pytest.raises(LookupError):
            get_adapter("nonexistent")
        with pytest.raises(LookupError):
            get_adapter("prom")
        with pytest.raises(LookupError):
            get_adapter("amazon")
