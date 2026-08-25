"""Channel publication package.

Phase 1-3: channel foundation, taxonomy, mapping tables.
Phase 4: validation, transformation, mapping resolution.
Phase 5C: adapter interface cleaned up — adapter handles only
          transport/API operations; generic services are separate.
"""

from app.channels.base import (
    ChannelAdapter,
    RozetkaAdapter,
    get_adapter,
)
from app.channels.mapping_resolver import ChannelMappingResolver
from app.channels.validation import (
    validate_product,
    compute_content_hash,
    compute_commercial_hash,
)

__all__ = [
    "ChannelAdapter", "RozetkaAdapter", "get_adapter",
    "ChannelMappingResolver",
    "validate_product", "compute_content_hash", "compute_commercial_hash",
]