"""Rozetka Seller API authentication client.

Official documentation:
  POST /sites
  Content-Type: application/json
  Body: { "username": "...", "password": "<Base64(password)>" }
  Response: { "success": true, "content": { "id": ..., "access_token": "...", ... } }

The access_token is valid for 24 hours of inactivity and is extended with each use.
This client does NOT persist the token — it returns it in-memory.
"""

import base64
from typing import Optional

import httpx

from app.core.config import settings


ROZETKA_API_URL = settings.ROZETKA_API_URL.rstrip("/")


class RozetkaAuthResult:
    """Result of a successful /sites authentication call."""

    def __init__(self, seller_id: int, access_token: str, permissions: list[str],
                 market_id: int, market_title: str):
        self.seller_id = seller_id
        self.access_token = access_token
        self.permissions = permissions
        self.market_id = market_id
        self.market_title = market_title

    def __repr__(self) -> str:
        return (
            f"<RozetkaAuthResult seller_id={self.seller_id} "
            f"market_id={self.market_id} market_title={self.market_title!r}>"
        )


class RozetkaAuthError(Exception):
    """Raised when authentication fails (wrong credentials, network error, etc.)."""


class RozetkaAuthClient:
    """Minimal HTTP client for Rozetka Seller API authentication.

    Reads credentials from the application config and does NOT log/store them.
    """

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self._username = username or settings.ROZETKA_SELLER_USERNAME
        self._password = password or settings.ROZETKA_SELLER_PASSWORD
        self._base_url = ROZETKA_API_URL

    def authenticate(self) -> RozetkaAuthResult:
        """Authenticate with the Rozetka Seller API.

        Returns:
            RozetkaAuthResult with seller_id, access_token, permissions, market info.

        Raises:
            RozetkaAuthError if credentials are missing, the API returns an error,
            or a network/HTTP error occurs.
        """
        if not self._username or not self._password:
            raise RozetkaAuthError(
                "ROZETKA_SELLER_USERNAME and ROZETKA_SELLER_PASSWORD must be set"
            )

        try:
            password_b64 = base64.b64encode(self._password.encode()).decode()
        except Exception as e:
            raise RozetkaAuthError(f"Failed to Base64-encode password: {e}") from e

        payload = {
            "username": self._username,
            "password": password_b64,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self._base_url}/sites",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            raise RozetkaAuthError(f"Request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise RozetkaAuthError(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.RequestError as e:
            raise RozetkaAuthError(f"Network error: {e}") from e
        except ValueError as e:
            raise RozetkaAuthError(f"Invalid JSON response: {e}") from e

        # Parse the documented response envelope
        if not isinstance(data, dict):
            raise RozetkaAuthError(f"Unexpected response type: {type(data).__name__}")

        if not data.get("success"):
            errors = data.get("errors", "unknown error")
            raise RozetkaAuthError(f"API returned error: {errors}")

        content = data.get("content")
        if not isinstance(content, dict):
            raise RozetkaAuthError(f"Missing or invalid 'content' in response: {content}")

        access_token = content.get("access_token")
        if not access_token or not isinstance(access_token, str):
            raise RozetkaAuthError("Missing or invalid 'access_token' in response")

        seller_id = content.get("id")
        if not isinstance(seller_id, int):
            raise RozetkaAuthError(f"Missing or invalid 'id' (seller_id): {seller_id}")

        permissions = content.get("permissions") or []
        market = content.get("market") or {}
        market_id = market.get("id") if isinstance(market, dict) else None
        market_title = market.get("title") if isinstance(market, dict) else ""

        return RozetkaAuthResult(
            seller_id=seller_id,
            access_token=access_token,
            permissions=permissions,
            market_id=market_id,
            market_title=market_title,
        )