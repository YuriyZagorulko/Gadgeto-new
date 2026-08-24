"""
Database-backed mapping resolution for supplier imports.

Priority (highest first):
    1. supplier-specific mapping   (supplier_attributes.supplier_id = <sid>)
    2. global mapping              (supplier_id IS NULL)
    3. fallback                    (legacy JSON behaviour / pass-through)

The resolver preloads every rule once per importer run, so resolution cost is
in-memory — same model the legacy JSON loader used.
"""

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB


class MappingResolver:
    """Preloaded view of the three mapping tables scoped to one supplier."""

    def __init__(self, supplier_code: str):
        self.supplier_code = supplier_code
        # raw_attr(lower) -> {internal_name, active}
        self.attrs: dict = {}
        # (internal_attr_lower, raw_value_lower) -> {value_name, active}
        self.values: dict = {}
        # raw_category(lower) -> {category_id, internal_name, active}
        self.cats: dict = {}
        self._load()

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """SELECT sa.supplier_name AS raw, m.is_active,
                          m.attribute_id, a.name AS internal_name,
                          (sa.supplier_id IS NOT NULL) AS specific
                   FROM attribute_mappings m
                   JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
                   LEFT JOIN suppliers s ON s.id = sa.supplier_id
                   LEFT JOIN attributes a ON a.id = m.attribute_id
                   WHERE sa.supplier_id IS NULL OR s.code = %s""",
                (self.supplier_code,),
            )
            for r in cur.fetchall():
                key = r["raw"].strip()
                prev = self.attrs.get(key)
                # specific rows are applied after global ones -> they win
                if prev is not None and prev["specific"] and not r["specific"]:
                    continue
                self.attrs[key] = {
                    "internal_name": r["internal_name"],
                    "active": r["is_active"],
                    "specific": r["specific"],
                }

            cur.execute(
                """SELECT ha.supplier_name AS holder, sav.supplier_value AS raw_value,
                          m.is_active, m.attribute_value_id, av.value AS value_name,
                          (ha.supplier_id IS NOT NULL) AS specific
                   FROM attribute_value_mappings m
                   JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
                   JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
                   LEFT JOIN suppliers s ON s.id = ha.supplier_id
                   LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
                   WHERE ha.supplier_id IS NULL OR s.code = %s""",
                (self.supplier_code,),
            )
            for r in cur.fetchall():
                key = (r["holder"].strip(), r["raw_value"].strip())
                prev = self.values.get(key)
                if prev is not None and prev["specific"] and not r["specific"]:
                    continue
                entry = {
                    "value_name": r["value_name"],
                    "active": r["is_active"],
                    "specific": r["specific"],
                }
                self.values[key] = entry

            cur.execute(
                """SELECT sc.supplier_name AS raw, m.is_active,
                          m.category_id, c.name AS internal_name,
                          (sc.supplier_id IS NOT NULL) AS specific
                   FROM category_mappings m
                   JOIN supplier_categories sc ON sc.id = m.supplier_category_id
                   LEFT JOIN suppliers s ON s.id = sc.supplier_id
                   LEFT JOIN categories c ON c.id = m.category_id
                   WHERE sc.supplier_id IS NULL OR s.code = %s""",
                (self.supplier_code,),
            )
            for r in cur.fetchall():
                key = r["raw"].strip()
                prev = self.cats.get(key)
                if prev is not None and prev["specific"] and not r["specific"]:
                    continue
                self.cats[key] = {
                    "category_id": r["category_id"],
                    "internal_name": r["internal_name"],
                    "active": r["is_active"],
                    "specific": r["specific"],
                }
        finally:
            conn.close()

    # ------------------------------------------------------------- public API
    def has_rules(self) -> bool:
        """False => caller should fall back to the legacy JSON pipeline."""
        return bool(self.attrs or self.values or self.cats)

    def process_attribute(self, supplier_name: str, supplier_value: str):
        """Same contract as attribute_processor.process_attribute()."""
        from app.imports.attribute_processor import (
            ATTR_SKIP, ATTR_UNKNOWN_NAME, ATTR_UNKNOWN_VALUE,
        )
        name = (supplier_name or "").strip()
        value = str(supplier_value or "").strip()
        if not name or not value:
            return ATTR_SKIP

        entry = self.attrs.get(name)
        if entry is None:
            return ATTR_UNKNOWN_NAME
        if not entry["active"] or entry["internal_name"] is None:
            return ATTR_SKIP
        internal = entry["internal_name"]

        # BUGFIX: use the supplier attribute name (not internal name) for the value
        # lookup key, because self.values is keyed by (supplier_attr, raw_value).
        # When supplier_name != internal_name (e.g. "Цвет" → "Колір",
        # "Формфактор" → "Форм-фактор"), using internal_name caused every
        # value-level mapping to be invisible → "UNKNOWN_VALUE" for every product.
        key = (name.strip(), value)
        ventry = self.values.get(key)
        if ventry is not None:
            if not ventry["active"]:
                return ATTR_SKIP
            # active but unresolved target -> pass raw value through (no data loss)
            return (internal, ventry["value_name"] or value)
        # No value-level mapping found for this attribute+value combination.
        # If the attribute participates in the value allowlist (has >=1 active
        # value rule) AND this specific value is not in the list -> unknown.
        # If the attribute has NO value-level mappings at all, the raw value
        # was previously passed through, which silently created internal values
        # for every supplier variant.  This behaviour is now disabled: every
        # unmapped value is treated as unknown so that it is dropped and logged
        # instead of auto-creating catalog entries.
        return ATTR_UNKNOWN_VALUE

    def build_category_map(self) -> dict:
        """{raw_category: internal_category_name} for active, resolved rows."""
        return {
            raw_entry_raw: entry["internal_name"]
            for raw_entry_raw, entry in (
                (raw, e) for raw, e in self.cats.items()
            )
            if entry["active"] and entry["internal_name"]
        }

    @staticmethod
    def category_map_for(supplier_code: str) -> "dict | None":
        """Convenience: DB-derived map, or None when the DB holds no rules."""
        try:
            resolver = MappingResolver(supplier_code)
        except Exception:
            return None
        if not resolver.cats:
            return None
        return resolver.build_category_map()

