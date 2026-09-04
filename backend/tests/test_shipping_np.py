"""Unit tests for the Nova Poshta shipping endpoints (HTTP fully mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx

from app.core.config import settings
from app.shipping import np_api


def _np_response(data=None, success=True, errors=None, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = {
        "success": success, "data": data or [], "errors": errors or [],
    }
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp)
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _patch_async_client(monkeypatch, response=None, post_exception=None):
    """Replace httpx.AsyncClient with a mock; returns the fake client."""
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    if post_exception is not None:
        client.post.side_effect = post_exception
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=ctx)
    monkeypatch.setattr(np_api.httpx, "AsyncClient", factory)
    return client, factory


import pytest


@pytest.fixture
def np_key(monkeypatch):
    """Dummy API key — .env is not loaded from backend/, key is empty in tests."""
    monkeypatch.setattr(settings, "NOVAPOSHTA_API_KEY", "test-key")


async def test_cities_success_mapping(np_key, monkeypatch):
    resp = _np_response(data=[{
        "Ref": "city-ref-1", "Description": "Київ",
        "AreaDescription": "Київська область",
        "RegionDescription": "Київський район",
    }])
    client, factory = _patch_async_client(monkeypatch, resp)

    out = await np_api.get_cities(search="Київ")

    assert out["error"] == ""
    assert out["items"] == [{
        "ref": "city-ref-1", "name": "Київ",
        "area": "Київська область", "region": "Київський район",
    }]
    payload = client.post.call_args.kwargs["json"]
    assert payload["modelName"] == "Address"
    assert payload["calledMethod"] == "getCities"
    assert payload["apiKey"] == "test-key"
    assert payload["methodProperties"]["FindByString"] == "Київ"
    assert payload["methodProperties"]["Limit"] == "50"


async def test_cities_without_api_key_never_calls_http(monkeypatch):
    monkeypatch.setattr(settings, "NOVAPOSHTA_API_KEY", "")
    client, factory = _patch_async_client(monkeypatch)

    out = await np_api.get_cities(search="Київ")

    assert out["items"] == []
    assert "not configured" in out["error"]
    factory.assert_not_called()


async def test_np_error_envelope_returns_error(np_key, monkeypatch):
    resp = _np_response(success=False, errors=["City not found"])
    _patch_async_client(monkeypatch, resp)

    out = await np_api.get_cities(search="незнайоме")

    assert out["items"] == []
    assert "City not found" in out["error"]


async def test_timeout_returns_error(np_key, monkeypatch):
    _patch_async_client(
        monkeypatch, post_exception=httpx.TimeoutException("timed out"))

    out = await np_api.get_cities(search="Київ")

    assert out["items"] == []
    assert "timed out" in out["error"]


async def test_http_error_returns_error(np_key, monkeypatch):
    resp = _np_response(status_code=500)
    _patch_async_client(monkeypatch, resp)

    out = await np_api.get_cities(search="Київ")

    assert out["items"] == []
    assert out["error"]


async def test_branches_requires_city_ref(monkeypatch):
    client, factory = _patch_async_client(monkeypatch)

    out = await np_api.get_branches(city_ref="")

    assert out == {"items": [], "error": ""}
    factory.assert_not_called()


async def test_branches_success_mapping(np_key, monkeypatch):
    resp = _np_response(data=[{
        "Ref": "wh-ref-1", "Number": "1",
        "Description": "Відділення №1 (до 30 кг)",
        "ShortAddress": "вул. Хрещатик, 1", "Phone": "0800500609",
        "TotalMaxWeightAllowed": "30",
    }])
    client, _ = _patch_async_client(monkeypatch, resp)

    out = await np_api.get_branches(city_ref="city-ref-1", search="Хрещатик")

    assert out["error"] == ""
    assert out["items"][0] == {
        "ref": "wh-ref-1", "number": "1",
        "address": "Відділення №1 (до 30 кг)",
        "short_address": "вул. Хрещатик, 1", "phone": "0800500609",
        "max_weight": "30",
    }
    payload = client.post.call_args.kwargs["json"]
    assert payload["calledMethod"] == "getWarehouses"
    assert payload["methodProperties"]["CityRef"] == "city-ref-1"
    assert payload["methodProperties"]["FindByString"] == "Хрещатик"


async def test_limit_and_page_clamped(np_key, monkeypatch):
    resp = _np_response(data=[])
    client, _ = _patch_async_client(monkeypatch, resp)

    await np_api.get_cities(limit=9999, page=0)

    props = client.post.call_args.kwargs["json"]["methodProperties"]
    assert props["Limit"] == str(np_api._MAX_LIMIT)
    assert props["Page"] == "1"


async def test_streets_requires_city_ref(monkeypatch):
    client, factory = _patch_async_client(monkeypatch)

    out = await np_api.get_streets(city_ref="")

    assert out == {"items": [], "error": ""}
    factory.assert_not_called()


async def test_streets_success_mapping(np_key, monkeypatch):
    resp = _np_response(data=[{
        "Ref": "st-ref-1", "Description": "Хрещатик", "StreetsType": "вулиця",
    }])
    client, _ = _patch_async_client(monkeypatch, resp)

    out = await np_api.get_streets(city_ref="city-ref-1", search="Хрещатик")

    assert out["error"] == ""
    assert out["items"] == [{
        "ref": "st-ref-1", "name": "Хрещатик", "street_type": "вулиця",
    }]
    payload = client.post.call_args.kwargs["json"]
    assert payload["modelName"] == "Address"
    assert payload["calledMethod"] == "getStreet"
    assert payload["methodProperties"]["CityRef"] == "city-ref-1"
    assert payload["methodProperties"]["FindByString"] == "Хрещатик"
    assert payload["methodProperties"]["Limit"] == "50"
