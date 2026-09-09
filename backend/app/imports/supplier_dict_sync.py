"""Idempotent supplier dictionary synchronisation with external-ID support.

Ensures that supplier_categories / supplier_attributes / supplier_attribute_values
rows exist with the correct external_id before the import pipeline creates
mappings against them.

This module:
  - NEVER creates or modifies mappings.
  - NEVER modifies Gadgeto catalog data.
  - Uses per-run caches to avoid redundant DB round-trips.
  - Is idempotent: re-running on the same data is a no-op.

The primary identity for a row is:
  1. (supplier_id, external_id)     -- when external_id is provided (ID-capable).
  2. (supplier_id, name)  -- fallback for name-based lookup (IT-Link attribute/value).
"""

from typing import Optional

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB


class SupplierDictSync:
    """Idempotent upsert of supplier dictionary rows with external IDs.

    One instance per import run: caches lookups so repeated calls for the same
    (supplier_id, external_id) pair are resolved in memory.
    """

    def __init__(self, supplier_code: str):
        self.supplier_code = supplier_code
        self._supplier_id: Optional[int] = None
        # Category cache: external_id -> sc_id
        self._cat_cache: dict[str, int] = {}
        # Attribute cache: external_id -> sa_id
        self._attr_cache: dict[str, int] = {}
        # Value cache: (sa_id, external_id) -> sav_id
        self._val_cache: dict[tuple, int] = {}
        # Name-based fallback caches
        self._cat_by_name: dict[str, int] = {}
        self._attr_by_name: dict[str, int] = {}
        self._val_by_key: dict[tuple, int] = {}  # (sa_id, name) -> sav_id

    def _get_supplier_id(self, conn, cur) -> int:
        if self._supplier_id is None:
            cur.execute("SELECT id FROM suppliers WHERE code = %s", (self.supplier_code,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Supplier {self.supplier_code} not found")
            self._supplier_id = row["id"]
        return self._supplier_id

    # ------------------------------------------------------------------ category
    def sync_category(self, external_id: Optional[str], name: str) -> Optional[int]:
        """Upsert a supplier_categories row.

        Returns the supplier_categories.id (either existing or newly created).
        """
        # ID-first lookup
        if external_id is not None and str(external_id).strip():
            eid = str(external_id).strip()
            if eid in self._cat_cache:
                return self._cat_cache[eid]
            conn = psycopg2.connect(DB)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                sid = self._get_supplier_id(conn, cur)
                # Try by (supplier_id, external_id)
                cur.execute(
                    "SELECT id, supplier_name FROM supplier_categories WHERE supplier_id=%s AND external_id=%s",
                    (sid, eid),
                )
                row = cur.fetchone()
                if row:
                    sc_id = row["id"]
                    # Update name if it changed (source name change tracking)
                    if row["supplier_name"] != name:
                        cur.execute(
                            "UPDATE supplier_categories SET supplier_name=%s, updated_at=NOW() WHERE id=%s",
                            (name, sc_id),
                        )
                        conn.commit()
                    self._cat_cache[eid] = sc_id
                    return sc_id
                # Try by (supplier_id, name) with no external_id -> backfill
                cur.execute(
                    "SELECT id, external_id FROM supplier_categories WHERE supplier_id=%s AND supplier_name=%s",
                    (sid, name),
                )
                row = cur.fetchone()
                if row:
                    sc_id = row["id"]
                    if row["external_id"] is None:
                        cur.execute(
                            "UPDATE supplier_categories SET external_id=%s, updated_at=NOW() WHERE id=%s",
                            (eid, sc_id),
                        )
                        conn.commit()
                    self._cat_cache[eid] = sc_id
                    return sc_id
                # Insert new
                cur.execute(
                    """INSERT INTO supplier_categories
                       (supplier_id, external_id, supplier_name, is_removed, created_at, updated_at)
                       VALUES (%s, %s, %s, FALSE, NOW(), NOW())
                       RETURNING id""",
                    (sid, eid, name),
                )
                sc_id = cur.fetchone()["id"]
                conn.commit()
                self._cat_cache[eid] = sc_id
                return sc_id
            finally:
                conn.close()

        # Name-based fallback (IT-Link category)
        key = name.strip()
        if key in self._cat_by_name:
            return self._cat_by_name[key]
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            sid = self._get_supplier_id(conn, cur)
            cur.execute(
                "SELECT id FROM supplier_categories WHERE supplier_id=%s AND supplier_name=%s",
                (sid, key),
            )
            row = cur.fetchone()
            if row:
                self._cat_by_name[key] = row["id"]
                return row["id"]
            cur.execute(
                """INSERT INTO supplier_categories
                   (supplier_id, external_id, supplier_name, is_removed, created_at, updated_at)
                   VALUES (%s, NULL, %s, FALSE, NOW(), NOW())
                   RETURNING id""",
                (sid, key),
            )
            sc_id = cur.fetchone()["id"]
            conn.commit()
            self._cat_by_name[key] = sc_id
            return sc_id
        finally:
            conn.close()

    # ------------------------------------------------------------------ attribute
    def sync_attribute(self, external_id: Optional[str], name: str) -> Optional[int]:
        """Upsert a supplier_attributes row.

        Returns the supplier_attributes.id.
        """
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            sid = self._get_supplier_id(conn, cur)

            if external_id is not None and str(external_id).strip():
                eid = str(external_id).strip()
                if eid in self._attr_cache:
                    return self._attr_cache[eid]
                # Try by (supplier_id, external_id)
                cur.execute(
                    "SELECT id, supplier_name FROM supplier_attributes WHERE supplier_id=%s AND external_id=%s",
                    (sid, eid),
                )
                row = cur.fetchone()
                if row:
                    sa_id = row["id"]
                    # Update name if it changed (source name change tracking)
                    if row["supplier_name"] != name:
                        cur.execute(
                            "UPDATE supplier_attributes SET supplier_name=%s, updated_at=NOW() WHERE id=%s",
                            (name, sa_id),
                        )
                        conn.commit()
                    self._attr_cache[eid] = sa_id
                    return sa_id
                # Try by (supplier_id, name) -> backfill external_id
                cur.execute(
                    "SELECT id, external_id FROM supplier_attributes WHERE supplier_id=%s AND supplier_name=%s",
                    (sid, name),
                )
                row = cur.fetchone()
                if row:
                    sa_id = row["id"]
                    if row["external_id"] is None:
                        cur.execute(
                            "UPDATE supplier_attributes SET external_id=%s, updated_at=NOW() WHERE id=%s",
                            (eid, sa_id),
                        )
                        conn.commit()
                    self._attr_cache[eid] = sa_id
                    return sa_id
                # Insert new
                cur.execute(
                    """INSERT INTO supplier_attributes
                       (supplier_id, external_id, supplier_name, is_removed, created_at, updated_at)
                       VALUES (%s, %s, %s, FALSE, NOW(), NOW())
                       RETURNING id""",
                    (sid, eid, name),
                )
                sa_id = cur.fetchone()["id"]
                conn.commit()
                self._attr_cache[eid] = sa_id
                return sa_id

            # Name-based fallback (IT-Link)
            key = name.strip()
            if key in self._attr_by_name:
                return self._attr_by_name[key]
            cur.execute(
                "SELECT id FROM supplier_attributes WHERE supplier_id=%s AND supplier_name=%s",
                (sid, key),
            )
            row = cur.fetchone()
            if row:
                self._attr_by_name[key] = row["id"]
                return row["id"]
            cur.execute(
                """INSERT INTO supplier_attributes
                   (supplier_id, external_id, supplier_name, is_removed, created_at, updated_at)
                   VALUES (%s, NULL, %s, FALSE, NOW(), NOW())
                   RETURNING id""",
                (sid, key),
            )
            sa_id = cur.fetchone()["id"]
            conn.commit()
            self._attr_by_name[key] = sa_id
            return sa_id
        finally:
            conn.close()

    # ------------------------------------------------------------------ value
    def sync_value(self, supplier_attribute_id: int, external_id: Optional[str],
                   value: str) -> Optional[int]:
        """Upsert a supplier_attribute_values row.

        Args:
            supplier_attribute_id: The supplier_attributes.id (parent).
            external_id: Stable value ID from the supplier.
            value: The display value text.
        """
        conn = psycopg2.connect(DB)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if external_id is not None and str(external_id).strip():
                eid = str(external_id).strip()
                vk = (supplier_attribute_id, eid)
                if vk in self._val_cache:
                    return self._val_cache[vk]
                # Try by (supplier_attribute_id, external_id)
                cur.execute(
                    "SELECT id, supplier_value FROM supplier_attribute_values WHERE supplier_attribute_id=%s AND external_id=%s",
                    (supplier_attribute_id, eid),
                )
                row = cur.fetchone()
                if row:
                    sav_id = row["id"]
                    # Update value if it changed (source name change tracking)
                    if row["supplier_value"] != value:
                        cur.execute(
                            "UPDATE supplier_attribute_values SET supplier_value=%s, updated_at=NOW() WHERE id=%s",
                            (value, sav_id),
                        )
                        conn.commit()
                    self._val_cache[vk] = sav_id
                    return sav_id
                # Try by (supplier_attribute_id, supplier_value) -> backfill
                cur.execute(
                    "SELECT id, external_id FROM supplier_attribute_values WHERE supplier_attribute_id=%s AND supplier_value=%s",
                    (supplier_attribute_id, value),
                )
                row = cur.fetchone()
                if row:
                    sav_id = row["id"]
                    if row["external_id"] is None:
                        cur.execute(
                            "UPDATE supplier_attribute_values SET external_id=%s, updated_at=NOW() WHERE id=%s",
                            (eid, sav_id),
                        )
                        conn.commit()
                    self._val_cache[vk] = sav_id
                    return sav_id
                # Insert new
                cur.execute(
                    """INSERT INTO supplier_attribute_values
                       (supplier_attribute_id, external_id, supplier_value, is_removed, created_at, updated_at)
                       VALUES (%s, %s, %s, FALSE, NOW(), NOW())
                       RETURNING id""",
                    (supplier_attribute_id, eid, value),
                )
                sav_id = cur.fetchone()["id"]
                conn.commit()
                self._val_cache[vk] = sav_id
                return sav_id

            # Name-based fallback
            key = (supplier_attribute_id, value.strip())
            if key in self._val_by_key:
                return self._val_by_key[key]
            cur.execute(
                "SELECT id FROM supplier_attribute_values WHERE supplier_attribute_id=%s AND supplier_value=%s",
                (supplier_attribute_id, value.strip()),
            )
            row = cur.fetchone()
            if row:
                self._val_by_key[key] = row["id"]
                return row["id"]
            cur.execute(
                """INSERT INTO supplier_attribute_values
                   (supplier_attribute_id, external_id, supplier_value, is_removed, created_at, updated_at)
                   VALUES (%s, NULL, %s, FALSE, NOW(), NOW())
                   RETURNING id""",
                (supplier_attribute_id, value.strip()),
            )
            sav_id = cur.fetchone()["id"]
            conn.commit()
            self._val_by_key[key] = sav_id
            return sav_id
        finally:
            conn.close()
