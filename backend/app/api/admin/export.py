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
        count_sql = f"""SELECT count(DISTINCT v.id) AS c
                        FROM channel_external_values v
                        JOIN channel_external_attributes a
                          ON a.channel_id = v.channel_id AND a.external_id = v.attribute_external_id
                        WHERE {where}"""
        cur.execute(count_sql, params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT DISTINCT ON (v.id) v.id, v.attribute_external_id, v.external_id, v.value, v.fetched_at,
                       a.name AS attribute_name, a.category_external_id,
                       c.name AS category_name
                FROM channel_external_values v
                JOIN channel_external_attributes a
                  ON a.channel_id = v.channel_id AND a.external_id = v.attribute_external_id
                LEFT JOIN channel_external_categories c
                       ON c.channel_id = a.channel_id AND c.external_id = a.category_external_id
                WHERE {where}
                ORDER BY v.id, v.value LIMIT %s OFFSET %s""",
            params + [per_page, (page - 1) * per_page],
        )
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


# ── Products ──────────────────────────────────────────────────────────────────


@router.get("/export/channels/{code}/products")
async def channel_products(
        code: str,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        q: Optional[str] = Query(None),
        category_id: Optional[int] = Query(None),
        publication_status: Optional[str] = Query(None),
        sync_status: Optional[str] = Query(None),
        stock_status: Optional[str] = Query(None),
        has_mapping: Optional[bool] = Query(None),
        user=Depends(require_admin),
):
    """Paginated list of products with Rozetka listing and mapping status.

    Server-side pagination, search by SKU/name, category filter,
    listing status filters, and mapping status indicator.
    """
    conn, cur = db()
    try:
        channel = _resolve_channel(cur, code)
        cid = channel["id"]

        filters = ["1 = 1"]
        params: list = []

        if q:
            filters.append("(p.sku ILIKE %s OR p.name ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])
        if category_id is not None:
            filters.append(
                "EXISTS (SELECT 1 FROM product_categories pc "
                "WHERE pc.product_id = p.id AND pc.category_id = %s)")
            params.append(category_id)
        if stock_status:
            filters.append("p.stock_status = %s")
            params.append(stock_status)
        if publication_status is not None:
            filters.append("COALESCE(cl.publication_status, 'draft') = %s")
            params.append(publication_status)
        if sync_status is not None:
            filters.append("COALESCE(cl.sync_status, 'idle') = %s")
            params.append(sync_status)
        if has_mapping is not None:
            exists_sql = (
                "EXISTS (SELECT 1 FROM channel_category_mappings ccm "
                "JOIN product_categories pc2 ON pc2.category_id = ccm.internal_category_id "
                "WHERE ccm.channel_id = %s AND ccm.status = 'accepted' "
                "AND pc2.product_id = p.id)")
            if has_mapping:
                filters.append(exists_sql)
            else:
                filters.append("NOT " + exists_sql)
            params.append(cid)

        where = " AND ".join(filters)
        base_params = [cid] + params

        cur.execute(
            f"SELECT count(*) AS c FROM products p "
            f"LEFT JOIN channel_listings cl ON cl.product_id = p.id AND cl.channel_id = %s "
            f"WHERE {where}",
            base_params)
        total = cur.fetchone()["c"]

        data_sql = f"""
            SELECT p.id, p.sku, p.name,
                   p.price, p.currency, p.stock_qty, p.stock_status,
                   p.status AS product_status,
                   (SELECT c.name FROM product_categories pc
                    JOIN categories c ON c.id = pc.category_id
                    WHERE pc.product_id = p.id ORDER BY pc.id LIMIT 1) AS category_name,
                   (SELECT pc.category_id FROM product_categories pc
                    WHERE pc.product_id = p.id ORDER BY pc.id LIMIT 1) AS category_id,
                   cl.id AS listing_id,
                   cl.publication_status, cl.sync_status,
                   cl.external_id, cl.last_error_type, cl.last_error_message,
                   cl.last_synced_at,
                   EXISTS (SELECT 1 FROM channel_category_mappings ccm
                           JOIN product_categories pc2 ON pc2.category_id = ccm.internal_category_id
                           WHERE ccm.channel_id = %s AND ccm.status = 'accepted'
                           AND pc2.product_id = p.id) AS has_mapping
            FROM products p
            LEFT JOIN channel_listings cl ON cl.product_id = p.id AND cl.channel_id = %s
            WHERE {where}
            ORDER BY p.id DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(
            data_sql,
            base_params + [per_page, (page - 1) * per_page])
        items = []
        for r in cur.fetchall():
            item = {
                "id": r["id"],
                "sku": r["sku"] or "",
                "name": r["name"] or "",
                "category_name": r["category_name"],
                "category_id": r["category_id"],
                "price": float(r["price"]) if r["price"] else 0.0,
                "stock_qty": r["stock_qty"] or 0,
                "stock_status": r["stock_status"] or "out_of_stock",
                "status": r["product_status"] or "DRAFT",
                "publication_status": r["publication_status"] or "draft",
                "sync_status": r["sync_status"] or "idle",
                "external_id": r["external_id"],
                "has_mapping": bool(r["has_mapping"]),
                "validation_summary": {"errors": 0, "warnings": 0},
            }
            if r["sync_status"] == "error":
                item["last_error"] = (
                    r.get("last_error_type") or
                    r.get("last_error_message") or "")
            items.append(item)

        return {"items": items, "total": total, "page": page, "per_page": per_page}
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


# ── Export Preview ───────────────────────────────────────────────────────────

MAX_PREVIEW_PRODUCTS = 50


class PreviewSelectionFilters(BaseModel):
    q: Optional[str] = None
    category_id: Optional[int] = None
    publication_status: Optional[str] = None
    sync_status: Optional[str] = None
    stock_status: Optional[str] = None
    has_mapping: Optional[bool] = None


class PreviewSelection(BaseModel):
    all_matching_filters: bool = False
    product_ids: Optional[list[int]] = None
    filters: Optional[PreviewSelectionFilters] = None
    exclude_ids: Optional[list[int]] = None


class PreviewRequest(BaseModel):
    selection: PreviewSelection
    public_base_url: Optional[str] = None

def _resolve_preview_product_ids(
    cur, cid: int, selection: PreviewSelection,
) -> list[int]:
    """Resolve a PreviewSelection to a concrete list of product IDs."""
    if not selection.all_matching_filters:
        if not selection.product_ids:
            raise HTTPException(
                status_code=422,
                detail="Виберіть товари для попереднього перегляду")
        return selection.product_ids

    sf = selection.filters or PreviewSelectionFilters()
    filters = ["1 = 1"]
    params: list = []

    if sf.q:
        filters.append("(p.sku ILIKE %s OR p.name ILIKE %s)")
        params.extend([f"%{sf.q}%", f"%{sf.q}%"])
    if sf.category_id is not None:
        filters.append(
            "EXISTS (SELECT 1 FROM product_categories pc "
            "WHERE pc.product_id = p.id AND pc.category_id = %s)")
        params.append(sf.category_id)
    if sf.stock_status:
        filters.append("p.stock_status = %s")
        params.append(sf.stock_status)
    if sf.publication_status is not None:
        filters.append("COALESCE(cl.publication_status, 'draft') = %s")
        params.append(sf.publication_status)
    if sf.sync_status is not None:
        filters.append("COALESCE(cl.sync_status, 'idle') = %s")
        params.append(sf.sync_status)
    if sf.has_mapping is not None:
        exists_sql = (
            "EXISTS (SELECT 1 FROM channel_category_mappings ccm "
            "JOIN product_categories pc2 ON pc2.category_id = ccm.internal_category_id "
            "WHERE ccm.channel_id = %s AND ccm.status = 'accepted' "
            "AND pc2.product_id = p.id)")
        if sf.has_mapping:
            filters.append(exists_sql)
        else:
            filters.append("NOT " + exists_sql)
        params.append(cid)

    exclude_sql = ""
    if selection.exclude_ids:
        exclude_sql = " AND p.id != ALL(%s)"
        params.append(selection.exclude_ids)

    where = " AND ".join(filters)
    limit = MAX_PREVIEW_PRODUCTS + 1
    cur.execute(
        "SELECT p.id FROM products p "
        "LEFT JOIN channel_listings cl "
        "  ON cl.product_id = p.id AND cl.channel_id = %s "
        f"WHERE {where} {exclude_sql} ORDER BY p.id LIMIT %s",
        [cid] + params + [limit],
    )
    ids = [r["id"] for r in cur.fetchall()]

    if len(ids) > MAX_PREVIEW_PRODUCTS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Попередній перегляд обмежений {MAX_PREVIEW_PRODUCTS} "
                f"товарами. Звужте фільтри або оберіть менше товарів."),
        )
    return ids


@router.post("/export/channels/{code}/export/preview")
async def export_preview(
        code: str,
        body: PreviewRequest,
        user=Depends(require_admin),
):
    """Preview the export payload for selected products.

    Resolves all mappings, builds the payload using the same logic as
    the real export, runs validation.  Read-only.  Maximum 50 products.
    NEVER sends data to Rozetka.
    """
    from app.channels.validation import (
        validate_product as _validate,
        _load_product_data,
        _get_external_category_id,
        _build_transform_payload,
    )
    from app.channels.mapping_resolver import ChannelMappingResolver
    from app.channels.export_settings import (
        load_export_settings,
        apply_export_settings,
        stock_exclusion_reason,
    )

    conn, cur = db()
    try:
        ch = _resolve_channel(cur, code)
        cid = ch["id"]

        product_ids = _resolve_preview_product_ids(cur, cid, body.selection)

        # Single resolver shared across all preview products
        resolver = ChannelMappingResolver(channel_id=cid, channel_code=code)

        # Export settings so the preview can show the ACTUAL price that the
        # real export would submit (single source of truth).
        try:
            export_settings = load_export_settings(cur, cid)
        except Exception:
            export_settings = None

        preview_products = []
        summary = {"total": len(product_ids), "exportable": 0,
                    "errors": 0, "warnings": 0}

        for pid in product_ids:
            product = _load_product_data(cur, pid)
            if product is None:
                preview_products.append({
                    "id": pid, "name": None, "sku": None,
                    "exportable": False,
                    "issues": [{"code": "PRODUCT_NOT_FOUND",
                                "severity": "error",
                                "message": f"Товар {pid} не знайдено"}],
                    "category": None, "attributes": [], "payload": None,
                })
                summary["errors"] += 1
                continue

            ext_cat_id = _get_external_category_id(resolver, product)
            try:
                payload = _build_transform_payload(
                    product, resolver, ext_cat_id, body.public_base_url)
            except Exception:
                payload = None

            # Apply the SAME export settings/preview as the real export.
            if payload is not None and export_settings is not None:
                apply_export_settings(payload, export_settings)
                product["export_price"] = payload.get("export_price")

            validation = _validate(pid, channel_code=code,
                                   public_base_url=body.public_base_url,
                                   export_settings=export_settings)
            exportable = validation.get("ready", False)
            issues = validation.get("issues", [])

            # Attribute preview details
            attrs_preview = []
            for pa in product.get("attributes") or []:
                attr_map = resolver.resolve_attribute(
                    pa["attribute_id"], ext_cat_id)
                mapped = attr_map is not None
                ext_attr_id = attr_map.get("external_attribute_id") if mapped else None
                ext_attr_name = attr_map.get("external_attribute_name") if mapped else None

                resolved_val = None
                ext_val_id = None
                warning = None
                if pa["attribute_value_id"]:
                    val_map = resolver.resolve_value(
                        pa["attribute_value_id"], ext_cat_id)
                    if val_map:
                        resolved_val = val_map.get("external_value_name")
                        ext_val_id = val_map.get("external_value_id")
                elif pa.get("value_text"):
                    val_map = resolver.resolve_value_by_text(
                        pa["attribute_id"], pa["value_text"], ext_cat_id)
                    if val_map:
                        resolved_val = val_map.get("external_value_name")
                        ext_val_id = val_map.get("external_value_id")
                    else:
                        resolved_val = pa["value_text"]
                        if mapped:
                            warning = "Не зіставлено — передається оригінальний текст"

                attrs_preview.append({
                    "internal_attribute_id": pa["attribute_id"],
                    "internal_attribute_name": pa.get("attr_name", ""),
                    "internal_value": pa.get("value_text") or "",
                    "external_attribute_id": ext_attr_id,
                    "external_attribute_name": ext_attr_name,
                    "external_value_id": ext_val_id,
                    "external_value": resolved_val,
                    "mapped": mapped and (ext_val_id is not None
                                          or not pa.get("value_text")),
                    "warning": warning,
                })

            # Category preview
            cat_preview = None
            for cat in product.get("categories") or []:
                cm = resolver.resolve_category(cat["category_id"])
                if cm:
                    cat_preview = {
                        "internal_id": cat["category_id"],
                        "internal_name": cat.get("category_name", ""),
                        "external_id": cm.get("external_category_id"),
                        "external_name": cm.get("external_category_name"),
                        "mapped": True,
                    }
                    break
            if cat_preview is None and product.get("categories"):
                cat_preview = {
                    "internal_id": product["categories"][0]["category_id"],
                    "internal_name": product["categories"][0].get("category_name", ""),
                    "external_id": None, "external_name": None,
                    "mapped": False,
                }

            err_count = sum(1 for i in issues if i.get("severity") == "error")
            warn_count = sum(1 for i in issues if i.get("severity") == "warning")

            preview_products.append({
                "id": pid,
                "sku": product.get("sku") or "",
                "name": product.get("name") or "",
                "exportable": exportable,
                "issues": issues,
                "category": cat_preview,
                "attributes": attrs_preview,
                "payload": payload,
            })
            if exportable:
                summary["exportable"] += 1
            if err_count > 0:
                summary["errors"] += 1
            if warn_count > 0:
                summary["warnings"] += 1

        return {"products": preview_products, "summary": summary}
    finally:
        conn.close()


# ── Export (real, async) ─────────────────────────────────────────────────────


def _resolve_export_product_ids(cur, cid: int, selection: PreviewSelection) -> list[int]:
    """Resolve a selection to a concrete product-ID list server-side.

    Mirrors the preview resolution but WITHOUT the 50-product cap, so a
    full "export all" works without loading the catalog into the browser.
    `product_ids` never come from the browser as prices/categories/ids:
    only the internal product ids (or filters) are accepted and everything
    else is resolved from the database inside the engine.
    """
    if not selection.all_matching_filters:
        if not selection.product_ids:
            raise HTTPException(
                status_code=422, detail="Виберіть товари для експорту")
        # De-duplicate without trusting the client beyond internal ids.
        return list(dict.fromkeys(int(x) for x in selection.product_ids))

    sf = selection.filters or PreviewSelectionFilters()
    filters = ["1 = 1"]
    params: list = []
    if sf.q:
        filters.append("(p.sku ILIKE %s OR p.name ILIKE %s)")
        params.extend([f"%{sf.q}%", f"%{sf.q}%"])
    if sf.category_id is not None:
        filters.append(
            "EXISTS (SELECT 1 FROM product_categories pc "
            "WHERE pc.product_id = p.id AND pc.category_id = %s)")
        params.append(sf.category_id)
    if sf.stock_status:
        filters.append("p.stock_status = %s")
        params.append(sf.stock_status)
    if sf.publication_status is not None:
        filters.append("COALESCE(cl.publication_status, 'draft') = %s")
        params.append(sf.publication_status)
    if sf.sync_status is not None:
        filters.append("COALESCE(cl.sync_status, 'idle') = %s")
        params.append(sf.sync_status)
    if sf.has_mapping is not None:
        exists_sql = (
            "EXISTS (SELECT 1 FROM channel_category_mappings ccm "
            "JOIN product_categories pc2 ON pc2.category_id = ccm.internal_category_id "
            "WHERE ccm.channel_id = %s AND ccm.status = 'accepted' "
            "AND pc2.product_id = p.id)")
        if sf.has_mapping:
            filters.append(exists_sql)
        else:
            filters.append("NOT " + exists_sql)
        params.append(cid)

    exclude_sql = ""
    if selection.exclude_ids:
        exclude_sql = " AND p.id != ALL(%s)"
        params.append(list(int(x) for x in selection.exclude_ids))

    where = " AND ".join(filters)
    cur.execute(
        "SELECT p.id FROM products p "
        "LEFT JOIN channel_listings cl "
        "  ON cl.product_id = p.id AND cl.channel_id = %s "
        f"WHERE {where} {exclude_sql} ORDER BY p.id",
        [cid] + params,
    )
    return [r["id"] for r in cur.fetchall()]


class ExportRequest(BaseModel):
    selection: PreviewSelection
    public_base_url: Optional[str] = None


@router.post("/export/channels/{code}/export")
async def start_export(
        code: str,
        body: ExportRequest,
        user=Depends(require_admin),
):
    """Start a real (async) Rozetka export of the selected products.

    Selection is resolved SERVER-SIDE.  Returns immediately with a run_id;
    progress/status is polled via GET .../export/status/{run_id}.
    """
    from app.channels.export_run import (
        ExportRunBusy,
        start_export_run,
        run_export,
    )

    conn, cur = db()
    try:
        ch = _resolve_channel(cur, code)
        cid = ch["id"]
        product_ids = _resolve_export_product_ids(cur, cid, body.selection)
    finally:
        conn.close()

    if not product_ids:
        raise HTTPException(status_code=422,
                            detail="Не вибрано жодного товару для експорту")

    try:
        run_id = start_export_run(cid, product_ids, body.public_base_url,
                                  user_id=user.get("id"))
    except ExportRunBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Offload to a worker thread so the async event loop stays free.
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_export, cid, code, run_id,
                         product_ids, body.public_base_url)

    return {
        "run_id": run_id,
        "status": "queued",
        "total": len(product_ids),
    }


@router.get("/export/channels/{code}/export/status/{run_id}")
async def export_status(
        code: str,
        run_id: int,
        user=Depends(require_admin),
):
    """Poll the live progress/final result of an export run."""
    from app.channels.export_run import get_export_run_status

    conn, cur = db()
    try:
        ch = _resolve_channel(cur, code)
        status = get_export_run_status(cur, ch["id"], run_id)
    finally:
        conn.close()

    if status is None:
        raise HTTPException(status_code=404,
                            detail="Експорт не знайдено")
    return status

# ── Value Mapping Candidates (read-only) ────────────────────────────────────


@router.get("/export/channels/{code}/value-mappings/candidates")
async def value_mapping_candidates(
        code: str,
        q: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        attribute_id: Optional[int] = Query(None),
        external_category_id: Optional[str] = Query(None),
        min_products: int = Query(1, ge=1),
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=200),
        user=Depends(require_admin),
):
    """Paginated list of internal attribute values with their Rozetka mapping
    status, sorted by product count descending.  Supports filtering by Rozetka
    category context via external_category_id.

    Status options: 'unmapped' (default), 'mapped', or None for all.
    """
    conn, cur = db()
    try:
        ch = _resolve_channel(cur, code)
        cid = ch["id"]

        filters = ["1 = 1"]
        params: list = []

        if status == "mapped":
            filters.append("cvm.id IS NOT NULL")
        elif status != "all":
            filters.append("cvm.id IS NULL")  # default: unmapped only

        if q:
            filters.append("(a.name ILIKE %s OR av.value ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])

        if attribute_id is not None:
            filters.append("av.attribute_id = %s")
            params.append(attribute_id)

        if external_category_id:
            filters.append("cvm.external_category_id IS NOT DISTINCT FROM %s")
            params.append(external_category_id)

        filters.append("sq.product_count >= %s")
        params.append(min_products)

        where = " AND ".join(filters)

        # Count query
        count_sql = f"""
            SELECT count(*) AS c FROM (
                SELECT av.attribute_id, av.value, av.id AS av_id,
                       count(DISTINCT pa.product_id) AS product_count
                FROM attribute_values av
                JOIN product_attributes pa ON pa.attribute_id = av.attribute_id
                    AND pa.value_text = av.value
                LEFT JOIN channel_value_mappings cvm
                    ON cvm.internal_value_id = av.id
                    AND cvm.channel_id = %s
                WHERE {where}
                GROUP BY av.attribute_id, av.value, av.id
            ) AS sq
        """
        cur.execute(count_sql, [cid] + params)
        total = cur.fetchone()["c"]

        # Data query
        data_sql = f"""
            SELECT sq.attribute_id, sq.av_id, a.name AS attribute_name,
                   sq.value AS internal_value, sq.product_count,
                   cam.external_attribute_id AS rozetka_attr_id,
                   cea.name AS rozetka_attr_name,
                   cvm.id AS cvm_id,
                   cvm.external_value_id,
                   cvm.external_value_name AS rozetka_value_name,
                   cvm.external_category_id,
                   ec.name AS rozetka_category_name
            FROM (
                SELECT av.attribute_id, av.value, av.id AS av_id,
                       count(DISTINCT pa.product_id) AS product_count
                FROM attribute_values av
                JOIN product_attributes pa ON pa.attribute_id = av.attribute_id
                    AND pa.value_text = av.value
                LEFT JOIN channel_value_mappings cvm
                    ON cvm.internal_value_id = av.id
                    AND cvm.channel_id = %s
                WHERE {where}
                GROUP BY av.attribute_id, av.value, av.id
            ) AS sq
            JOIN attributes a ON a.id = sq.attribute_id
            LEFT JOIN channel_attribute_mappings cam
                ON cam.internal_attribute_id = sq.attribute_id
                AND cam.channel_id = %s AND cam.status = 'accepted'
            LEFT JOIN channel_external_attributes cea
                ON cea.external_id = cam.external_attribute_id
                AND cea.channel_id = %s
            LEFT JOIN channel_value_mappings cvm
                ON cvm.internal_value_id = sq.av_id
                AND cvm.channel_id = %s
            LEFT JOIN channel_external_categories ec
                ON ec.channel_id = %s AND ec.external_id = cvm.external_category_id
            ORDER BY sq.product_count DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(data_sql, [cid] + params + [cid, cid, cid, cid, cid, per_page, (page - 1) * per_page])
        items = []
        for r in cur.fetchall():
            items.append({
                "attribute_id": r["attribute_id"],
                "attribute_name": r["attribute_name"],
                "internal_value_id": r["av_id"],
                "internal_value": r["internal_value"],
                "product_count": r["product_count"],
                "external_attribute_id": r["rozetka_attr_id"],
                "external_attribute_name": r["rozetka_attr_name"],
                "mapped": r["cvm_id"] is not None,
                "external_value_id": r["external_value_id"],
                "external_value_name": r["rozetka_value_name"],
                "external_category_id": r["external_category_id"],
                "external_category_name": r["rozetka_category_name"],
            })

        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()