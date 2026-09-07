"""PromAdapter / adapter-registry tests (unit — no DB)."""

from unittest.mock import MagicMock

import pytest

from app.channels.base import ChannelAdapter, get_adapter
from app.channels.prom.api import PromAdapter
from app.channels.prom.errors import PromNotConfiguredError
from app.core.config import settings


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "PROM_ENABLED", True)
    monkeypatch.setattr(settings, "PROM_API_URL", "https://my.prom.ua/api")
    monkeypatch.setattr(settings, "PROM_CREDENTIALS_JSON", '{"token": "x"}')


class TestPromAdapter:
    def test_is_channel_adapter(self):
        assert issubclass(PromAdapter, ChannelAdapter)

    def test_has_channel_code(self):
        assert PromAdapter.channel_code == "prom"

    def test_constructor_requires_configuration(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", False)
        with pytest.raises(PromNotConfiguredError):
            PromAdapter()

    def test_can_build_skeleton_without_credentials(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", False)
        adapter = PromAdapter(require_configured=False)
        assert adapter.channel_code == "prom"

    def test_has_required_methods(self):
        adapter = PromAdapter(require_configured=False)
        for m in ("push_product", "update_price_stock", "unpublish",
                  "fetch_listing_status", "classify_error"):
            assert hasattr(adapter, m)

    def test_push_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", False)
        adapter = PromAdapter(require_configured=False)
        with pytest.raises(PromNotConfiguredError):
            adapter.push_product({"operation": "create", "payload": {}})

    def test_update_price_stock_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", False)
        adapter = PromAdapter(require_configured=False)
        with pytest.raises(PromNotConfiguredError):
            adapter.update_price_stock({})

    def test_unpublish_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", False)
        adapter = PromAdapter(require_configured=False)
        with pytest.raises(PromNotConfiguredError):
            adapter.unpublish({})

    def test_fetch_listing_status_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", False)
        adapter = PromAdapter(require_configured=False)
        with pytest.raises(PromNotConfiguredError):
            adapter.fetch_listing_status({})

    def test_classify_transient_timeout(self):
        adapter = PromAdapter(require_configured=False)
        etype, retryable = adapter.classify_error(TimeoutError("timeout"))
        assert etype == "timeout" and retryable is True

    def test_classify_auth(self):
        adapter = PromAdapter(require_configured=False)
        etype, retryable = adapter.classify_error(Exception("invalid credentials"))
        assert etype == "auth" and retryable is False

    def test_classify_config_error_defaults_invalid_data(self):
        # PromNotConfiguredError carries no transport signal yet → falls to the
        # generic non-retryable classification.
        adapter = PromAdapter(require_configured=False)
        etype, retryable = adapter.classify_error(PromNotConfiguredError())
        assert retryable is False
        assert isinstance(etype, str)

    def test_classify_default_invalid_data(self):
        adapter = PromAdapter(require_configured=False)
        etype, retryable = adapter.classify_error(ValueError("boom"))
        assert etype == "invalid_data" and retryable is False

    def test_push_not_implemented_when_configured(self, configured):
        adapter = PromAdapter()
        with pytest.raises(NotImplementedError):
            adapter.push_product({"operation": "create", "payload": {}})


class TestGetAdapter:
    def test_rozetka_resolved(self):
        from app.channels.base import RozetkaAdapter
        adapter = get_adapter("rozetka")
        assert isinstance(adapter, RozetkaAdapter)

    def test_prom_raises_lookup_error_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", False)
        with pytest.raises(LookupError):
            get_adapter("prom")

    def test_unknown_channel_raises(self):
        with pytest.raises(LookupError):
            get_adapter("nonexistent")
        with pytest.raises(LookupError):
            get_adapter("amazon")

    def test_prom_resolves_when_configured(self, configured):
        adapter = get_adapter("prom")
        assert isinstance(adapter, PromAdapter)
        assert adapter.channel_code == "prom"