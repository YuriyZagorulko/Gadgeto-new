"""Tests for the channel adapter interface."""

from unittest.mock import MagicMock

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
