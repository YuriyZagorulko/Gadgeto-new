"""Unit tests for the BRAIN API client (backend/app/imports/brain.py).

All HTTP traffic is mocked — no real network calls are made.  The client
module is loaded through importlib (same convention as
test_dclink_image_fix.py) so the tests are independent of the app package
import chain.
"""

import hashlib
import importlib.util
import time
from pathlib import Path

import pytest
import requests

_BRAIN_PATH = str(
    Path(__file__).resolve().parents[2] / "backend/app/imports/brain.py"
)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def brain():
    return _load_module("_test_brain_client_module", _BRAIN_PATH)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("no json")
        return self._payload


def make_client(brain, **kwargs):
    # Disable throttling delay by default (rate-limit behaviour is tested
    # explicitly where needed).
    kwargs.setdefault("request_interval", 0)
    return brain.BrainClient(**kwargs)


# --------------------------------------------------------------------------- auth


def test_authenticate_sends_form_encoded_md5_password(brain, monkeypatch):
    calls = []

    def fake_post(url, data=None, timeout=None, **kwargs):
        calls.append({"url": url, "data": data, "kwargs": kwargs})
        return FakeResponse(payload={"status": 1, "result": "SESSIONABC123"})

    monkeypatch.setattr(brain.requests, "post", fake_post)
    client = make_client(brain, login="dealer@test.ua", password="s3cret")

    sid = client.authenticate()

    assert sid == "SESSIONABC123"
    assert client.sid == "SESSIONABC123"
    assert len(calls) == 1
    assert calls[0]["url"].endswith("/auth")
    # Form-encoded fields (NOT a JSON body) — verified against the live API.
    assert calls[0]["data"]["login"] == "dealer@test.ua"
    assert calls[0]["data"]["password"] == hashlib.md5(b"s3cret").hexdigest()
    assert "json" not in calls[0]["kwargs"]


def test_authenticate_bad_credentials_raises_auth_error(brain, monkeypatch):
    def fake_post(url, data=None, timeout=None, **kwargs):
        return FakeResponse(payload={
            "status": 0, "error_code": 6,
            "error_message": "Incorrect login or password",
        })

    monkeypatch.setattr(brain.requests, "post", fake_post)
    client = make_client(brain, login="bad", password="creds")

    with pytest.raises(brain.BrainAuthError):
        client.authenticate()
    # Credentials must never leak through the exception message.
    try:
        client.authenticate()
    except brain.BrainAuthError as exc:
        assert "bad" not in str(exc)
        assert "creds" not in str(exc)


def test_authenticate_blocked_user_raises_auth_error(brain, monkeypatch):
    monkeypatch.setattr(
        brain.requests, "post",
        lambda *a, **k: FakeResponse(payload={"status": 0, "error_code": 7}),
    )
    client = make_client(brain, login="u", password="p")
    with pytest.raises(brain.BrainAuthError):
        client.authenticate()


def test_authenticate_missing_credentials_raises_config_error(brain, monkeypatch):
    for attr in ("SUPPLIER_BRAIN_LOGIN", "SUPPLIER_BRAIN_PASSWORD",
                 "BRAIN_LOGIN", "BRAIN_PASSWORD"):
        monkeypatch.setattr(brain.settings, attr, "")
    client = make_client(brain)
    with pytest.raises(brain.BrainConfigError):
        client.authenticate()


def test_authenticate_network_error_raises_api_error(brain, monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(brain.requests, "post", boom)
    client = make_client(brain, login="u", password="p")
    with pytest.raises(brain.BrainAPIError):
        client.authenticate()


def test_authenticate_legacy_env_fallback(brain, monkeypatch):
    """Legacy .env name BRAIN_LOGIN with BRAIN_PASSWORD must work."""
    monkeypatch.setattr(brain.settings, "SUPPLIER_BRAIN_LOGIN", "")
    monkeypatch.setattr(brain.settings, "SUPPLIER_BRAIN_PASSWORD", "")
    monkeypatch.setattr(brain.settings, "BRAIN_LOGIN", "legacy_login")
    monkeypatch.setattr(brain.settings, "BRAIN_PASSWORD", "legacy_pass")

    captured = {}

    def fake_post(url, data=None, timeout=None, **kwargs):
        captured["data"] = data
        return FakeResponse(payload={"status": 1, "result": "SID"})

    monkeypatch.setattr(brain.requests, "post", fake_post)
    client = make_client(brain)
    client.authenticate()
    assert captured["data"]["login"] == "legacy_login"
    assert captured["data"]["password"] == hashlib.md5(b"legacy_pass").hexdigest()


# --------------------------------------------------------------- envelope/errors


def _auth_ok(monkeypatch, brain):
    monkeypatch.setattr(
        brain.requests, "post",
        lambda *a, **k: FakeResponse(payload={"status": 1, "result": "SIDOK"}),
    )


def test_get_categories_returns_result_list(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    cats = [{"categoryID": 11, "parentID": 1, "realcat": 0, "name": "Комп'ютери"}]
    urls = []

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        urls.append((method, url, params))
        return FakeResponse(payload={"status": 1, "result": cats})

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")

    result = client.get_categories()

    assert result == cats
    method, url, params = urls[0]
    assert method == "GET"
    assert "/categories/" in url
    assert params["lang"] == "ua"


def test_get_products_page_passes_limit_offset(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    seen = []

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        seen.append((url, params))
        return FakeResponse(payload={"status": 1, "result": {"list": [], "count": 42}})

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")

    result = client.get_products_page(155, limit=100, offset=200)

    assert result == {"list": [], "count": 42}
    url, params = seen[0]
    assert "/products/155/" in url
    assert params == {"lang": "ua", "limit": 100, "offset": 200}


def test_get_products_page_limit_fallback_on_error_20(brain, monkeypatch):
    """Accounts without OWN_MODE: error 20 lowers the page size to 100."""
    _auth_ok(monkeypatch, brain)
    limits_used = []

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        limits_used.append(params["limit"])
        if params["limit"] > 100:
            return FakeResponse(payload={
                "status": 0, "error_code": 20,
                "error_message": "Exceed max limit value",
            })
        return FakeResponse(payload={"status": 1, "result": {"list": [], "count": 0}})

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p", page_limit=1000)

    result = client.get_products_page(155)

    assert result == {"list": [], "count": 0}
    assert limits_used == [1000, 100]
    assert client.page_limit == 100


def test_sid_expiry_triggers_single_reauth(brain, monkeypatch):
    """error_code 5 (SID expired) → exactly one re-auth, then success."""
    auth_calls = {"n": 0}

    def fake_post(url, data=None, timeout=None, **kwargs):
        auth_calls["n"] += 1
        return FakeResponse(payload={"status": 1, "result": f"SID{auth_calls['n']}"})

    monkeypatch.setattr(brain.requests, "post", fake_post)
    product_calls = {"n": 0}

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        product_calls["n"] += 1
        if product_calls["n"] == 1:
            return FakeResponse(payload={
                "status": 0, "error_code": 5,
                "error_message": "Session identifier is outdate",
            })
        return FakeResponse(payload={"status": 1, "result": {"list": [], "count": 0}})

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")

    result = client.get_products_page(1)

    assert result == {"list": [], "count": 0}
    assert auth_calls["n"] == 2  # initial auth + one re-auth
    assert product_calls["n"] == 2


def test_rate_limit_http_429_retries_then_succeeds(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    sleeps = []
    monkeypatch.setattr(brain.time, "sleep", lambda s: sleeps.append(s))
    calls = {"n": 0}

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(status_code=429)
        return FakeResponse(payload={"status": 1, "result": []})

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")

    assert client.get_categories() == []
    assert calls["n"] == 2
    assert sleeps  # backoff was applied


def test_rate_limit_error_115_retries(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    monkeypatch.setattr(brain.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse(payload={
                "status": 0, "error_code": 115,
                "error_message": "Too many requests",
            })
        return FakeResponse(payload={"status": 1, "result": []})

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")
    assert client.get_categories() == []
    assert calls["n"] == 2


def test_api_error_includes_code_but_never_the_sid(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        return FakeResponse(payload={
            "status": 0, "error_code": 21,
            "error_message": "No category with specified categoryID",
        })

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")

    with pytest.raises(brain.BrainAPIError) as exc_info:
        client.get_products_page(999999)

    assert exc_info.value.error_code == 21
    assert "SIDOK" not in str(exc_info.value)   # SID never leaks
    assert "/products/" not in str(exc_info.value)


def test_invalid_json_raises_api_error(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    monkeypatch.setattr(
        brain.requests, "request",
        lambda *a, **k: FakeResponse(json_error=True),
    )
    client = make_client(brain, login="u", password="p")
    with pytest.raises(brain.BrainAPIError):
        client.get_categories()


def test_http_4xx_raises_api_error(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    monkeypatch.setattr(
        brain.requests, "request",
        lambda *a, **k: FakeResponse(status_code=404),
    )
    client = make_client(brain, login="u", password="p")
    with pytest.raises(brain.BrainAPIError):
        client.get_categories()


def test_network_error_retries_then_raises(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    monkeypatch.setattr(brain.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_request(*a, **k):
        calls["n"] += 1
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")
    with pytest.raises(brain.BrainAPIError):
        client.get_categories()
    assert calls["n"] == brain._MAX_ATTEMPTS


# --------------------------------------------------------------- content batches


def test_content_request_batching(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    bodies = []

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        assert method == "POST"
        assert "/products/content/" in url
        bodies.append(data["productIDs"])
        ids = [int(x) for x in data["productIDs"].split(",")]
        return FakeResponse(payload={
            "status": 1,
            "result": {"list": [{"productID": i, "description": "d"} for i in ids]},
        })

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")

    items = client.get_products_content([1, 2, 3, 4, 5], batch_size=2)

    assert bodies == ["1,2", "3,4", "5"]
    assert [i["productID"] for i in items] == [1, 2, 3, 4, 5]


def test_content_accepts_plain_list_result(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    monkeypatch.setattr(
        brain.requests, "request",
        lambda *a, **k: FakeResponse(payload={"status": 1,
                                              "result": [{"productID": 1}]}),
    )
    client = make_client(brain, login="u", password="p")
    items = client.get_products_content([1])
    assert items == [{"productID": 1}]


# --------------------------------------------------------------- misc


def test_logout_clears_sid_and_calls_endpoint(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    logout_urls = []
    monkeypatch.setattr(
        brain.requests, "request",
        lambda *a, **k: FakeResponse(payload={"status": 1, "result": []}),
    )

    def fake_get(url, timeout=None, **kw):
        logout_urls.append(url)
        return FakeResponse(status_code=200, payload={"status": 1})

    monkeypatch.setattr(brain.requests, "get", fake_get)
    client = make_client(brain, login="u", password="p")
    client.authenticate()
    client.logout()
    assert client.sid is None
    assert len(logout_urls) == 1
    # second logout without SID performs no request
    client.logout()
    assert len(logout_urls) == 1


def test_throttle_enforces_min_interval(brain, monkeypatch):
    client = make_client(brain, login="u", password="p", request_interval=0.05)
    start = time.monotonic()
    client._throttle()
    client._throttle()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.045


def test_modified_products_url_shapes(brain, monkeypatch):
    _auth_ok(monkeypatch, brain)
    urls = []

    def fake_request(method, url, params=None, data=None, timeout=None, **kw):
        urls.append((url, params))
        return FakeResponse(payload={"status": 1, "result": {"productIDs": []}})

    monkeypatch.setattr(brain.requests, "request", fake_request)
    client = make_client(brain, login="u", password="p")

    client.get_modified_products()
    client.get_modified_products(modified_type="images",
                                 modified_time="2016-04-17 07:00:00")

    assert "/modified_products/" in urls[0][0]
    assert "/modified_products/images/" in urls[1][0]
    assert urls[1][1]["modified_time"] == "2016-04-17 07:00:00"


def test_brain_registered_in_system_registry():
    from app.imports.registry import SUPPLIERS
    assert "brain" in SUPPLIERS
    assert SUPPLIERS["brain"]["name"] == "BRAIN"
    assert SUPPLIERS["brain"]["importer"].SUPPLIER_CODE == "brain"
    assert SUPPLIERS["brain"]["importer"].SKU_PREFIX == "BRA-"



