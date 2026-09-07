"""Prom.ua-specific export validation (placeholder).

The generic channel validation (``app.channels.validation``) is shared and
channel-independent.  This module is the Prom.ua-specific extension point: it
mirrors ``app.channels.rozetka.rozetka_validation`` but, because Prom.ua is
not configured yet, it always reports the product as NOT ready with a single
clear error ("Prom.ua integration is not configured.").

When Prom.ua API documentation/credentials become available, extend this
function with Prom.ua-specific checks (category validity, required attributes,
value correctness, payload format) exactly like the Rozetka equivalent.
"""

from __future__ import annotations

from typing import Any, Optional

import psycopg2
import psycopg2.extras

from app.channels.prom.client import PROM_NOT_CONFIGURED_MESSAGE
from app.channels.validation import SEVERITY_ERROR
from app.core.db_connect import DB

PROM_NOT_CONFIGURED = "PROM_NOT_CONFIGURED"


def validate_prom_export(product_id: int,
                         channel_code: str = "prom",
                         channel_id: int = 0,
                         public_base_url: Optional[str] = None,
                         export_settings: Optional[dict] = None) -> dict:
    """Prom.ua-specific validation for one product.

    Current behaviour: always returns ``ready=False`` with a single
    application-level error because the Prom.ua integration is not configured.
    This guarantees no product can be exported to Prom.ua prematurely.
    """
    return {
        "ready": False,
        "category": None,
        "main_filters": {"total": 0, "mapped": 0, "unmapped": 0},
        "attributes": [],
        "issues": [{
            "code": PROM_NOT_CONFIGURED,
            "severity": SEVERITY_ERROR,
            "message": PROM_NOT_CONFIGURED_MESSAGE,
            "details": {"channel": channel_code},
        }],
    }