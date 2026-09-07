"""Prom.ua validation / transformation / taxonomy tests (unit — no DB)."""

import pytest

from app.channels.prom.prom_transformer import to_prom_payload
from app.channels.prom.prom_validation import (
    PROM_NOT_CONFIGURED,
    validate_prom_export,
)
from app.channels.prom.taxonomy import PromTaxonomyService
from app.channels.prom.client import PROM_NOT_CONFIGURED_MESSAGE, is_prom_configured
from app.channels.prom.errors import PromNotConfiguredError
from app.core.config import settings


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(settings, "PROM_ENABLED", False)


class TestPromValidation:
    def test_validate_returns_not_ready_when_not_configured(self, disabled):
        result = validate_prom_export(product_id=1)
        assert result["ready"] is False
        codes = {i["code"] for i in result["issues"]}
        assert PROM_NOT_CONFIGURED in codes
        assert any(
            PROM_NOT_CONFIGURED_MESSAGE in i["message"]
            for i in result["issues"]
        )

    def test_validate_never_hits_db(self, disabled, monkeypatch):
        # No DB call should even be attempted while not configured.
        import app.channels.prom.prom_validation as mod
        original = dict(mod.__dict__)
        monkeypatch.setattr(mod, "psycopg2", None)
        result = validate_prom_export(product_id=999)
        assert result["ready"] is False


class TestPromTransformer:
    def test_to_prom_payload_raises_when_not_configured(self, disabled):
        with pytest.raises(PromNotConfiguredError):
            to_prom_payload({"price": 1000, "title": "x"})

    def test_to_prom_payload_not_implemented_when_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", True)
        monkeypatch.setattr(settings, "PROM_API_URL", "https://my.prom.ua/api")
        monkeypatch.setattr(settings, "PROM_CREDENTIALS_JSON", '{"token": "x"}')
        with pytest.raises(NotImplementedError):
            to_prom_payload({"price": 1000, "title": "x"})


class TestPromTaxonomy:
    def test_refresh_raises_when_not_configured(self, disabled):
        svc = PromTaxonomyService()
        with pytest.raises(PromNotConfiguredError):
            svc.refresh(channel_id=123, channel_code="prom")

    def test_refresh_not_implemented_when_configured(self, monkeypatch):
        monkeypatch.setattr(settings, "PROM_ENABLED", True)
        monkeypatch.setattr(settings, "PROM_API_URL", "https://my.prom.ua/api")
        monkeypatch.setattr(settings, "PROM_CREDENTIALS_JSON", '{"token": "x"}')
        svc = PromTaxonomyService()
        with pytest.raises(NotImplementedError):
            svc.refresh(channel_id=123, channel_code="prom")


class TestPromPricingResolver:
    def test_no_rules_by_default(self):
        from app.services.prom_pricing import PromPricingResolver
        r = PromPricingResolver()
        assert r.has_rules is False
        assert r.calculate_export_price("cat-1", 10000, "Brand") is None