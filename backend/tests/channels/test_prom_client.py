"""Prom.ua configuration / client tests (unit — no DB).

Verifies the "not configured / disabled" default behaviour and the future
API client boundary.  No real (or invented) HTTP requests are ever made.
"""

import pytest

from app.channels.prom.client import (
    PROM_NOT_CONFIGURED_MESSAGE,
    PromApiClient,
    is_prom_configured,
    is_prom_enabled,
)
from app.channels.prom.errors import PromNotConfiguredError
from app.core.config import settings


@pytest.fixture
def configured(monkeypatch):
    """Force the settings singleton to look fully configured."""
    monkeypatch.setattr(settings, "PROM_ENABLED", True)
    monkeypatch.setattr(settings, "PROM_API_URL", "https://my.prom.ua/api")
    monkeypatch.setattr(settings, "PROM_CREDENTIALS_JSON", '{"token": "x"}')


@pytest.mark.unit
def test_is_prom_enabled_default_false(monkeypatch):
    monkeypatch.setattr(settings, "PROM_ENABLED", False)
    assert is_prom_enabled() is False


@pytest.mark.unit
def test_is_prom_enabled_true_when_flag_set(monkeypatch):
    monkeypatch.setattr(settings, "PROM_ENABLED", True)
    assert is_prom_enabled() is True


@pytest.mark.unit
def test_is_prom_configured_requires_flag(configured, monkeypatch):
    monkeypatch.setattr(settings, "PROM_ENABLED", False)
    assert is_prom_configured() is False


@pytest.mark.unit
def test_is_prom_configured_requires_url(configured, monkeypatch):
    monkeypatch.setattr(settings, "PROM_API_URL", "")
    assert is_prom_configured() is False


@pytest.mark.unit
def test_is_prom_configured_requires_credentials(configured, monkeypatch):
    monkeypatch.setattr(settings, "PROM_CREDENTIALS_JSON", "")
    assert is_prom_configured() is False


@pytest.mark.unit
def test_is_prom_configured_ok(configured):
    assert is_prom_configured() is True


@pytest.mark.unit
def test_prom_api_client_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "PROM_ENABLED", False)
    with pytest.raises(PromNotConfiguredError, match="not configured"):
        PromApiClient()


@pytest.mark.unit
def test_prom_api_client_constructs_when_configured(configured):
    client = PromApiClient()
    assert client._base_url == "https://my.prom.ua/api"


@pytest.mark.unit
def test_prom_api_client_never_makes_requests_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "PROM_ENABLED", False)
    client = PromApiClient(require_configured=False)
    with pytest.raises(PromNotConfiguredError):
        client.authenticate()
    with pytest.raises(PromNotConfiguredError):
        client.push_product({"name": "x"})


@pytest.mark.unit
def test_prom_not_configured_error_is_lookup_error():
    # Registry lookups keep raising LookupError for not-yet-syncable channels.
    assert issubclass(PromNotConfiguredError, LookupError)
    assert PROM_NOT_CONFIGURED_MESSAGE == "Prom.ua integration is not configured."