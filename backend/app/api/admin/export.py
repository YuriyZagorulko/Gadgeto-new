"""Admin API for the channel publication (export) foundation.

Phase 1: read-only listing and settings endpoints only.  No Rozetka API
calls, no mapping, no sync engine.  Endpoints are data-driven from the
new channel tables.

Endpoints:
  GET    /export/channels              — list all channels
  GET    /export/channels/{code}       — single channel details
  GET    /export/channels/{code}/listings  — paginated listing table
  GET    /export/channels/{code}/stats — dashboard counts
  GET    /export/channels/{code}/settings — channel settings
  PUT    /export/channels/{code}/settings — update channel settings
"""

from datetime import datetime
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


def _resolve_channel(cur, code: str) -> dict:
    """Fetch a channel by stable code or raise 404."""
    cur.execute("SELECT * FROM channels WHERE code = %s", (code,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Канал '{code}' не знайдено")
    return row


def _mask_secrets(settings: list[dict]) -> list[dict]:
    """Mask values of secret settings."""
    return [
        {**s, "value": "••••••••" if s["is_secret"] else s["value"]}
        for s in settings
    ]


class ChannelSettingUpdate(BaseModel):
    key: str
    value: Optional[str] = None
    is_secret: bool = False


@router.get("/export/channels")
async def list_channels(user=Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute(
            "SELECT id, code, name, is_enabled, created_at, updated_at FROM channels ORDER BY code"
        )
        return {"items": cur.fetchall()}
    finally:
        conn.close()


@router.get("/export/channels/{code}")
async def get_channel(code: str, user=Depends(require_admin)):
    conn, cur = db()
    try:
        return _resolve_channel(cur, code)
    finally:
        conn.close()


@router.get("/export/channels/{code}/settings")
async def list_settings(code: str, user=Depends(require_admin)):
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        cur.execute(
            "SELECT id, key, value, is_secret FROM channel_settings WHERE channel_id = %s ORDER BY key",
            (channel["id"],),
        )
        return {"items": _mask_secrets(cur.fetchall())}
    finally:
        conn.close()


@router.put("/export/channels/{code}/settings")
async def upsert_setting(code: str, body: ChannelSettingUpdate, user=Depends(require_admin)):
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        cur.execute(
            """INSERT INTO channel_settings (channel_id, key, value, is_secret, created_at, updated_at)
               VALUES (%s, %s, %s, %s, NOW(), NOW())
               ON CONFLICT (channel_id, key)
               DO UPDATE SET value = EXCLUDED.value, is_secret = EXCLUDED.is_secret, updated_at = NOW()
               RETURNING id""",
            (channel["id"], body.key, body.value, body.is_secret),
        )
        sid = cur.fetchone()["id"]
        return {"ok": True, "id": sid}
    finally:
        conn.close()


# ── Listings (paginated) ─────────────────────────────────────────────────────


@router.get("/export/channels/{code}/listings")
async def list_listings(
        code: str,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        publication_status: Optional[str] = Query(None),
        sync_status: Optional[str] = Query(None),
        q: Optional[str] = Query(None),
        user=Depends(require_admin),
):
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        filters = ["cl.channel_id = %s"]
        params = [channel["id"]]

        if publication_status:
            filters.append("cl.publication_status = %s")
            params.append(publication_status)
        if sync_status:
            filters.append("cl.sync_status = %s")
            params.append(sync_status)
        if q:
            filters.append("(p.sku ILIKE %s OR p.name ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])

        where = " AND ".join(filters)

        count_sql = f"""
            SELECT count(*) AS c
            FROM channel_listings cl
            JOIN products p ON p.id = cl.product_id
            WHERE {where}
        """
        cur.execute(count_sql, params)
        total = cur.fetchone()["c"]

        data_sql = f"""
            SELECT cl.id, cl.product_id, cl.channel_id,
                   cl.publication_status, cl.sync_status,
                   cl.external_id, cl.last_synced_at, cl.last_attempt_at,
                   cl.last_error_type, cl.last_error_message,
                   cl.remote_status,
                   p.name AS product_name, p.sku AS product_sku,
                   p.is_active, p.status AS product_status
            FROM channel_listings cl
            JOIN products p ON p.id = cl.product_id
            WHERE {where}
            ORDER BY cl.updated_at DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


# ── Stats (for the dashboard overview) ───────────────────────────────────────


@router.get("/export/channels/{code}/stats")
async def channel_stats(code: str, user=Depends(require_admin)):
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)

        cur.execute("SELECT count(*) AS c FROM products WHERE status = 'PUBLISHED'")
        total_products = cur.fetchone()["c"]

        cur.execute(
            """
            SELECT
                count(*) AS total_listings,
                count(*) FILTER (WHERE publication_status = 'PUBLISHED') AS published,
                count(*) FILTER (WHERE publication_status = 'READY') AS ready,
                count(*) FILTER (WHERE publication_status IN ('DRAFT','DISABLED')) AS blocked,
                count(*) FILTER (WHERE sync_status = 'ERROR') AS errors
            FROM channel_listings
            WHERE channel_id = %s
            """,
            (channel["id"],),
        )
        stats = dict(cur.fetchone())

        cur.execute(
            "SELECT started_at, finished_at, status FROM sync_runs WHERE channel_id = %s ORDER BY created_at DESC LIMIT 1",
            (channel["id"],),
        )
        last_run = cur.fetchone()

        return {
            "channel_id": channel["id"],
            "channel_code": channel["code"],
            "channel_enabled": channel["is_enabled"],
            "total_products": total_products,
            "total_listings_with_channel": stats.get("total_listings", 0),
            "published": stats.get("published", 0),
            "ready": stats.get("ready", 0),
            "blocked": stats.get("blocked", 0),
            "errors": stats.get("errors", 0),
            "last_sync": last_run,
        }
    finally:
        conn.close()


# ── Taxonomy (Rozetka reference data) ────────────────────────────────────────


@router.get("/export/channels/{code}/taxonomy")
async def channel_taxonomy_stats(code: str, user=Depends(require_admin)):
    """Return taxonomy counts for the channel."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        from app.channels.taxonomy import get_taxonomy_stats as _stats
        return {"items": _stats(cur, channel["id"])}
    finally:
        conn.close()


@router.post("/export/channels/{code}/taxonomy/refresh")
async def refresh_taxonomy(code: str, user=Depends(require_admin)):
    """Trigger a full taxonomy refresh from the marketplace API."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        from app.channels.taxonomy import get_taxonomy_service
        svc = get_taxonomy_service(code)
        result = svc.refresh(channel["id"], code)
        return result
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    finally:
        conn.close()