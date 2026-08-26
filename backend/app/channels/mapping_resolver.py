"""Channel mapping resolver — Internal → External Channel.

This resolver is the counterpart of the supplier-importer MappingResolver but
with the opposite direction: internal catalog entities resolve to external
channel taxonomy entities.

The resolver is deterministic.  No fuzzy matching happens during export
resolution; fuzzy matching/suggestions belong to the mapping UI phase.

Rozetka attributes are category-dependent, so the resolver supports
category-scoped attribute lookups.
"""

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB


class ChannelMappingResolver:
    """Preloaded view of the three channel mapping tables for one channel.

    Usage:
        resolver = ChannelMappingResolver(channel_id=1, channel_code='rozetka')
        cat = resolver.resolve_category(internal_category_id=42)
        attr = resolver.resolve_attribute(internal_attribute_id=10, external_category_id='123')
        val = resolver.resolve_value(internal_value_id=100, external_category_id='123')
        # Value resolution by text (when attribute_value_id is not set):
        val = resolver.resolve_value_by_text(attribute_id=10, value_text='4 вентилятори', ext_cat_id='123')
    """

    def __init__(self, channel_id: int, channel_code: str = "rozetka"):
        self.channel_id = channel_id
        self.channel_code = channel_code
        # {internal_category_id: {external_category_id, external_category_name, status, ...}}
        self._cats: dict[int, dict] = {}
        # {(internal_attribute_id, external_category_id): {external_attribute_id, ...}}
        self._attrs: dict[tuple, dict] = {}
        # {(internal_value_id, external_category_id): {external_value_id, ...}}
        self._vals: dict[tuple, dict] = {}
        # {(attribute_id, value_text): attribute_value_id} — preloaded bridge lookup
        self._value_text_ids: dict[tuple, int] = {}
        self._load()

    # ------------------------------------------------------------------ load

    def _load(self) -> None:
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            # Categories
            cur.execute(
                """SELECT internal_category_id, external_category_id,
                          external_category_name, status, confidence
                   FROM channel_category_mappings
                   WHERE channel_id = %s AND status = 'accepted'""",
                (self.channel_id,),
            )
            for r in cur.fetchall():
                self._cats[r["internal_category_id"]] = dict(r)

            # Attributes
            cur.execute(
                """SELECT internal_attribute_id, external_attribute_id,
                          external_attribute_name, external_category_id,
                          status, confidence
                   FROM channel_attribute_mappings
                   WHERE channel_id = %s AND status = 'accepted'""",
                (self.channel_id,),
            )
            for r in cur.fetchall():
                key = (r["internal_attribute_id"], r["external_category_id"])
                self._attrs[key] = dict(r)

            # Values
            cur.execute(
                """SELECT internal_value_id, external_value_id,
                          external_value_name, external_category_id,
                          status, confidence
                   FROM channel_value_mappings
                   WHERE channel_id = %s AND status = 'accepted'""",
                (self.channel_id,),
            )
            for r in cur.fetchall():
                key = (r["internal_value_id"], r["external_category_id"])
                self._vals[key] = dict(r)

            # Value-text bridge: preload (attribute_id, value_text) -> attribute_value_id
            # for all attributes that have channel mappings, enabling O(1) text lookup.
            cur.execute(
                """SELECT av.attribute_id, av.value AS value_text, av.id AS av_id
                   FROM attribute_values av
                   JOIN channel_attribute_mappings cam
                     ON cam.internal_attribute_id = av.attribute_id
                   WHERE cam.channel_id = %s AND cam.status = 'accepted'""",
                (self.channel_id,),
            )
            for r in cur.fetchall():
                key = (r["attribute_id"], r["value_text"])
                self._value_text_ids[key] = r["av_id"]
        finally:
            conn.close()

    # ------------------------------------------------------------- public API

    def resolve_category(self, internal_category_id: int) -> dict | None:
        """Return the accepted external category mapping, or None."""
        return self._cats.get(internal_category_id)

    def resolve_attribute(
        self, internal_attribute_id: int, external_category_id: str | None = None,
    ) -> dict | None:
        """Resolve an internal attribute to its external counterpart.

        When external_category_id is provided, the lookup is category-scoped
        (Rozetka characteristics are category-dependent).  Falls back to a
        global (NULL external_category_id) mapping if no category-specific
        mapping is found.
        """
        if external_category_id is not None:
            result = self._attrs.get((internal_attribute_id, external_category_id))
            if result is not None:
                return result
        # Fallback: global attribute mapping (no category scope)
        return self._attrs.get((internal_attribute_id, None))

    def resolve_value(
        self, internal_value_id: int, external_category_id: str | None = None,
    ) -> dict | None:
        """Resolve an internal attribute value to its external counterpart.

        Supports category-scoped lookup with fallback to global mapping.
        """
        if external_category_id is not None:
            result = self._vals.get((internal_value_id, external_category_id))
            if result is not None:
                return result
        return self._vals.get((internal_value_id, None))

    def resolve_value_by_text(
        self, attribute_id: int, value_text: str,
        external_category_id: str | None = None,
    ) -> dict | None:
        """Resolve a text value (product_attributes.value_text) to its external
        counterpart via the intermediate attribute_values bridge.

        This enables value resolution for product attributes that store values
        as free text rather than as foreign keys to attribute_values.

        Resolution chain:
            (attribute_id, value_text) → attribute_values.id → channel_value_mappings → Rozetka

        Returns the external mapping dict (with external_value_id, external_value_name)
        or None if no mapping exists.
        """
        av_id = self._value_text_ids.get((attribute_id, value_text))
        if av_id is None:
            return None
        return self.resolve_value(av_id, external_category_id)

    def has_rules(self) -> bool:
        """True if any mapping rules are loaded."""
        return bool(self._cats or self._attrs or self._vals)