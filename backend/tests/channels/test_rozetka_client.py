"""Tests for the Rozetka authentication client."""

import json
import base64

import httpx
import pytest
from unittest.mock import patch, MagicMock

from app.channels.rozetka.client import (
    RozetkaAuthClient,
    RozetkaAuthResult,
    RozetkaAuthError,
    ROZETKA_API_URL,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def mock_success_response() -> dict:
    """A realistic successful /sites response."""
    return {
        "success": True,
        "content": {
            "id": 107940,
            "access_token": "test_access_token_12345",
            "permissions": ["api_items_view", "api_items_delete", "owner"],
            "roles": ["admin"],
            "seller": {
                "fio": "Test Seller",
                "email": "seller@example.com",
                "first_phone": {"id": 1, "phone_number": "+380501234567", "confirmed": True},
                "wizard": False,
            },
            "market": {
                "id": 42,
                "title": "Test Shop",
                "logo": "https://example.com/logo.png",
                "business_model": "marketplace",
                "market_url": "https://example.com/shop",
                "status": 1,
            },
            "lang": "uk",
        },
    }


def mock_error_response(code: str = "incorrect_username_pasword", message: str = "") -> dict:
    return {
        "success": False,
        "errors": {"code": code, "message": message or "Неправильний логин или пароль"},
    }


# ── Tests ────────────────────────────────────────────────────────────────────


class TestRozetkaAuthClient:
    """Tests for RozetkaAuthClient."""

    def test_password_base64_encoding(self):
        """Verify that the password is Base64-encoded before sending."""
        client = RozetkaAuthClient(username="test_user", password="test_password")
        expected_b64 = base64.b64encode(b"test_password").decode()
        assert client._password == "test_password"
        # Verify encoding logic (not the actual request)
        encoded = base64.b64encode(client._password.encode()).decode()
        assert encoded == expected_b64
        assert encoded == "dGVzdF9wYXNzd29yZA=="

    def test_empty_password_raises(self):
        """Empty username or password should raise RozetkaAuthError."""
        client = RozetkaAuthClient(username="", password="")
        with pytest.raises(RozetkaAuthError, match="must be set"):
            client.authenticate()

    def test_none_password_raises(self):
        client = RozetkaAuthClient(username=None, password=None)  # type: ignore
        with pytest.raises(RozetkaAuthError, match="must be set"):
            client.authenticate()

    def test_successful_response_parsing(self):
        """A successful API response should be parsed into RozetkaAuthResult."""
        mock_response = mock_success_response()

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value = mock_response_obj

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            result = client.authenticate()

            assert isinstance(result, RozetkaAuthResult)
            assert result.seller_id == 107940
            assert result.access_token == "test_access_token_12345"
            assert result.permissions == ["api_items_view", "api_items_delete", "owner"]
            assert result.market_id == 42
            assert result.market_title == "Test Shop"

    def test_unsuccessful_response(self):
        """An API error response should raise RozetkaAuthError."""
        mock_response = mock_error_response()

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value = mock_response_obj

            client = RozetkaAuthClient(username="bad_user", password="bad_pass")
            with pytest.raises(RozetkaAuthError, match="incorrect_username_pasword"):
                client.authenticate()

    def test_http_error_response(self):
        """An HTTP error (e.g. 500) should raise RozetkaAuthError."""
        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500, text="Internal Server Error"),
            )

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            with pytest.raises(RozetkaAuthError, match="500"):
                client.authenticate()

    def test_timeout_error(self):
        """A network timeout should raise RozetkaAuthError."""
        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Connection timed out")

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            with pytest.raises(RozetkaAuthError, match="timed out"):
                client.authenticate()

    def test_network_error(self):
        """A network error should raise RozetkaAuthError."""
        with patch.object(httpx.Client, "post") as mock_post:
            mock_post.side_effect = httpx.RequestError("DNS resolution failed")

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            with pytest.raises(RozetkaAuthError, match="Network error"):
                client.authenticate()

    def test_malformed_json_response(self):
        """A non-JSON response should raise RozetkaAuthError."""
        with patch.object(httpx.Client, "post") as mock_post:
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.side_effect = ValueError("Invalid JSON")
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value = mock_response_obj

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            with pytest.raises(RozetkaAuthError, match="Invalid JSON"):
                client.authenticate()

    def test_missing_access_token(self):
        """Response without access_token should raise RozetkaAuthError."""
        mock_response = {"success": True, "content": {"id": 123}}

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value = mock_response_obj

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            with pytest.raises(RozetkaAuthError, match="access_token"):
                client.authenticate()

    def test_missing_seller_id(self):
        """Response without seller id should raise RozetkaAuthError."""
        mock_response = {"success": True, "content": {"access_token": "abc"}}

        with patch.object(httpx.Client, "post") as mock_post:
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value = mock_response_obj

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            with pytest.raises(RozetkaAuthError, match="seller_id"):
                client.authenticate()

    def test_post_url_and_headers(self):
        """Verify the correct URL and headers are sent."""
        with patch.object(httpx.Client, "post") as mock_post:
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_success_response()
            mock_response_obj.raise_for_status.return_value = None
            mock_post.return_value = mock_response_obj

            client = RozetkaAuthClient(username="test_user", password="test_pass")
            client.authenticate()

            # Verify the request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            url = call_args[0][0]
            kwargs = call_args[1]

            assert "/sites" in url
            assert "json" in kwargs
            assert kwargs["json"]["username"] == "test_user"
            # Password should be Base64 encoded
            assert kwargs["json"]["password"] == base64.b64encode(b"test_pass").decode()
            assert kwargs["headers"]["Content-Type"] == "application/json"

    def test_rozetka_api_url_default(self):
        """Default API URL should be the official Rozetka endpoint."""
        assert "api-seller.rozetka.com.ua" in ROZETKA_API_URL


class TestRozetkaAuthResult:
    """Tests for RozetkaAuthResult data class."""

    def test_repr_does_not_contain_token(self):
        """The repr should not leak the access_token."""
        result = RozetkaAuthResult(
            seller_id=123, access_token="secret123",
            permissions=["view"], market_id=42, market_title="Shop"
        )
        r = repr(result)
        assert "secret123" not in r
        assert "access_token" not in r
        assert "seller_id=123" in r
        assert "market_id=42" in r
        assert "Shop" in r
