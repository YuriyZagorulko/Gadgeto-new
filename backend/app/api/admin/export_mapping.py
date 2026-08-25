"""Admin API for channel (Rozetka) mapping — Internal → External Channel.

Three mapping kinds mirror the importer mapping pattern but with opposite
direction and separate tables.  UI uses the same 3-tab layout as
/imports/mappings.

Direction: Internal Category/Attribute/Value → External Channel Entity
"""

from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

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


@router.get("/export/channels/{code}/mappings/{kind}")
async def list_mappings(
        code: str, kind: str,
        page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
        q: Optional[str] = Query(None),
        status_filter: Optional[str] = Query(None, alias="status"),
        user=Depends(require_admin),
):
    conn, cur = db()
    try:
        cfg = _resolve_kind(kind)
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")

        filters = ["m.channel_id = %s"]
        params = [ch["id"]]
        if status_filter:
            filters.append("m.status = %s")
            params.append(status_filter)
        if q:
            filters.append(f"(i.{cfg['internal_name_col']} ILIKE %s OR m.{cfg['external_name_col']} ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])

        where = " AND ".join(filters)
        cur.execute(
            f"SELECT count(*) AS c FROM {cfg['table']} m JOIN {cfg['internal_table']} i ON i.id = m.{cfg['internal_id_col']} WHERE {where}",
            params,
        )
        total = cur.fetchone()["c"]

        cur.execute(
            f"""SELECT m.id, m.{cfg['internal_id_col']} AS internal_id,
                       i.{cfg['internal_name_col']} AS internal_name,
                       m.{cfg['external_id_col']} AS external_id,
                       m.{cfg['external_name_col']} AS external_name,
                       m.status, m.confidence, m.source,
                       m.created_at, m.updated_at
                FROM {cfg['table']} m
                JOIN {cfg['internal_table']} i ON i.id = m.{cfg['internal_id_col']}
                WHERE {where}
                ORDER BY m.updated_at DESC LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page],
        )
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.post("/export/channels/{code}/mappings/{kind}")
async def create_mapping(code: str, kind: str, body: MappingCreate, user=Depends(require_admin)):
    conn, cur = db()
    try:
        cfg = _resolve_kind(kind)
        cur.execute("SELECT id FROM channels WHERE code = %s", (code,))
        ch = cur.fetchone()
        if not ch:
            raise HTTPException(status_code=404, detail="Канал не знайдено")
        cur.execute(
            f"""INSERT INTO {cfg['table']}
                (channel_id, {cfg['internal_id_col']},
                 {cfg['external_id_col']}, {cfg['external_name_col']},
                 external_category_id, status, confidence, source, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'manual',NOW(),NOW())
               RETURNING id""",
            (ch["id"], body.internal_id, body.external_id, body.external_name,
             body.external_category_id, body.status, body.confidence),
        )
        return {"ok": True, "id": cur.fetchone()["id"]}
    finally:
        conn.close()


@router.put("/export/channels/{code}/mappings/{kind}/{mid}")
async def update_mapping(code: str, kind: str, mid: int, body: MappingUpdate, user=Depends(require_admin)):
    conn, cur = db()
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
async def delete_mapping(code: str, kind: str, mid: int, user=Depends(require_admin)):
    conn, cur = db()
    try:
        cfg = _resolve_kind(kind)
        cur.execute(f"DELETE FROM {cfg['table']} WHERE id = %s", (mid,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        return {"ok": True, "deleted": mid}
    finally:
        conn.close()
        raise HTTPException(status_code=404, detail="Невідомий тип відповідностей")
    return _KIND_MAP[kind]