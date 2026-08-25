"""Rozetka marketplace adapter package.

Phase 5F: authentication.
Phase 5G: taxonomy synchronization.
Future phases: product creation, price/stock updates.
"""

from app.channels.rozetka.client import (
    RozetkaAuthClient,
    RozetkaAuthResult,
    RozetkaAuthError,
)
from app.channels.rozetka.taxonomy import (
    RozetkaTaxonomyService,
    RozetkaTaxonomyError,
)

__all__ = [
    "RozetkaAuthClient", "RozetkaAuthResult", "RozetkaAuthError",
    "RozetkaTaxonomyService", "RozetkaTaxonomyError",
]