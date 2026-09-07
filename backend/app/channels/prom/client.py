"""Prom.ua API client — interface boundary (placeholder).

THIS MODULE IS THE future implementation point for the real Prom.ua API /
authentication.  At this stage we deliberately do NOT have Prom.ua credentials
or API documentation, so:

  * no real authentication is implemented;
  * no real HTTP requests are ever made;
  * no Prom.ua API endpoints / payloads are invented.

What IS provided:

  * ``is_prom_enabled()``       — read PROM_ENABLED (env, default false);
  * ``is_prom_configured()``    — enabled AND a non-empty API URL AND some
                                  credentials blob are present;
  * ``PromApiClient``           — the documented interface the future real
                                  client must implement.  Instantiating it
                                  while not configured raises
                                  ``PromNotConfiguredError``.

When Prom.ua credentials/API docs become available, implement the methods of
``PromApiClient`` here (real auth + transport) and nothing else in the system
needs to change.
"""

from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings

from app.channels.prom.errors import (
    PROM_NOT_CONFIGURED_MESSAGE,
    PromNotConfiguredError,
)

# Sentinel used to let callers opt out of the configuration guard (e.g. when a
# supervisor wants to build the object graph without real credentials).
_UNSET = object()


def is_prom_enabled() -> bool:
    """Whether the Prom.ua channel is enabled at all (env default: False)."""
    return bool(getattr(settings, "PROM_ENABLED", False))


def is_prom_configured() -> bool:
    """Whether Prom.ua can actually be used.

    Requires: PROM_ENABLED=true, a non-empty PROM_API_URL and a non-empty
    PROM_CREDENTIALS_JSON blob.  Until all three are present the integration
    is treated as "not configured" and every operation fails cleanly with
    ``PromNotConfiguredError`` — no request is ever made.
    """
    if not is_prom_enabled():
        return False
    if not (getattr(settings, "PROM_API_URL", "") or "").strip():
        return False
    if not (getattr(settings, "PROM_CREDENTIALS_JSON", "") or "").strip():
        return False
    return True


class PromApiClient:
    """Contract for the future Prom.ua API client.

    Implement these methods when Prom.ua credentials/API documentation are
    available.  Until then the class only guarantees the configuration guard.
    """

    def __init__(self, require_configured: bool = True) -> None:
        self._base_url = (getattr(settings, "PROM_API_URL", "") or "").strip()
        if require_configured and not is_prom_configured():
            raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)

    # ------------------------------------------------------------------ auth
    def authenticate(self) -> dict:
        """Future: authenticate to Prom.ua and return auth state.

        Currently a placeholder — raises a clear error instead of ever making
        a real (or invented) HTTP call.
        """
        raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)

    # ------------------------------------------------------------- transport
    def push_product(self, payload: dict) -> dict:
        """Future: create/update one Prom.ua listing.  Placeholder."""
        raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)

    def update_price_stock(self, payload: dict) -> dict:
        """Future: commercial (price/stock) update.  Placeholder."""
        raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)

    def unpublish(self, payload: dict) -> dict:
        """Future: hide/disable a listing.  Placeholder."""
        raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)

    def fetch_listing_status(self, external_id: Any) -> Optional[str]:
        """Future: read marketplace status.  Placeholder."""
        raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)

    def refresh_taxonomy(self, channel_id: int) -> dict:
        """Future: fetch Prom.ua taxonomy (categories/attributes/values)."""
        raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)


__all__ = [
    "PromApiClient",
    "PromNotConfiguredError",
    "PROM_NOT_CONFIGURED_MESSAGE",
    "is_prom_enabled",
    "is_prom_configured",
]