"""Prom.ua product transformation layer (placeholder boundary).

Architecture (shared by every channel):

    Internal Product
           │
           ├── Rozetka Transformer → Rozetka Payload   (app/channels/rozetka/)
           │
           └── Prom Transformer    → Prom Payload      (THIS module)

The channel-neutral transformed representation is produced by the generic
service ``app.channels.transformer.transform_product`` / ``_build_transform_payload``.
This module provides the Prom.ua-specific **payload preparation boundary**:
``to_prom_payload()`` converts that neutral representation into the Prom.ua
wire format.

Because the exact Prom.ua payload fields/API are not known yet, we DO NOT
fabricate them.  ``to_prom_payload()`` currently raises a clear error so the
boundary exists but no invented contract is committed.
"""

from __future__ import annotations

from typing import Any, Optional

from app.channels.prom.client import (
    PROM_NOT_CONFIGURED_MESSAGE,
    is_prom_configured,
)
from app.channels.prom.errors import PromNotConfiguredError

_NOT_IMPLEMENTED = (
    "Prom.ua payload contract is a future implementation point — "
    "exact Prom fields are not known yet and are intentionally not invented."
)


def to_prom_payload(transformed: dict, *, attr_specs: Optional[dict] = None):
    """Convert a channel-neutral transformed product into a Prom.ua payload.

    ``transformed`` is the output of
    ``app.channels.validation._build_transform_payload`` (resolved mappings,
    normalized values, resolved price).

    Raises ``PromNotConfiguredError`` while the integration is not configured
    and ``NotImplementedError`` once configured but before the real payload
    builder is implemented.  Never fabricates Prom.ua field names.
    """
    if not is_prom_configured():
        raise PromNotConfiguredError(PROM_NOT_CONFIGURED_MESSAGE)
    raise NotImplementedError(_NOT_IMPLEMENTED)