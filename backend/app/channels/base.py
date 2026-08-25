"""Channel adapter abstraction.

A ChannelAdapter encapsulates every marketplace-specific behaviour:
taxonomy refresh, validation, transformation, publishing and error
classification.  The sync engine talks ONLY to this interface, so future
channels (Prom.ua, Amazon, ...) plug in without touching catalog code.

Phase 1: interface only — no marketplace API logic is implemented yet.
Concrete endpoints will be added in the Rozetka integration phase once the
authenticated seller documentation/credentials are available.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ChannelAdapter(ABC):
    """Contract every marketplace adapter must satisfy."""

    #: Stable channel code, e.g. "rozetka" (matches channels.code).
    channel_code: str

    @abstractmethod
    def refresh_taxonomy(self) -> Any:
        """Fetch/refresh the marketplace category & attribute dictionary
        into the local channel_external_* reference tables."""

    @abstractmethod
    def validate_product(self, product_id: int) -> list[dict]:
        """Local pre-flight validation.  Returns a list of issue dicts:
        [{"code": ..., "message": ..., "details": {...}}, ...] (empty = valid)."""

    @abstractmethod
    def transform_product(self, product_id: int) -> dict:
        """Map the internal product into this channel's representation.
        Must never mutate internal catalog data."""

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