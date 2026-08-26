"""Channel adapter abstraction.

A ChannelAdapter encapsulates every marketplace-specific transport/API
behaviour: publishing, commercial updates, unpublishing, status lookup
and error classification.  The sync engine talks ONLY to this interface,
so future channels (Prom.ua, Amazon, ...) plug in without touching
catalog code.

Operations that are generic channel-agnostic services (validation,
transformation, taxonomy refresh, pricing/stock settings, the export
runner) live outside the adapter — see validation.py, transformer.py,
taxonomy.py, export_settings.py, export_run.py.

RozetkaAdapter implements the OFFICIAL Seller API workflow documented at
https://api-seller.rozetka.com.ua/apidoc/ :
  create     -> POST /items-create/create             (one JSON product)
  content    -> PUT /items-create/mass-update-basic-data
  commercial -> PUT /items/mass-update                ({item_rz_id,...})
  lookup     -> GET /goods/all | /goods/details
The raw HTTP conversations live in app/channels/rozetka/api.py; this class
adapts them to the ChannelAdapter contract used by the export engine.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

import logging

logger = logging.getLogger("channels.adapter")


class ChannelAdapter(ABC):
    """Contract every marketplace adapter must satisfy.

    The adapter is responsible only for transport and API-specific wire
    format.  Generic operations (validation, transformation, taxonomy) are
    handled by dedicated services.

    Convention used by the export engine: every `listing` argument is a
    plain dict that already carries everything resolved server-side:

        {
          "operation": "create" | "update",
          "sku": "...",
          "payload": {...},                      # for push_product()
          "external_ref": {"item_id": int|None, "rz_item_id": int|None},
          "price": float|None,
          "stock_quantity": int|None,
        }
    """

    #: Stable channel code, e.g. "rozetka" (matches channels.code).
    channel_code: str

    @abstractmethod
    def push_product(self, listing) -> dict:
        """Create/update the remote listing.  Returns e.g.
        {"external_id": ..., "remote_status": ..., "operation": ...}."""

    @abstractmethod
    def update_price_stock(self, listing) -> dict:
        """Lightweight commercial update (price / stock / availability)."""

    @abstractmethod
    def unpublish(self, listing) -> dict:
        """Disable/hide the remote listing WITHOUT physical deletion."""

    @abstractmethod
    def fetch_listing_status(self, listing) -> Optional[str]:
        """Return the marketplace's own status for the listing."""

    @abstractmethod
    def classify_error(self, exc: Exception) -> tuple[str, bool]:
        """Classify an exception into (error_type, retryable).  error_type is a
        SyncJobErrorType value ('network', 'rate_limit', 'auth', ...)."""



class RozetkaAdapter(ChannelAdapter):
    """Rozetka Seller API adapter (Phase 6.3).

    Implements exactly the officially documented mechanism.  All catalog
    decisions (mappings, pricing, stock rules, idempotency state) are made
    upstream in the export engine; this adapter performs the transport.
    """

    channel_code = "rozetka"

    def __init__(self, api_client=None):
        from app.channels.rozetka.api import RozetkaApiClient
        self._client = api_client or RozetkaApiClient()

    # ------------------------------------------------------------- push

    def push_product(self, listing: dict) -> dict:
        """Create or content-update one item on Rozetka."""
        op = (listing.get("operation") or "create").lower()
        sku = listing.get("sku") or ""

        if op == "create":
            created = self._client.create_item(listing["payload"])
            item_id = int(created["item_id"])
            logger.info("rozetka create ok sku=%s item_id=%s", sku, item_id)
            return {
                "external_id": str(item_id),
                "remote_status": None,
                "operation": "create",
                "created": True,
                "raw": created,
            }

        # update — PUT /items-create/mass-update-basic-data accepts either
        # item_id or rz_item_id (documented: exactly one is required).
        ext_ref = listing.get("external_ref") or {}
        if ext_ref.get("item_id") is None and ext_ref.get("rz_item_id") is None:
            raise ValueError("Оновлення без ідентифікатора Rozetka неможливе")
        result = self._client.update_items_basic_data([listing["payload"]])
        updated = int((result.get("items_updated") or 0)) if isinstance(result, dict) else 0
        logger.info("rozetka basic-data update ok sku=%s items_updated=%s",
                    sku, updated)
        return {
            "external_id": _preferred_external_id(ext_ref),
            "remote_status": None,
            "operation": "update",
            "created": False,
            "items_updated": updated,
        }

    # ------------------------------------------------------- commercial

    def update_price_stock(self, listing: dict) -> dict:
        """PUT /items/mass-update — documented fields item_rz_id / price /
        stock_quantity.  Requires the marketplace-side rz_item_id."""
        ext_ref = listing.get("external_ref") or {}
        rz_id = ext_ref.get("rz_item_id")
        if rz_id is None:
            raise ValueError(
                "Оновлення ціни/залишку потребує rz_item_id — товар ще не "
                "присвоєний маркетплейсом")
        item = {
            "item_rz_id": int(rz_id),
            "price": int(round(float(listing.get("price")))),
            "stock_quantity": int(listing.get("stock_quantity") or 0),
        }
        self._client.mass_update_price_stock([item])
        logger.info("rozetka mass-update ok sku=%s rz_item_id=%s",
                    listing.get("sku"), rz_id)
        return {"external_id": str(rz_id), "operation": "price_stock"}

    def unpublish(self, listing: dict) -> dict:
        """Disable the listing WITHOUT physical deletion.

        The official docs expose availability through /items/mass-update;
        zeroing stock makes the item unavailable for sale.  No undocumented
        hide/archive endpoint exists.
        """
        data = dict(listing)
        data["stock_quantity"] = 0
        return self.update_price_stock(data)

    def fetch_listing_status(self, listing: dict) -> Optional[str]:
        """GET /goods/details and surface the remote sell/upload status."""
        ext_ref = listing.get("external_ref") or {}
        details = None
        if ext_ref.get("rz_item_id") is not None:
            details = self._client.get_item_details(
                rz_item_id=int(ext_ref["rz_item_id"]))
        if details is None and ext_ref.get("item_id") is not None:
            details = self._client.get_item_details(item_id=int(ext_ref["item_id"]))
        if not details:
            return None
        for key in ("sell_status", "rz_sell_status", "upload_status",
                    "status_moderation", "status"):
            if details.get(key):
                return str(details[key])
        return None

    def resolve_external_ref(self, listing: dict) -> dict:
        """Normalise a possibly-stale stored external_id into the full
        {item_id, rz_item_id} pair using GET /goods/details.

        The stored channel_listings.external_id prefers the marketplace-side
        rz_item_id but may temporarily hold the internal API item_id (right
        after creation, before moderation assigns an rz id).
        """
        ext_raw = str(listing.get("external_id") or "").strip()
        if not ext_raw or not ext_raw.isdigit():
            return {}
        number = int(ext_raw)
        details = self._client.get_item_details(rz_item_id=number)
        if not details:
            # The stored id may be the internal API item_id (freshly created
            # items get rz_item_id only after Rozetka assigns it).
            details = self._client.get_item_details(item_id=number)
        if not details:
            return {}
        return {
            "item_id": details.get("item_id"),
            "rz_item_id": details.get("rz_item_id") or (
                number if details.get("rz_item_id") == number else None),
        }

    def classify_error(self, exc: Exception) -> tuple[str, bool]:
        """Map exceptions onto SyncJobErrorType values + retryable flag.

        Transient (retryable): timeout, network, HTTP 429, 5xx.
        Permanent: Rozetka validation errors, per-item mass-update
        rejections, auth failures, invalid payloads.
        """
        from app.channels.rozetka.api import (
            RozetkaApiError,
            RozetkaMassUpdateError,
        )
        from app.channels.rozetka.client import RozetkaAuthError

        if isinstance(exc, RozetkaMassUpdateError):
            return ("validation", False)
        if isinstance(exc, RozetkaApiError):
            return (exc.error_type or "invalid_data", bool(exc.retryable))
        if isinstance(exc, RozetkaAuthError):
            return ("auth", False)
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
        return ("invalid_data", False)


def _preferred_external_id(ext_ref: dict) -> str:
    """Marketplace-side id wins (it can address commercial updates)."""
    if ext_ref.get("rz_item_id") is not None:
        return str(ext_ref["rz_item_id"])
    return str(ext_ref.get("item_id") or "")


def get_adapter(channel_code: str) -> ChannelAdapter:
    """Resolve an adapter by stable channel code.

    Raises LookupError while a concrete integration does not exist
    (callers must treat channels without adapters as not-yet-syncable).
    """
    registry: dict[str, type[ChannelAdapter]] = {
        RozetkaAdapter.channel_code: RozetkaAdapter,
    }
    cls = registry.get(channel_code)
    if cls is None:
        raise LookupError(f"Немає адаптера для каналу '{channel_code}'")
    return cls()




def get_adapter(channel_code: str) -> ChannelAdapter:
    """Resolve an adapter by stable channel code.

    Raises LookupError while the concrete integration is not implemented
    (callers must treat channels without adapters as not-yet-syncable).
    """
    registry: dict[str, type[ChannelAdapter]] = {
        RozetkaAdapter.channel_code: RozetkaAdapter,
    }
    cls = registry.get(channel_code)
    if cls is None:
        raise LookupError(f"Немає адаптера для каналу '{channel_code}'")
    return cls()