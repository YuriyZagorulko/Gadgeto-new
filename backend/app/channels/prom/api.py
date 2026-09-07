"""Prom.ua channel adapter (placeholder).

Implements the ``ChannelAdapter`` contract for the future Prom.ua
Seller API.  Because the real Prom.ua API/authentication is not available
yet, every operation:

  * verifies the integration is configured (``PROM_ENABLED`` + URL +
    credentials) — raising ``PromNotConfiguredError`` otherwise;
  * otherwise raises ``NotImplementedError`` with a clear message so the
    future API client can be dropped in without redesigning anything else.

``classify_error`` is the one generic method that works today — it maps
incoming exceptions onto the project's ``SyncJobErrorType`` vocabulary so the
export engine can record consistent error types once Prom operations are wired
in.
"""

from __future__ import annotations

from typing import Any, Optional

from app.channels.base import ChannelAdapter
from app.channels.prom.client import (
    PROM_NOT_CONFIGURED_MESSAGE,
    PromApiClient,
    is_prom_configured,
)
from app.channels.prom.errors import PromNotConfiguredError

_NOT_IMPLEMENTED = (
    "Prom.ua API client is a future implementation point — "
    "real communication is not implemented yet."
)


class PromAdapter(ChannelAdapter):
    """Placeholder adapter for the Prom.ua channel.

    When ``api_client`` is provided (e.g. in tests) the configuration guard is
    still applied unless ``require_configured=False`` is passed, which lets the
    object graph be built for introspection without real credentials.
    """

    channel_code = "prom"

    def __init__(self, api_client: Any = None, require_configured: bool = True):
        if require_configured and not is_prom_configured():
            # Kept as LookupError subclass so get_adapter() registry lookups
            # behave exactly like unknown channels (existing behaviour).
            raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)
        self._client = api_client

    def _require_ready(self) -> "PromApiClient":
        """Return a configured client or raise; never makes network calls."""
        if not is_prom_configured():
            raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)
        if self._client is None:
            self._client = PromApiClient()
        return self._client

    # ------------------------------------------------------------ transport
    def push_product(self, listing) -> dict:
        self._require_ready()
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def update_price_stock(self, listing) -> dict:
        self._require_ready()
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def unpublish(self, listing) -> dict:
        self._require_ready()
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def fetch_listing_status(self, listing) -> Optional[str]:
        self._require_ready()
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def classify_error(self, exc: Exception) -> tuple[str, bool]:
        """Map exceptions onto SyncJobErrorType values + retryable flag.

        Transient → retryable; anything else → non-retryable invalid_data.
        Prom.ua-specific API errors will be classified here once the real
        client exists.
        """
        name = type(exc).__name__
        text = str(exc)
        lowered = text.lower()
        if isinstance(exc, TimeoutError) or "timeout" in name.lower() \
                or "timeout" in lowered:
            return ("timeout", True)
        if "connection" in name.lower() or "requesterror" in name.lower() \
                or "network" in lowered:
            return ("network", True)
        if "429" in text or "rate limit" in lowered:
            return ("rate_limit", True)
        if any(s in text for s in ("HTTP 500", "HTTP 502", "HTTP 503",
                                   "HTTP 504", "status 5")):
            return ("server_5xx", True)
        if "auth" in name.lower() or "credential" in lowered:
            return ("auth", False)
        return ("invalid_data", False)