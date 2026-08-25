"""Channel taxonomy service.

Fetches and persists the marketplace's category/attribute/value dictionary
(local reference data).  The first channel is Rozetka; the interface is
channel-agnostic for future marketplaces.

Phase 2 limitation: the official Rozetka Seller API documentation is behind
the authenticated seller portal and real credentials are not available yet.
The concrete HTTP logic is therefore stubbed — the storage layer, service
interface, and admin action are fully implemented so that when credentials
become available only the adapter's `refresh_taxonomy` method needs filling.
"""

from abc import ABC, abstractmethod
from typing import Optional

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB


class TaxonomyService(ABC):
    """Contract for refreshing a channel's taxonomy dictionary."""

    @abstractmethod
    def refresh(self, channel_id: int, channel_code: str) -> dict:
        """Fetch the full taxonomy from the marketplace API and persist.
        Returns a stats dict:
          {categories_created, categories_updated, categories_removed,
           attributes_created, attributes_updated,
           values_created, values_updated,
           errors, duration_seconds}"""


from app.channels.rozetka.taxonomy import RozetkaTaxonomyService as _RozetkaTaxonomyService, RozetkaTaxonomyError

class RozetkaTaxonomyService(TaxonomyService):
    """Rozetka implementation.

    Fetches the full Rozetka taxonomy using the official Seller API
    and persists it into the channel_external_* tables.
    """

    def refresh(self, channel_id: int, channel_code: str) -> dict:
        svc = _RozetkaTaxonomyService()
        return svc.refresh(channel_id=channel_id, channel_code=channel_code)


def get_taxonomy_service(channel_code: str) -> TaxonomyService:
    registry = {
        "rozetka": RozetkaTaxonomyService,
    }
    cls = registry.get(channel_code)
    if cls is None:
        raise LookupError(f"Немає сервісу таксономії для каналу '{channel_code}'")
    return cls()


def get_taxonomy_stats(cur, channel_id: int) -> dict:
    """Return current taxonomy counts for a channel (independent of API)."""
    cur.execute(
        "SELECT count(*) FROM channel_external_categories WHERE channel_id = %s",
        (channel_id,),
    )
    categories = cur.fetchone()["c"]

    cur.execute(
        "SELECT count(*) FROM channel_external_attributes WHERE channel_id = %s",
        (channel_id,),
    )
    attributes = cur.fetchone()["c"]

    cur.execute(
        "SELECT count(*) FROM channel_external_values WHERE channel_id = %s",
        (channel_id,),
    )
    values = cur.fetchone()["c"]

    return {"categories": categories, "attributes": attributes, "values": values}