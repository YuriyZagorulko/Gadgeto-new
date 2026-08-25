"""Channel publication package.

Phase 1 contains only the adapter abstraction (`base`).  Taxonomy clients,
mapping services, validation/transformation and the sync engine arrive in
later phases.
"""

from app.channels.base import (
    ChannelAdapter,
    RozetkaAdapter,
    get_adapter,
)

__all__ = ["ChannelAdapter", "RozetkaAdapter", "get_adapter"]