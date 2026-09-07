"""Prom.ua marketplace adapter package (placeholder).

Prom.ua is prepared as a SECOND export channel, mirroring the Rozetka
adapter architecture.  The real Prom.ua API communication/authentication is
intentionally NOT implemented yet because there are no Prom.ua credentials or
API documentation in the project.

Everything here is safe when Prom.ua is simply not configured:
  * no startup failure — the application starts normally;
  * no automatic requests to Prom.ua;
  * every operation fails cleanly with ``PromNotConfiguredError``.
"""

from app.channels.prom.client import (
    PromApiClient,
    PromNotConfiguredError,
    PROM_NOT_CONFIGURED_MESSAGE,
    is_prom_configured,
    is_prom_enabled,
)
from app.channels.prom.api import PromAdapter
from app.channels.prom.taxonomy import PromTaxonomyService

__all__ = [
    "PromApiClient",
    "PromAdapter",
    "PromTaxonomyService",
    "PromNotConfiguredError",
    "PROM_NOT_CONFIGURED_MESSAGE",
    "is_prom_configured",
    "is_prom_enabled",
]