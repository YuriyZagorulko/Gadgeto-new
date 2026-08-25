"""Channel adapter abstraction.

A ChannelAdapter encapsulates every marketplace-specific transport/API
behaviour: publishing, commercial updates, unpublishing, status lookup
and error classification.  The sync engine talks ONLY to this interface,
so future channels (Prom.ua, Amazon, ...) plug in without touching
catalog code.

Operations that are already implemented as generic channel-agnostic
services (validation, transformation, taxonomy refresh) live outside
the adapter — see validation.py, transformer.py, taxonomy.py.

Phase 1: interface only — no marketplace API logic is implemented yet.
Concrete endpoints will be added in the Rozetka integration phase once the
authenticated seller documentation/credentials are available.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ChannelAdapter(ABC):
    """Contract every marketplace adapter must satisfy.

    The adapter is responsible only for transport and API-specific
    wire format.  Generic operations (validation, transformation,
    taxonomy) are handled by dedicated services.
    """

    #: Stable channel code, e.g. "rozetka" (matches channels.code).
    channel_code: str

    @abstractmethod
    def push_product(self, listing) -> dict:
        """Create/update the remote listing.  Returns e.g.
        {"external_id": ..., "remote_status": ...}."""

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
    """Placeholder for the Rozetka marketplace adapter.

    Deliberately contains NO API logic in Phase 1: the official Seller API
    documentation is behind the authenticated seller portal and must be
    verified with real credentials before any endpoint is coded.
    """

    channel_code = "rozetka"

    def push_product(self, listing) -> dict:
        raise NotImplementedError("RozetkaAdapter.push_product — API credentials required")

    def update_price_stock(self, listing) -> dict:
        raise NotImplementedError("RozetkaAdapter.update_price_stock — API credentials required")

    def unpublish(self, listing) -> dict:
        raise NotImplementedError("RozetkaAdapter.unpublish — API credentials required")

    def fetch_listing_status(self, listing) -> Optional[str]:
        raise NotImplementedError("RozetkaAdapter.fetch_listing_status — API credentials required")

    def classify_error(self, exc: Exception) -> tuple[str, bool]:
        raise NotImplementedError("RozetkaAdapter.classify_error — API credentials required")


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