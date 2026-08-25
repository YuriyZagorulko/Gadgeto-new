"""Tests for the channel adapter interface."""

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
        adapter = RozetkaAdapter()
        assert isinstance(adapter, RozetkaAdapter)

    def test_has_required_methods(self):
        """Adapter must have the 5 API-specific methods."""
        adapter = RozetkaAdapter()
        assert hasattr(adapter, "push_product")
        assert hasattr(adapter, "update_price_stock")
        assert hasattr(adapter, "unpublish")
        assert hasattr(adapter, "fetch_listing_status")
        assert hasattr(adapter, "classify_error")

    def test_does_not_require_generic_methods(self):
        """Adapter should NOT require methods that are generic services."""
        adapter = RozetkaAdapter()
        # These methods live in validation.py, transformer.py, taxonomy.py
        assert not hasattr(adapter, "validate_product")
        assert not hasattr(adapter, "transform_product")
        assert not hasattr(adapter, "refresh_taxonomy")

    def test_methods_raise_not_implemented(self):
        """All adapter methods should raise NotImplementedError (stub)."""
        adapter = RozetkaAdapter()
        import pytest
        with pytest.raises(NotImplementedError):
            adapter.push_product(None)
        with pytest.raises(NotImplementedError):
            adapter.update_price_stock(None)
        with pytest.raises(NotImplementedError):
            adapter.unpublish(None)
        with pytest.raises(NotImplementedError):
            adapter.fetch_listing_status(None)
        with pytest.raises(NotImplementedError):
            adapter.classify_error(Exception("test"))


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
