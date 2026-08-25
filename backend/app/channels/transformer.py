"""Channel product transformation service.

Converts an internal Product into a channel-neutral export representation
with resolved mappings.  This is a deterministic transformation that does
not mutate the internal catalog.

The output is an internal export representation, NOT the final marketplace
API payload.  The adapter layer (Phase 5) converts this to the specific
API format.
"""

from app.channels.mapping_resolver import ChannelMappingResolver
from app.channels.validation import _build_transform_payload


def transform_product(
    product_id: int,
    channel_code: str = "rozetka",
    public_base_url: str | None = None,
) -> dict:
    """Transform an internal product into a channel-ready export representation.

    Returns a dict with resolved mappings and normalized data.
    Raises LookupError if the product or channel is not found.
    """
    import psycopg2
    import psycopg2.extras
    from app.core.db_connect import DB
    from app.channels.validation import _load_product_data, _get_channel_id, _get_external_category_id

    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        channel_id = _get_channel_id(cur, channel_code)
        if channel_id is None:
            raise LookupError(f"Channel '{channel_code}' not found")

        product = _load_product_data(cur, product_id)
        if product is None:
            raise LookupError(f"Product {product_id} not found")

        resolver = ChannelMappingResolver(channel_id=channel_id, channel_code=channel_code)
        ext_cat_id = _get_external_category_id(resolver, product)

        return _build_transform_payload(product, resolver, ext_cat_id, public_base_url)
    finally:
        conn.close()