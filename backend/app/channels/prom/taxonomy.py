"""Prom.ua taxonomy synchronization service (placeholder).

Mirrors the ``TaxonomyService`` contract used by the generic channel taxonomy
layer (see ``app/channels/taxonomy.py``).  Since there are no Prom.ua
credentials/API docs yet, a refresh always fails cleanly with
``PromNotConfiguredError`` — no HTTP request is made and no taxonomy is
written.

When Prom.ua credentials/API documentation become available, implement the
real fetch here (categories, attributes, values) and persist it into the
existing ``channel_external_*`` tables keyed by the prom channel_id.
"""

from __future__ import annotations

from typing import Optional

from app.channels.prom.client import (
    PROM_NOT_CONFIGURED_MESSAGE,
    is_prom_configured,
)
from app.channels.prom.errors import PromNotConfiguredError
from app.channels.taxonomy import TaxonomyService

_NOT_IMPLEMENTED = (
    "Prom.ua taxonomy sync is a future implementation point — "
    "real communication is not implemented yet."
)


class PromTaxonomyService(TaxonomyService):
    """Prom.ua implementation of the channel taxonomy contract."""

    def refresh(self, channel_id: int, channel_code: str = "prom",
                progress_cb=None) -> dict:
        if not is_prom_configured():
            raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)
        raise NotImplementedError(_NOT_IMPLEMENTED)


def get_prom_taxonomy_service() -> PromTaxonomyService:
    return PromTaxonomyService()