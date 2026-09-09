"""
Database-backed mapping resolution for supplier imports.

Priority (highest first):
    1. external-ID mapping (supplier attribute/value ID from the feed)
    2. category-specific supplier mapping   (attribute_mappings.category_id = X)
    3. supplier-specific mapping            (supplier_attributes.supplier_id = <sid>)
    4. global mapping                       (supplier_id IS NULL)

External-ID resolution rules (per supplier capability):
  - Brain:       supplier_id + external_id   (category, attribute, value)
  - DC-Link:     supplier_id + external_id   (category, attribute, value)
  - IT-Link:     category: supplier_id + external_id;  attr/value: name-based (no stable IDs)

When an external ID is provided to the resolver, it is the primary identity.
Name-based resolution is ONLY used when:
  - the supplier does not provide stable IDs (IT-Link attributes/values), OR
  - the caller explicitly resolves by name (backward-compatible path).

The resolver preloads every rule once per importer run, so resolution cost is
in-memory -- same model the legacy JSON loader used.
"""

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB


class MappingResolver:
    """Preloaded view of the three mapping tables scoped to one supplier."""

    def __init__(self, supplier_code: str):
        self.supplier_code = supplier_code
        # Name-based maps (backward compat, used by IT-Link attr/value)
        self.attrs: dict = {}          # raw_name or (name, category_id) -> entry
        self.values: dict = {}         # (holder_name, raw_value) -> entry
        self.cats: dict = {}           # raw_name -> entry
        # External-ID maps (ID-first)
        self.attrs_by_ext: dict = {}   # external_id -> entry
        self.values_by_ext: dict = {}  # (sa_id, external_id) -> entry
        self.cats_by_ext: dict = {}    # external_id -> entry
        self._load()

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            # -- attributes -------------------------------------------------
            cur.execute(
                """SELECT sa.id AS sa_id, sa.supplier_name AS raw,
                          sa.external_id,
                          m.is_active, m.attribute_id,
                          a.name AS internal_name, m.category_id,
                          (sa.supplier_id IS NOT NULL) AS specific
                   FROM attribute_mappings m
                   JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
                   LEFT JOIN suppliers s ON s.id = sa.supplier_id
                   LEFT JOIN attributes a ON a.id = m.attribute_id
                   WHERE sa.supplier_id IS NULL OR s.code = %s""",
                (self.supplier_code,),
            )
            for r in cur.fetchall():
                raw_name = r["raw"].strip()
                cat_id = r["category_id"]
                if cat_id is not None:
                    key = (raw_name, cat_id)
                else:
                    key = raw_name
                prev = self.attrs.get(key)
                if prev is not None and prev["specific"] and not r["specific"]:
                    continue
                entry = {
                    "sa_id": r["sa_id"],
                    "internal_name": r["internal_name"],
                    "active": r["is_active"],
                    "specific": r["specific"],
                    "category_id": cat_id,
                }
                self.attrs[key] = entry
                if cat_id is None and raw_name not in self.attrs:
                    self.attrs[raw_name] = entry

                # External-ID map: specific wins over global
                ext_id = r["external_id"]
                if ext_id is not None:
                    ext_id = ext_id.strip()
                    if ext_id:
                        prev_ext = self.attrs_by_ext.get(ext_id)
                        if prev_ext is None or (r["specific"] and not prev_ext.get("specific")):
                            self.attrs_by_ext[ext_id] = entry

            # -- values -----------------------------------------------------
            cur.execute(
                """SELECT ha.id AS sa_id, ha.supplier_name AS holder,
                          ha.external_id AS holder_external_id,
                          sav.id AS sav_id, sav.supplier_value AS raw_value,
                          sav.external_id,
                          m.is_active, m.attribute_value_id,
                          av.value AS value_name,
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
                holder = r["holder"].strip()
                raw_val = r["raw_value"].strip()
                key = (holder, raw_val)
                prev = self.values.get(key)
                if prev is not None and prev["specific"] and not r["specific"]:
                    continue
                ventry = {
                    "sav_id": r["sav_id"],
                    "value_name": r["value_name"],
                    "active": r["is_active"],
                    "specific": r["specific"],
                    "sa_id": r["sa_id"],
                }
                self.values[key] = ventry

                # External-ID map for value: (sa_id, external_id) -> entry
                val_ext = r["external_id"]
                if val_ext is not None:
                    val_ext = val_ext.strip()
                    if val_ext:
                        vk = (r["sa_id"], val_ext)
                        prev_ext = self.values_by_ext.get(vk)
                        if prev_ext is None or (r["specific"] and not prev_ext.get("specific")):
                            self.values_by_ext[vk] = ventry

            # -- categories ------------------------------------------------
            cur.execute(
                """SELECT sc.id AS sc_id, sc.supplier_name AS raw,
                          sc.external_id,
                          m.is_active, m.category_id,
                          c.name AS internal_name,
                          (sc.supplier_id IS NOT NULL) AS specific
                   FROM category_mappings m
                   JOIN supplier_categories sc ON sc.id = m.supplier_category_id
                   LEFT JOIN suppliers s ON s.id = sc.supplier_id
                   LEFT JOIN categories c ON c.id = m.category_id
                   WHERE sc.supplier_id IS NULL OR s.code = %s""",
                (self.supplier_code,),
            )
            for r in cur.fetchall():
                raw_name = r["raw"].strip()
                prev = self.cats.get(raw_name)
                if prev is not None and prev["specific"] and not r["specific"]:
                    continue
                centry = {
                    "sc_id": r["sc_id"],
                    "category_id": r["category_id"],
                    "internal_name": r["internal_name"],
                    "active": r["is_active"],
                    "specific": r["specific"],
                }
                self.cats[raw_name] = centry

                # External-ID map for category
                ext_id = r["external_id"]
                if ext_id is not None:
                    ext_id = ext_id.strip()
                    if ext_id:
                        prev_ext = self.cats_by_ext.get(ext_id)
                        if prev_ext is None or (r["specific"] and not prev_ext.get("specific")):
                            self.cats_by_ext[ext_id] = centry
        finally:
            conn.close()

    # ------------------------------------------------------------- public API
    def has_rules(self) -> bool:
        """False => caller should fall back to the legacy JSON pipeline."""
        return bool(self.attrs or self.values or self.cats)

    def resolve_category(self, external_id: str | None = None,
                         name: str | None = None) -> str | None:
        """Resolve a supplier category to an internal category name.

        Args:
            external_id: Supplier's stable category ID.
            name: Supplier category name (used when external_id is absent).

        Returns:
            Internal category name, or None if the source category is unmapped.
        """
        # ID-first: external_id provided -> resolve by ID only
        if external_id is not None and str(external_id).strip():
            eid = str(external_id).strip()
            entry = self.cats_by_ext.get(eid)
            if entry is not None and entry["active"] and entry["internal_name"]:
                return entry["internal_name"]
            return None  # ID expected but no mapping -> unmapped

        # Name-based fallback (IT-Link categories, or backward compat)
        if name is not None:
            key = name.strip()
            entry = self.cats.get(key)
            if entry is not None and entry["active"] and entry["internal_name"]:
                return entry["internal_name"]
        return None

    def process_attribute(self, supplier_name: str, supplier_value: str,
                          category_id: int | None = None,
                          supplier_attr_external_id: str | None = None,
                          supplier_value_external_id: str | None = None):
        """Resolve a supplier attribute to an internal attribute name.

        External-ID resolution (Brain/DC-Link):
          - supplier_attr_external_id provided -> resolve by ID only.
          - If not found -> ATTR_UNKNOWN_NAME (no name fallback).

        Name-based resolution (IT-Link attr/value):
          - supplier_attr_external_id is None -> existing name-based logic.

        Returns:
            (internal_name, internal_value)  -- successful mapping.
            ATTR_SKIP                        -- skip this attribute.
            ATTR_UNKNOWN_NAME                -- attribute name not mapped.
            ATTR_UNKNOWN_VALUE               -- attribute known but value not mapped.
        """
        from app.imports.attribute_processor import (
            ATTR_SKIP, ATTR_UNKNOWN_NAME, ATTR_UNKNOWN_VALUE,
        )
        name = (supplier_name or "").strip()
        value = str(supplier_value or "").strip()
        if not name or not value:
            return ATTR_SKIP

        # -- Attribute resolution ------------------------------------------
        entry = None

        # Priority 1: external-ID resolution (when ID provided)
        if supplier_attr_external_id is not None and str(supplier_attr_external_id).strip():
            eid = str(supplier_attr_external_id).strip()
            entry = self.attrs_by_ext.get(eid)
            if entry is None:
                return ATTR_UNKNOWN_NAME  # ID expected but no mapping -> unmapped

        # Priority 2: category-specific mapping (name-based)
        if entry is None and category_id is not None:
            entry = self.attrs.get((name, category_id))

        # Priority 3: global name-based mapping
        if entry is None:
            entry = self.attrs.get(name)

        if entry is None:
            return ATTR_UNKNOWN_NAME
        if not entry["active"] or entry["internal_name"] is None:
            return ATTR_SKIP
        internal = entry["internal_name"]

        # -- Value resolution ------------------------------------------------
        ventry = None

        # Priority 1: value external-ID resolution
        if supplier_value_external_id is not None and str(supplier_value_external_id).strip():
            veid = str(supplier_value_external_id).strip()
            sa_id = entry.get("sa_id")
            if sa_id:
                ventry = self.values_by_ext.get((sa_id, veid))
            if ventry is None:
                return ATTR_UNKNOWN_VALUE  # ID expected but no value mapping

        # Priority 2: name-based value resolution
        if ventry is None:
            key = (name, value)
            ventry = self.values.get(key)

        if ventry is not None:
            if not ventry["active"]:
                return ATTR_SKIP
            return (internal, ventry["value_name"] or value)
        return ATTR_UNKNOWN_VALUE

    def build_category_map(self) -> dict:
        """{raw_category: internal_category_name} for active, resolved rows."""
        return {
            raw: entry["internal_name"]
            for raw, entry in self.cats.items()
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
