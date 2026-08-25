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

    def has_rules(self) -> bool:
        """True if any mapping rules are loaded."""
        return bool(self._cats or self._attrs or self._vals)