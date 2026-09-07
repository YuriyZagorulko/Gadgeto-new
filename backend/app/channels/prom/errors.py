"""Prom.ua channel error types.

The only errors introduced at this stage are configuration errors: the
application MUST start and work normally while Prom.ua is simply not
configured (no credentials / no API details yet).  All transport-specific
error types will be added together with the real Prom.ua API client.
"""

from __future__ import annotations

# Human-facing (Ukrainian) message returned to the admin when a Prom.ua
# operation is attempted while the integration is disabled / not configured.
PROM_NOT_CONFIGURED_MESSAGE = "Prom.ua integration is not configured."


class PromNotConfiguredError(LookupError):
    """Raised when a Prom.ua operation is attempted while the integration is
    not configured (disabled or missing credentials).

    It intentionally subclasses ``LookupError`` so existing registry lookups
    (e.g. ``app.channels.base.get_adapter``) keep raising a ``LookupError``
    for unknown / not-yet-syncable channels — the same way they do today.
    """

    def __init__(self, message: str = PROM_NOT_CONFIGURED_MESSAGE):
        super().__init__(message)