"""Admin API for Prom.ua pricing/commission management (infrastructure only).

Provides read-only status/rules endpoints mirroring the Rozetka pricing API
(``app.api.admin.rozetka_pricing``).  Because Prom.ua has no credentials and no
documented pricing/commission format yet, there is nothing to import: the
``/import`` endpoint returns a clean application-level error instead of
inventing a Prom.ua file format, and no Prom.ua commission rates are seeded.
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor
from app.channels.prom.client import PROM_NOT_CONFIGURED_MESSAGE

router = APIRouter()


def _get_active_import(cur):
    cur.execute("""
        SELECT id, original_filename, status, total_rows, categories_found,
               rules_imported, invalid_rows, duplicate_rows, errors_json,
               created_at, updated_at
        FROM prom_pricing_imports
        WHERE is_active = true
        ORDER BY id DESC LIMIT 1
    """)
    return cur.fetchone()


@router.get("/pricing/prom/status")
def pricing_status(user=Depends(require_admin)):
    """Prom.ua pricing status.  No active import exists until credentials/
    commission documentation are available."""
    conn, cur = admin_cursor()
    try:
        active = _get_active_import(cur)
        if not active:
            return {"active": False, "imports": [], "detail": PROM_NOT_CONFIGURED_MESSAGE}
        return {"active": True, "import_id": active["id"],
                "filename": active["original_filename"], "status": active["status"],
                "total_rows": active["total_rows"],
                "categories_found": active["categories_found"],
                "rules_imported": active["rules_imported"],
                "invalid_rows": active["invalid_rows"],
                "duplicate_rows": active["duplicate_rows"]}
    finally:
        conn.close()


@router.post("/pricing/prom/import")
async def import_pricing_file(file=None, user=Depends(require_admin)):
    """Prom.ua pricing/commission import is intentionally unsupported yet.

    Returning a clean application-level error (NOT a real API call) until the
    Prom.ua pricing format is documented.
    """
    raise HTTPException(
        status_code=422,
        detail="Prom.ua pricing import is not available yet: "
               + PROM_NOT_CONFIGURED_MESSAGE,
    )


@router.get("/pricing/prom/rules")
def list_pricing_rules(
        q: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=200),
        user=Depends(require_admin),
):
    """Prom.ua pricing rules (empty until configured)."""
    conn, cur = admin_cursor()
    try:
        active = _get_active_import(cur)
        if not active:
            return {"items": [], "total": 0, "page": page, "per_page": per_page,
                    "import_id": None, "detail": PROM_NOT_CONFIGURED_MESSAGE}

        import_id = active["id"]
        filters = ["r.import_id = %s"]
        params: list = [import_id]
        where = " AND ".join(filters)
        cur.execute(f"SELECT count(*) AS c FROM prom_category_pricing_rules r WHERE {where}", params)
        total = cur.fetchone()["c"]
        cur.execute(f"""
            SELECT r.id, r.external_category_id, r.category_name, r.brand,
                   r.price_min, r.price_max, r.commission_percent, r.created_at
            FROM prom_category_pricing_rules r
            WHERE {where}
            ORDER BY r.category_name, r.price_min NULLS LAST, r.brand NULLS LAST
            LIMIT %s OFFSET %s
        """, params + [per_page, (page - 1) * per_page])
        return {"items": [dict(r) for r in cur.fetchall()], "total": total,
                "page": page, "per_page": per_page, "import_id": import_id}
    finally:
        conn.close()