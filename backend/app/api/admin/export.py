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
    """Start a full taxonomy refresh in a background job and return immediately.

    The long-running fetch/upsert never blocks the HTTP request.  Progress and
    logs are available via GET /export/channels/{code}/taxonomy/status.
    """
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
    finally:
        conn.close()

    from app.channels.rozetka.taxonomy_run import (
        TaxonomyRunBusy,
        run_taxonomy_refresh,
        start_taxonomy_refresh,
    )
    try:
        run_id = start_taxonomy_refresh(channel["id"], (user or {}).get("id"))
    except TaxonomyRunBusy as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Offload the blocking fetch to a worker thread so the async event loop
    # stays free to serve the status endpoint and the rest of the admin API.
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_taxonomy_refresh, channel["id"], run_id)
    return {"ok": True, "run_id": run_id, "detail": "Оновлення таксономії запущено у фоновому режимі"}


@router.get("/export/channels/{code}/taxonomy/status")
async def taxonomy_run_status(code: str, user=Depends(require_admin)):
    """Current progress of the latest (or running) taxonomy refresh job."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        from app.channels.rozetka.taxonomy_run import get_taxonomy_run_status
        from app.channels.taxonomy import get_taxonomy_stats as _stats
        status = get_taxonomy_run_status(cur, channel["id"])
        taxonomy = _stats(cur, channel["id"])
        if status is None:
            return {
                "run_id": None, "status": "never",
                "started_at": None, "finished_at": None, "duration_seconds": None,
                "categories": {"processed": 0, "total": 0, "created": 0, "updated": 0},
                "attributes": {"categories_processed": 0, "categories_total": 0,
                               "total": 0, "created": 0, "updated": 0},
                "values": {"total": 0, "created": 0, "updated": 0},
                "errors": 0, "current_operation": None, "logs": [], "taxonomy": taxonomy,
            }
        status["taxonomy"] = taxonomy
        return status
    finally:
        conn.close()


@router.get("/export/channels/{code}/taxonomy/runs")
async def taxonomy_runs_history(
        code: str,
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=100),
        user=Depends(require_admin),
):
    """Paginated list of historical taxonomy runs for the channel."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        cid = channel["id"]

        cur.execute(
            "SELECT count(*) AS c FROM sync_runs WHERE channel_id=%s AND run_type='TAXONOMY'",
            (cid,),
        )
        total = cur.fetchone()["c"]

        cur.execute(
            """SELECT id, status, total_count, processed_count, created_count,
                      updated_count, failed_count, skipped_count,
                      current_stage, started_at, finished_at, created_at,
                      heartbeat_at
               FROM sync_runs
               WHERE channel_id=%s AND run_type='TAXONOMY'
               ORDER BY id DESC
               LIMIT %s OFFSET %s""",
            (cid, per_page, (page - 1) * per_page),
        )
        rows = cur.fetchall()

        # Attach error count from progress_json
        result = []
        for r in rows:
            item = dict(r)
            errors = 0
            if r.get("progress_json"):
                try:
                    import json
                    pj = json.loads(r["progress_json"])
                    if isinstance(pj, dict):
                        errors = int(pj.get("errors") or 0)
                except (ValueError, TypeError):
                    pass
            item["errors"] = errors
            item.pop("progress_json", None)
            result.append(item)

        return {"items": result, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/export/channels/{code}/taxonomy/runs/{run_id}")
async def taxonomy_run_detail(
        code: str,
        run_id: int,
        user=Depends(require_admin),
):
    """Detailed progress and logs for a specific taxonomy run."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        cur.execute(
            "SELECT * FROM sync_runs WHERE id=%s AND channel_id=%s AND run_type='TAXONOMY'",
            (run_id, channel["id"]),
        )
        run = cur.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Запуск не знайдено")

        progress = {}
        if run.get("progress_json"):
            try:
                import json
                progress = json.loads(run["progress_json"]) or {}
            except (ValueError, TypeError):
                progress = {}
        if not isinstance(progress, dict):
            progress = {}
        logs = progress.get("logs") or []
        started_at = run.get("started_at")
        finished_at = run.get("finished_at")
        duration = None
        if started_at:
            delta = (finished_at or datetime.now()) - started_at
            duration = max(0, round(delta.total_seconds()))

        cat = progress.get("categories") or {}
        attrs = progress.get("attributes") or {}
        vals = progress.get("values") or {}
        return {
            "run_id": run["id"],
            "status": run.get("status"),
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration,
            "categories": {
                "processed": int(cat.get("processed") or 0),
                "total": int(cat.get("total") or 0),
                "created": int(cat.get("created") or 0),
                "updated": int(cat.get("updated") or 0),
            },
            "attributes": {
                "categories_processed": int(attrs.get("categories_processed") or 0),
                "categories_total": int(attrs.get("categories_total") or 0),
                "total": int(attrs.get("created") or 0) + int(attrs.get("updated") or 0),
                "created": int(attrs.get("created") or 0),
                "updated": int(attrs.get("updated") or 0),
            },
            "values": {
                "total": int(vals.get("total") or 0),
                "created": int(vals.get("created") or 0),
                "updated": int(vals.get("updated") or 0),
            },
            "errors": int(progress.get("errors") or 0),
            "current_operation": progress.get("current_operation") or run.get("current_stage"),
            "logs": logs,
        }
    finally:
        conn.close()


# ── Taxonomy (local reference data browsing) ─────────────────────────────────


@router.get("/export/channels/{code}/taxonomy/categories")
async def taxonomy_categories(
        code: str,
        q: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=200),
        user=Depends(require_admin),
):
    """Paginated list of local Rozetka categories with attribute counts."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        filters = ["c.channel_id = %s"]
        params = [channel["id"]]
        if q:
            filters.append("(c.name ILIKE %s OR c.external_id ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])
        where = " AND ".join(filters)
        cur.execute(
            f"SELECT count(*) AS c FROM channel_external_categories c WHERE {where}",
            params,
        )
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT c.id, c.external_id, c.parent_external_id, c.name, c.path,
                       (SELECT count(*) FROM channel_external_attributes a
                         WHERE a.channel_id = c.channel_id
                           AND a.category_external_id = c.external_id) AS attributes_count
                FROM channel_external_categories c
                WHERE {where}
                ORDER BY c.name LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page],
        )
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/export/channels/{code}/taxonomy/attributes")
async def taxonomy_attributes(
        code: str,
        q: Optional[str] = Query(None),
        category_external_id: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=200),
        user=Depends(require_admin),
):
    """Paginated local Rozetka attributes (optionally scoped to a category)."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        filters = ["a.channel_id = %s"]
        params = [channel["id"]]
        if category_external_id:
            filters.append("a.category_external_id = %s")
            params.append(category_external_id)
        if q:
            filters.append("(a.name ILIKE %s OR a.external_id ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])
        where = " AND ".join(filters)
        cur.execute(f"SELECT count(*) AS c FROM channel_external_attributes a WHERE {where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT a.id, a.category_external_id, a.external_id, a.name, a.param_type,
                       a.unit, a.is_required, a.fetched_at,
                       c.name AS category_name
                FROM channel_external_attributes a
                LEFT JOIN channel_external_categories c
                       ON c.channel_id = a.channel_id
                      AND c.external_id = a.category_external_id
                WHERE {where}
                ORDER BY a.name LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page],
        )
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/export/channels/{code}/taxonomy/values")
async def taxonomy_values(
        code: str,
        q: Optional[str] = Query(None),
        attribute_external_id: Optional[str] = Query(None),
        category_external_id: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=200),
        user=Depends(require_admin),
):
    """Paginated local Rozetka values (optionally scoped to attr/category)."""
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        filters = ["v.channel_id = %s"]
        params = [channel["id"]]
        if attribute_external_id:
            filters.append("v.attribute_external_id = %s")
            params.append(attribute_external_id)
        if category_external_id:
            filters.append("a.category_external_id = %s")
            params.append(category_external_id)
        if q:
            filters.append("(v.value ILIKE %s OR v.external_id ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])
        where = " AND ".join(filters)
        count_sql = f"""SELECT count(*) AS c
                        FROM channel_external_values v
                        JOIN channel_external_attributes a
                          ON a.channel_id = v.channel_id AND a.external_id = v.attribute_external_id
                        WHERE {where}"""
        cur.execute(count_sql, params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT v.id, v.attribute_external_id, v.external_id, v.value, v.fetched_at,
                       a.name AS attribute_name, a.category_external_id,
                       c.name AS category_name
                FROM channel_external_values v
                JOIN channel_external_attributes a
                  ON a.channel_id = v.channel_id AND a.external_id = v.attribute_external_id
                LEFT JOIN channel_external_categories c
                       ON c.channel_id = a.channel_id AND c.external_id = a.category_external_id
                WHERE {where}
                ORDER BY v.value LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page],
        )
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


# ── Validation ───────────────────────────────────────────────────────────────


class ValidateRequest(BaseModel):
    product_id: int
    public_base_url: Optional[str] = None


@router.post("/export/channels/{code}/validate")
async def validate_product_endpoint(
        code: str,
        body: ValidateRequest,
        user=Depends(require_admin),
):
    """Validate a single product for export to the channel."""
    from app.channels.validation import validate_product as _validate
    result = _validate(body.product_id, channel_code=code,
                       public_base_url=body.public_base_url)
    return result