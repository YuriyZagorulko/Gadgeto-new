"""Admin API for channel (Rozetka) mapping — Internal → External Channel.

Three mapping kinds mirror the importer mapping pattern but with opposite
direction and separate tables.  UI uses the same 3-tab layout as
/imports/mappings.

Direction: Internal Category/Attribute/Value → External Channel Entity
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class MappingCreate(BaseModel):
    internal_id: int
    external_id: Optional[str] = None
    external_name: Optional[str] = None
    external_category_id: Optional[str] = None
    status: str = "proposed"
    confidence: Optional[float] = None


class MappingUpdate(BaseModel):
    external_id: Optional[str] = None
    external_name: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = None


_KIND_MAP = {
    "categories": {
        "table": "channel_category_mappings",
        "internal_table": "categories",
        "internal_id_col": "internal_category_id",
        "internal_name_col": "name",
        "external_id_col": "external_category_id",
        "external_name_col": "external_category_name",
    },
    "attributes": {
        "table": "channel_attribute_mappings",
        "internal_table": "attributes",
        "internal_id_col": "internal_attribute_id",
        "internal_name_col": "name",
        "external_id_col": "external_attribute_id",
        "external_name_col": "external_attribute_name",
        "has_ext_cat": True,
    },
    "values": {
        "table": "channel_value_mappings",
        "internal_table": "attribute_values",
        "internal_id_col": "internal_value_id",
        "internal_name_col": "value",
        "external_id_col": "external_value_id",
        "external_name_col": "external_value_name",
        "has_ext_cat": True,
    },
}


def _resolve_kind(kind: str):
    if kind not in _KIND_MAP:
        raise HTTPException(status_code=404, detail="Невідомий тип відповідностей")
    return _KIND_MAP[kind]


def _list_category_mappings(cur, cid: int, q, status_filter, page: int, per_page: int,
                             parent_category_q: Optional[str] = None,
                             internal_category_ids: Optional[str] = None,
                             internal_parent_category_ids: Optional[str] = None,
                             internal_q: Optional[str] = None,
                             external_q: Optional[str] = None,
                             external_category_ids: Optional[str] = None,
                             external_parent_category_ids: Optional[str] = None):
    """All internal categories with their (optional) channel mapping row.

    Includes Rozetka category metadata: children_count, attribute_count, is_leaf.
    """
    join_params = [cid]
    where_conds, where_params = [], []
    if q:
        where_conds.append(
            "(i.name ILIKE %s OR COALESCE(m.external_category_name, '') ILIKE %s)")
        where_params.extend([f"%{q}%", f"%{q}%"])
    else:
        if internal_q:
            where_conds.append("i.name ILIKE %s")
            where_params.append(f"%{internal_q}%")
        if external_q:
            where_conds.append("COALESCE(m.external_category_name, '') ILIKE %s")
            where_params.append(f"%{external_q}%")
    if status_filter == "unmapped":
        where_conds.append("m.id IS NULL")
    elif status_filter:
        where_conds.append("m.status = %s")
        where_params.append(status_filter)
    if parent_category_q:
        where_conds.append("EXISTS (SELECT 1 FROM channel_external_categories pc WHERE pc.channel_id = %s AND pc.external_id = ec.parent_external_id AND pc.name ILIKE %s)")
        where_params.extend([cid, f"%{parent_category_q}%"])
    # Phase 52: multi-value entity filters
    if internal_category_ids:
        ids = [x.strip() for x in internal_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where_conds.append(f"i.id IN ({placeholders})")
            where_params.extend(ids)
    if internal_parent_category_ids:
        ids = [x.strip() for x in internal_parent_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where_conds.append(f"i.parent_id IN ({placeholders})")
            where_params.extend(ids)
    if external_category_ids:
        ids = [x.strip() for x in external_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where_conds.append(f"m.external_category_id IN ({placeholders})")
            where_params.extend(ids)
    if external_parent_category_ids:
        ids = [x.strip() for x in external_parent_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where_conds.append(f"ec.parent_external_id IN ({placeholders})")
            where_params.extend(ids)
    where_sql = (" WHERE " + " AND ".join(where_conds)) if where_conds else ""
    base = f"""
        FROM categories i
        LEFT JOIN channel_category_mappings m
               ON m.channel_id = %s AND m.internal_category_id = i.id
        LEFT JOIN channel_external_categories ec
               ON ec.channel_id = m.channel_id AND ec.external_id = m.external_category_id
        {where_sql}
    """
    cur.execute(f"SELECT count(*) AS c {base}", join_params + where_params)
    total = cur.fetchone()["c"]
    cur.execute(
        f"""SELECT i.id AS internal_id, i.name AS internal_name, i.slug,
                   m.id AS mapping_id,
                   m.external_category_id AS external_id,
                   m.external_category_name AS external_name,
                   COALESCE(m.status, 'unmapped') AS status,
                   m.confidence, m.source,
                   m.created_at AS created_at, m.updated_at AS updated_at,
                   (SELECT count(*) FROM channel_external_categories ch
                    WHERE ch.channel_id = ec.channel_id
                      AND ch.parent_external_id = ec.external_id) AS children_count,
                   (SELECT count(*) FROM channel_external_attributes a
                    WHERE a.channel_id = ec.channel_id
                      AND a.category_external_id = ec.external_id) AS attribute_count
            {base}
            ORDER BY i.name LIMIT %s OFFSET %s""",
        join_params + where_params + [per_page, (page - 1) * per_page],
    )
    return cur.fetchall(), total


def _list_attribute_mappings(cur, cid: int, q, status_filter, ext_cat_id, scope,
                             page: int, per_page: int,
                             parent_category_q: Optional[str] = None,
                             internal_attr_ids: Optional[str] = None,
                             internal_category_ids: Optional[str] = None,
                             internal_parent_category_ids: Optional[str] = None,
                             external_attribute_ids: Optional[str] = None,
                             internal_q: Optional[str] = None,
                             external_q: Optional[str] = None,
                             external_category_ids: Optional[str] = None,
                             external_parent_category_ids: Optional[str] = None):
    """Attribute mappings — one row per (internal attribute × mapping context).

    An internal attribute can carry a global mapping and multiple
    category-scoped mappings; internal attributes without any mapping appear
    once as an unmapped row.
    """
    base = """
        WITH base AS (
            SELECT i.id AS internal_id, i.name AS internal_name,
                   m.id AS mapping_id,
                   m.external_attribute_id AS external_id,
                   m.external_attribute_name AS external_name,
                   m.external_category_id AS external_category_id,
                   ec.name AS external_category_name,
                   ec.parent_external_id AS external_parent_category_id,
                   COALESCE(m.status, 'accepted') AS status,
                   m.confidence, m.source,
                   m.created_at AS created_at, m.updated_at AS updated_at
            FROM channel_attribute_mappings m
            JOIN attributes i ON i.id = m.internal_attribute_id
            LEFT JOIN channel_external_categories ec
                   ON ec.channel_id = m.channel_id
                  AND ec.external_id = m.external_category_id
            WHERE m.channel_id = %s
            UNION ALL
            SELECT i.id, i.name, NULL, NULL, NULL, NULL, NULL, NULL,
                   'unmapped', NULL, NULL, NULL, NULL
            FROM attributes i
            WHERE NOT EXISTS (
                SELECT 1 FROM channel_attribute_mappings m2
                WHERE m2.channel_id = %s AND m2.internal_attribute_id = i.id
            )
        )
    """
    where, params = [], []
    if q:
        where.append("(internal_name ILIKE %s OR COALESCE(external_name, '') ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    else:
        if internal_q:
            where.append("internal_name ILIKE %s")
            params.append(f"%{internal_q}%")
        if external_q:
            where.append("COALESCE(external_name, '') ILIKE %s")
            params.append(f"%{external_q}%")
    if status_filter == "unmapped":
        where.append("status = 'unmapped'")
    elif status_filter:
        where.append("status = %s")
        params.append(status_filter)
    if ext_cat_id:
        where.append("external_category_id = %s")
        params.append(ext_cat_id)
    if scope == "global":
        where.append("(mapping_id IS NULL OR external_category_id IS NULL)")
    elif scope == "category":
        where.append("(mapping_id IS NOT NULL AND external_category_id IS NOT NULL)")
    if parent_category_q:
        where.append("EXISTS (SELECT 1 FROM channel_external_categories pc WHERE pc.channel_id = %s AND pc.external_id = external_parent_category_id AND pc.name ILIKE %s)")
        params.extend([cid, f"%{parent_category_q}%"])
    # Phase 52/53: multi-value entity filters (applied over base CTE columns)
    if internal_attr_ids:
        ids = [x.strip() for x in internal_attr_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"internal_id IN ({placeholders})")
            params.extend(ids)
    if internal_category_ids:
        # Real relationship: attributes <-> categories via category_attributes
        ids = [x.strip() for x in internal_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(
                "EXISTS (SELECT 1 FROM category_attributes ca"
                f" WHERE ca.attribute_id = internal_id AND ca.category_id IN ({placeholders}))"
            )
            params.extend(ids)
    if internal_parent_category_ids:
        # Parent internal category via category_attributes -> categories.parent_id
        ids = [x.strip() for x in internal_parent_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(
                "EXISTS (SELECT 1 FROM category_attributes ca"
                " JOIN categories pc ON pc.id = ca.category_id"
                f" WHERE ca.attribute_id = internal_id AND pc.parent_id IN ({placeholders}))"
            )
            params.extend(ids)
    if external_attribute_ids:
        ids = [x.strip() for x in external_attribute_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"external_id IN ({placeholders})")
            params.extend(ids)
    if external_category_ids:
        ids = [x.strip() for x in external_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"external_category_id IN ({placeholders})")
            params.extend(ids)
    if external_parent_category_ids:
        ids = [x.strip() for x in external_parent_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"external_parent_category_id IN ({placeholders})")
            params.extend(ids)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    cur.execute(
        f"{base} SELECT count(*) AS c FROM base {where_sql}",
        [cid, cid] + params,
    )
    total = cur.fetchone()["c"]
    cur.execute(
        f"{base} SELECT * FROM base {where_sql} ORDER BY internal_name LIMIT %s OFFSET %s",
        [cid, cid] + params + [per_page, (page - 1) * per_page],
    )
    return cur.fetchall(), total


def _list_value_mappings(cur, cid: int, q, status_filter, ext_cat_id, attribute_id,
                         page: int, per_page: int,
                         parent_category_q: Optional[str] = None,
                         internal_attr_ids: Optional[str] = None,
                         external_attribute_ids: Optional[str] = None,
                         internal_q: Optional[str] = None,
                         external_q: Optional[str] = None,
                         internal_attr_q: Optional[str] = None,
                         external_attr_q: Optional[str] = None,
                         internal_category_ids: Optional[str] = None,
                         internal_parent_category_ids: Optional[str] = None,
                         external_category_ids: Optional[str] = None,
                         external_parent_category_ids: Optional[str] = None):
    """Value mappings — mapping rows plus unmapped internal attribute values.

    Mapped rows carry the resolved Rozetka attribute context (via the local
    channel_external_values/channel_external_attributes tables).
    """
    base = """
        WITH base AS (
            SELECT av.id AS internal_id, av.value AS internal_name,
                   a.id AS attribute_id, a.name AS attribute_name,
                   m.id AS mapping_id,
                   m.external_value_id AS external_id,
                   m.external_value_name AS external_name,
                   m.external_category_id AS external_category_id,
                   ec.name AS external_category_name,
                   ec.parent_external_id AS external_parent_category_id,
                   ea.name AS external_attribute_name,
                   ea.external_id AS external_attribute_id,
                   COALESCE(m.status, 'accepted') AS status,
                   m.confidence, m.source,
                   m.created_at AS created_at, m.updated_at AS updated_at,
                   COALESCE(ea.is_required::boolean, false) AS is_required
            FROM channel_value_mappings m
            JOIN attribute_values av ON av.id = m.internal_value_id
            JOIN attributes a ON a.id = av.attribute_id
            LEFT JOIN channel_external_categories ec
                   ON ec.channel_id = m.channel_id
                  AND ec.external_id = m.external_category_id
            LEFT JOIN LATERAL (
                SELECT ea2.name AS name, ea2.external_id AS external_id,
                       ea2.is_required AS is_required
                FROM channel_external_attributes ea2
                JOIN channel_external_values ev2
                  ON ev2.channel_id = ea2.channel_id
                 AND ev2.attribute_external_id = ea2.external_id
                 AND ev2.external_id = m.external_value_id
                WHERE ea2.channel_id = m.channel_id
                  AND ea2.category_external_id = m.external_category_id
                LIMIT 1
            ) ea ON TRUE
            WHERE m.channel_id = %s
            UNION ALL
            SELECT av.id, av.value, a.id, a.name,
                   NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                   'unmapped', NULL, NULL, NULL, NULL, NULL
            FROM attribute_values av
            JOIN attributes a ON a.id = av.attribute_id
            WHERE NOT EXISTS (
                SELECT 1 FROM channel_value_mappings m2
                WHERE m2.channel_id = %s AND m2.internal_value_id = av.id
            )
        )
    """
    where, params = [], []
    if q:
        where.append("(internal_name ILIKE %s OR COALESCE(external_name, '') ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    else:
        if internal_q:
            where.append("internal_name ILIKE %s")
            params.append(f"%{internal_q}%")
        if external_q:
            where.append("COALESCE(external_name, '') ILIKE %s")
            params.append(f"%{external_q}%")
    # Independent attribute-side text search (value mappings)
    if internal_attr_q:
        where.append("attribute_name ILIKE %s")
        params.append(f"%{internal_attr_q}%")
    if external_attr_q:
        where.append("COALESCE(external_attribute_name, '') ILIKE %s")
        params.append(f"%{external_attr_q}%")
    if status_filter == "unmapped":
        where.append("status = 'unmapped'")
    elif status_filter:
        where.append("status = %s")
        params.append(status_filter)
    if ext_cat_id:
        where.append("external_category_id = %s")
        params.append(ext_cat_id)
    if attribute_id:
        where.append("attribute_id = %s")
        params.append(attribute_id)
    if parent_category_q:
        where.append("EXISTS (SELECT 1 FROM channel_external_categories pc WHERE pc.channel_id = %s AND pc.external_id = external_parent_category_id AND pc.name ILIKE %s)")
        params.extend([cid, f"%{parent_category_q}%"])
    # Phase 52/53: multi-value entity filters (must run BEFORE where_sql is built)
    if internal_attr_ids:
        ids = [x.strip() for x in internal_attr_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"attribute_id IN ({placeholders})")
            params.extend(ids)
    if external_attribute_ids:
        ids = [x.strip() for x in external_attribute_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"external_attribute_id IN ({placeholders})")
            params.extend(ids)
    if internal_category_ids:
        # Real relationship: value -> attribute -> category_attributes
        ids = [x.strip() for x in internal_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(
                "EXISTS (SELECT 1 FROM category_attributes ca"
                f" WHERE ca.attribute_id = attribute_id AND ca.category_id IN ({placeholders}))"
            )
            params.extend(ids)
    if internal_parent_category_ids:
        # Parent internal category via category_attributes -> categories.parent_id
        ids = [x.strip() for x in internal_parent_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(
                "EXISTS (SELECT 1 FROM category_attributes ca"
                " JOIN categories pc ON pc.id = ca.category_id"
                f" WHERE ca.attribute_id = attribute_id AND pc.parent_id IN ({placeholders}))"
            )
            params.extend(ids)
    if external_category_ids:
        ids = [x.strip() for x in external_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"external_category_id IN ({placeholders})")
            params.extend(ids)
    if external_parent_category_ids:
        ids = [x.strip() for x in external_parent_category_ids.split(",") if x.strip()]
        if ids:
            placeholders = ", ".join(["%s"] * len(ids))
            where.append(f"external_parent_category_id IN ({placeholders})")
            params.extend(ids)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    cur.execute(
        f"{base} SELECT count(*) AS c FROM base {where_sql}",
        [cid, cid] + params,
    )
    total = cur.fetchone()["c"]
    cur.execute(
        f"{base} SELECT * FROM base {where_sql} "
        f"ORDER BY attribute_name, internal_name LIMIT %s OFFSET %s",
        [cid, cid] + params + [per_page, (page - 1) * per_page],
    )
    return cur.fetchall(), total


@router.get("/export/channels/{code}/mappings/{kind}")
def list_mappings(
        code: str, kind: str,
        page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
        q: Optional[str] = Query(None),
        status_filter: Optional[str] = Query(None, alias="status"),
        external_category_id: Optional[str] = Query(None),
        attribute_id: Optional[int] = Query(None),
        scope: Optional[str] = Query(None),
        # Phase 47: text-search filters
        parent_category_q: Optional[str] = Query(None, description="Search parent Rozetka category by name"),
        # Phase 52+: independent internal/external text search
        internal_q: Optional[str] = Query(None, description="Search only internal name"),
        external_q: Optional[str] = Query(None, description="Search only external (Rozetka) name"),
        # Value mappings: independent internal/external attribute name search
        internal_attr_q: Optional[str] = Query(None, description="Values: search internal attribute by name"),
        external_attr_q: Optional[str] = Query(None, description="Values: search Rozetka attribute by name"),
        # Phase 52: multi-value entity filters (comma-separated IDs, OR-within-filter)
        internal_attr_ids: Optional[str] = Query(None, description="Comma-separated internal attribute IDs"),
        internal_category_ids: Optional[str] = Query(None, description="Comma-separated internal category IDs"),
        internal_parent_category_ids: Optional[str] = Query(None, description="Comma-separated parent internal category IDs"),
        external_attribute_ids: Optional[str] = Query(None, description="Comma-separated Rozetka attribute external IDs"),
        # Phase 53: Rozetka category hierarchy (real channel_external_categories.parent_external_id)
        external_category_ids: Optional[str] = Query(None, description="Comma-separated Rozetka category external IDs"),
        external_parent_category_ids: Optional[str] = Query(None, description="Comma-separated parent Rozetka category external IDs"),
        user=Depends(require_admin),
):
    """List channel mappings.

    Returns BOTH existing mapping rows and unmapped internal entities (their
    `mapping_id` is NULL), so the admin UI can display/complete everything.
    Additional context filters:
      * external_category_id — attribute/value mappings scoped to a Rozetka category
      * attribute_id    — value mappings scoped to an internal attribute
      * scope           — attributes: 'global' | 'category'
      * status          — also accepts 'unmapped'
    """
    conn, cur = admin_cursor()
    try:
        cfg = _resolve_kind(kind)
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        cid = ch["id"]

        if kind == "categories":
            items, total = _list_category_mappings(
                cur, cid, q, status_filter, page, per_page, parent_category_q,
                internal_category_ids, internal_parent_category_ids,
                internal_q, external_q, external_category_ids, external_parent_category_ids,
            )
        elif kind == "attributes":
            items, total = _list_attribute_mappings(
                cur, cid, q, status_filter, external_category_id, scope,
                page, per_page, parent_category_q,
                internal_attr_ids, internal_category_ids,
                internal_parent_category_ids, external_attribute_ids,
                internal_q, external_q,
                external_category_ids, external_parent_category_ids,
            )
        elif kind == "values":
            items, total = _list_value_mappings(
                cur, cid, q, status_filter, external_category_id, attribute_id,
                page, per_page, parent_category_q,
                internal_attr_ids, external_attribute_ids,
                internal_q, external_q, internal_attr_q, external_attr_q,
                internal_category_ids, internal_parent_category_ids,
                external_category_ids, external_parent_category_ids,
            )
        else:  # unreachable (resolved by _resolve_kind)
            raise HTTPException(status_code=404, detail="Невідомий тип відповідностей")
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.post("/export/channels/{code}/mappings/{kind}")
def create_mapping(code: str, kind: str, body: MappingCreate, user=Depends(require_admin)):
    """Create a mapping idempotently.

    Re-running with the same (internal entity, external category) updates the
    existing row instead of raising a duplicate-key error.
    """
    conn, cur = admin_cursor()
    try:
        cfg = _resolve_kind(kind)
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        cid = ch["id"]

        ext_name = body.external_name
        if not ext_name and body.external_id:
            ext_name = _lookup_external_name(cur, kind, cid, body.external_id,
                                             body.external_category_id)

        id_col = cfg["internal_id_col"]
        ext_col = cfg["external_id_col"]
        name_col = cfg["external_name_col"]
        status = body.status or "proposed"
        if status not in ("proposed", "accepted", "excluded"):
            raise HTTPException(status_code=400, detail="Невірний статус відповідності")

        # Idempotent upsert: (channel, internal, external_category) identifies a row.
        cur.execute(
            (f"SELECT id FROM {cfg['table']} "
             f"WHERE channel_id = %s AND {id_col} = %s "
             f"AND external_category_id IS NOT DISTINCT FROM %s"),
            (cid, body.internal_id, body.external_category_id),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                (f"UPDATE {cfg['table']} "
                 f"SET {ext_col} = %s, {name_col} = %s, status = %s, "
                 f"confidence = %s, source = 'manual', updated_at = NOW() "
                 f"WHERE id = %s RETURNING id"),
                (body.external_id, ext_name, status, body.confidence, existing["id"]),
            )
            return {"ok": True, "id": cur.fetchone()["id"], "updated": True}

        col_parts = [f"channel_id", f"{id_col}", f"{ext_col}", f"{name_col}"]
        val_parts = [f"%s", f"%s", f"%s", f"%s"]
        val_args = [cid, body.internal_id, body.external_id, ext_name]

        # external_category_id is a separate column (for attributes/values);
        # for categories where ext_col IS external_category_id, skip it.
        if ext_col != "external_category_id":
            col_parts.append("external_category_id")
            val_parts.append("%s")
            val_args.append(body.external_category_id)

        col_parts += ["status", "confidence", "source", "created_at", "updated_at"]
        val_parts += ["%s", "%s", "'manual'", "NOW()", "NOW()"]
        val_args += [status, body.confidence]

        cur.execute(
            f"INSERT INTO {cfg['table']} ({', '.join(col_parts)}) "
            f"VALUES ({', '.join(val_parts)}) "
            f"RETURNING id",
            val_args,
        )
        return {"ok": True, "id": cur.fetchone()["id"], "created": True}
    finally:
        conn.close()


def _lookup_external_name(cur, kind: str, cid: int, external_id: str,
                          ext_cat_id: Optional[str]) -> Optional[str]:
    """Fall back to the local taxonomy name when a name was not supplied."""
    try:
        if kind == "categories":
            cur.execute(
                "SELECT name FROM channel_external_categories WHERE channel_id=%s AND external_id=%s LIMIT 1",
                (cid, external_id))
        elif kind == "attributes":
            cur.execute(
                "SELECT name FROM channel_external_attributes WHERE channel_id=%s AND external_id=%s"
                " AND category_external_id IS NOT DISTINCT FROM %s LIMIT 1",
                (cid, external_id, ext_cat_id),
            )
        elif kind == "values":
            cur.execute(
                "SELECT value AS name FROM channel_external_values WHERE channel_id=%s AND external_id=%s LIMIT 1",
                (cid, external_id),
            )
        else:
            return None
        row = cur.fetchone()
        return row["name"] if row else None
    except Exception:
        return None


@router.put("/export/channels/{code}/mappings/{kind}/{mid}")
def update_mapping(code: str, kind: str, mid: int, body: MappingUpdate, user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cfg = _resolve_kind(kind)
        sets, params = [], []
        if body.external_id is not None:
            sets.append(f"{cfg['external_id_col']} = %s"); params.append(body.external_id)
        if body.external_name is not None:
            sets.append(f"{cfg['external_name_col']} = %s"); params.append(body.external_name)
        if body.status is not None:
            sets.append("status = %s"); params.append(body.status)
        if body.confidence is not None:
            sets.append("confidence = %s"); params.append(body.confidence)
        if not sets:
            return {"ok": True, "id": mid}
        sets.append("updated_at = NOW()")
        params.append(mid)
        cur.execute(f"UPDATE {cfg['table']} SET {', '.join(sets)} WHERE id = %s", params)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        return {"ok": True, "id": mid}
    finally:
        conn.close()


@router.delete("/export/channels/{code}/mappings/{kind}/{mid}")
def delete_mapping(code: str, kind: str, mid: int, user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cfg = _resolve_kind(kind)
        cur.execute(f"DELETE FROM {cfg['table']} WHERE id = %s", (mid,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        return {"ok": True, "deleted": mid}
    finally:
        conn.close()


# ── Suggestions ──────────────────────────────────────────────────────────────


@router.get("/export/channels/{code}/mappings/{kind}/{internal_id}/suggestions")
def get_suggestions(
        code: str, kind: str, internal_id: int,
        external_category_id: Optional[str] = Query(None),
        external_attribute_id: Optional[str] = Query(None),
        user=Depends(require_admin),
):
    from app.channels.rozetka.mapping_suggestions import suggest_mappings
    conn, cur = admin_cursor()
    try:
        _resolve_kind(kind)
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        suggestions = suggest_mappings(
            channel_id=ch["id"], kind=kind, internal_id=internal_id,
            ext_cat_id=external_category_id, ext_attr_id=external_attribute_id)
        return {"items": suggestions}
    finally:
        conn.close()

# ── Picker endpoints ─────────────────────────────────────────────────────────


@router.get("/export/channels/{code}/pickers/categories")
def pick_categories(code: str, q: Optional[str] = Query(None),
                          page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=500),
                          user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        filters, params = [], []
        if q:
            filters.append("name ILIKE %s"); params.append(f"%{q}%")
        where = " AND ".join(filters) if filters else "TRUE"
        cur.execute(f"SELECT count(*) AS c FROM categories WHERE {where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"SELECT id, name, parent_id FROM categories WHERE {where} ORDER BY name LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/export/channels/{code}/pickers/attributes")
def pick_attributes(code: str, q: Optional[str] = Query(None),
                          page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=500),
                          user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        filters, params = [], []
        if q:
            filters.append("name ILIKE %s"); params.append(f"%{q}%")
        where = " AND ".join(filters) if filters else "TRUE"
        cur.execute(f"SELECT count(*) AS c FROM attributes WHERE {where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"SELECT id, name FROM attributes WHERE {where} ORDER BY name LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/export/channels/{code}/pickers/values")
def pick_values(code: str, attribute_id: Optional[int] = Query(None),
                      q: Optional[str] = Query(None),
                      page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=500),
                      user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        filters, params = [], []
        if attribute_id:
            filters.append("attribute_id = %s"); params.append(attribute_id)
        if q:
            filters.append("value ILIKE %s"); params.append(f"%{q}%")
        where = " AND ".join(filters) if filters else "TRUE"
        cur.execute(f"SELECT count(*) AS c FROM attribute_values WHERE {where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"SELECT id, value, attribute_id FROM attribute_values WHERE {where} ORDER BY value LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


# ── External taxonomy pickers (local channel_external_* data) ────────────────


@router.get("/export/channels/{code}/pickers/external-categories")
def pick_external_categories(code: str, q: Optional[str] = Query(None),
                                    parents_only: bool = Query(False),
                                    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=500),
                                    user=Depends(require_admin)):
    """Rozetka categories from the LOCAL taxonomy (never an API call).

    Returns metadata: children_count (0 = leaf), attribute_count.
    When parents_only=True, only returns categories that have at least one
    child category (i.e. parent categories).
    """
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        filters, params = ["c.channel_id = %s"], [ch["id"]]
        if q:
            filters.append("c.name ILIKE %s"); params.append(f"%{q}%")
        if parents_only:
            filters.append(
                "EXISTS (SELECT 1 FROM channel_external_categories ch2 "
                "WHERE ch2.channel_id = c.channel_id "
                "AND ch2.parent_external_id = c.external_id)")
        where = " AND ".join(filters)
        cur.execute(
            f"SELECT count(*) AS c FROM channel_external_categories c WHERE {where}",
            params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT c.id, c.external_id, c.name, c.parent_external_id,
                       (SELECT count(*) FROM channel_external_categories ch
                        WHERE ch.channel_id = c.channel_id
                          AND ch.parent_external_id = c.external_id) AS children_count,
                       (SELECT count(*) FROM channel_external_attributes a
                        WHERE a.channel_id = c.channel_id
                          AND a.category_external_id = c.external_id) AS attribute_count
                FROM channel_external_categories c
                WHERE {where}
                ORDER BY c.name LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()



@router.get("/export/channels/{code}/pickers/external-attributes")
def pick_external_attributes(code: str,
                                   category_external_id: Optional[str] = Query(None),
                                   q: Optional[str] = Query(None),
                                   page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=500),
                                   user=Depends(require_admin)):
    """Rozetka attributes from local taxonomy, scoped to a Rozetka category.

    Uses DISTINCT ON (external_id) to avoid the same attribute appearing
    multiple times when it belongs to multiple Rozetka categories.
    """
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        filters, params = ["channel_id = %s"], [ch["id"]]
        if category_external_id:
            filters.append("category_external_id = %s"); params.append(category_external_id)
        if q:
            filters.append("name ILIKE %s"); params.append(f"%{q}%")
        where = " AND ".join(filters)
        # Count distinct external_ids for accurate pagination
        cur.execute(f"SELECT COUNT(DISTINCT external_id) AS c FROM channel_external_attributes WHERE {where}", params)
        total = cur.fetchone()["c"]
        # DISTINCT ON ensures each external_id appears once (ORDER BY external_id, name
        # picks the first category's row for each attribute name)
        cur.execute(
            f"""SELECT external_id, name, category_external_id, param_type, unit
                FROM (
                    SELECT DISTINCT ON (external_id) external_id, name,
                           category_external_id, param_type, unit
                    FROM channel_external_attributes
                    WHERE {where}
                    ORDER BY external_id, name
                ) sub
                ORDER BY name LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/export/channels/{code}/pickers/external-values")
def pick_external_values(code: str,
                               category_external_id: Optional[str] = Query(None),
                               attribute_external_id: Optional[str] = Query(None),
                               q: Optional[str] = Query(None),
                               page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=500),
                               user=Depends(require_admin)):
    """Rozetka values from local taxonomy, scoped to category + attribute."""
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        # Single-table filters only — no JOIN. The same external attribute id
        # exists once per Rozetka category (unique on channel_id,
        # category_external_id, external_id), so a JOIN here fans every value
        # row out ~N times (~15M rows before filtering). Category scope is
        # expressed as an IN-subquery over the indexed attribute list instead.
        # Attribute scope wins when both are given (it is the narrower one).
        filters, params = ["channel_id = %s"], [ch["id"]]
        if attribute_external_id:
            filters.append("attribute_external_id = %s"); params.append(attribute_external_id)
        elif category_external_id:
            filters.append(
                "attribute_external_id IN (SELECT external_id FROM channel_external_attributes"
                " WHERE channel_id = %s AND category_external_id = %s)")
            params.extend([ch["id"], category_external_id])
        if q:
            filters.append("value ILIKE %s"); params.append(f"%{q}%")
        where = " AND ".join(filters)
        cur.execute(f"SELECT count(*) AS c FROM channel_external_values WHERE {where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"SELECT id, external_id, value, attribute_external_id"
            f" FROM channel_external_values WHERE {where}"
            f" ORDER BY value LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


# ── Coverage ─────────────────────────────────────────────────────────────────

_COVERAGE_KINDS = {
    "categories": {
        "internal": "categories", "table": "channel_category_mappings",
        "id_col": "internal_category_id", "ext_col": "external_category_id",
    },
    "attributes": {
        "internal": "attributes", "table": "channel_attribute_mappings",
        "id_col": "internal_attribute_id", "ext_col": "external_attribute_id",
    },
    "values": {
        "internal": "attribute_values", "table": "channel_value_mappings",
        "id_col": "internal_value_id", "ext_col": "external_value_id",
    },
}


def _coverage_block(cur, cid: int, kind: str) -> dict:
    """Count distinct internal entities by effective mapping state.

    Buckets are exclusive (priority accepted > proposed > excluded > unmapped),
    so a category-scoped attribute with one accepted and one proposed mapping is
    counted exactly once as accepted.
    """
    cfg = _COVERAGE_KINDS[kind]
    sql = f"""
        WITH eff AS (
            SELECT i.id AS item_id,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM {cfg['table']} m
                        WHERE m.channel_id = %s AND m.{cfg['id_col']} = i.id
                          AND m.status = 'accepted'
                          AND m.{cfg['ext_col']} IS NOT NULL) THEN 'accepted'
                    WHEN EXISTS (
                        SELECT 1 FROM {cfg['table']} m
                        WHERE m.channel_id = %s AND m.{cfg['id_col']} = i.id
                          AND m.status = 'proposed'
                          AND m.{cfg['ext_col']} IS NOT NULL) THEN 'proposed'
                    WHEN EXISTS (
                        SELECT 1 FROM {cfg['table']} m
                        WHERE m.channel_id = %s AND m.{cfg['id_col']} = i.id
                          AND m.status = 'excluded') THEN 'excluded'
                    ELSE 'unmapped'
                END AS status
            FROM {cfg['internal']} i
        )
        SELECT count(*) AS total,
               count(*) FILTER (WHERE status = 'accepted') AS accepted,
               count(*) FILTER (WHERE status = 'proposed') AS proposed,
               count(*) FILTER (WHERE status = 'excluded') AS excluded,
               count(*) FILTER (WHERE status = 'unmapped') AS unmapped
        FROM eff
    """
    cur.execute(sql, (cid, cid, cid))
    block = dict(cur.fetchone())
    total = block.get("total") or 0
    for key in ("accepted", "proposed", "excluded", "unmapped"):
        block[f"{key}_pct"] = round(block.get(key, 0) * 100 / total, 1) if total else 0.0
    return block


@router.get("/export/channels/{code}/mapping-coverage")
def mapping_coverage(code: str, user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        cid = ch["id"]
        return {
            "categories": _coverage_block(cur, cid, "categories"),
            "attributes": _coverage_block(cur, cid, "attributes"),
            "values": _coverage_block(cur, cid, "values"),
        }
    finally:
        conn.close()