"""Admin suppliers API (read-only).

Suppliers are FIXED system integrations defined in ``app.imports.registry``.
Their rows in the ``suppliers`` table are SYSTEM DATA created by the idempotent
seed migration (012_system_suppliers). Administrators can view them and run
their imports but must never create/edit/delete them.
"""
import json
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import DB
from app.imports.registry import SUPPLIERS as SYSTEM_SUPPLIERS

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


@router.get("/suppliers")
async def list_suppliers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    conn, cur = db()
    try:
        conds, params = ["1=1"], []
        if q:
            conds.append("(s.code ILIKE %s OR s.name ILIKE %s)")
            params += [f"%{q}%", f"%{q}%"]
        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) AS c FROM suppliers s WHERE {where}", params)
        total = cur.fetchone()["c"]

        cur.execute(f"""
            SELECT s.id, s.code, s.name, s.enabled,
                   (SELECT COUNT(*) FROM products p WHERE p.supplier_id = s.id) AS products_count,
                   (SELECT COUNT(*) FROM supplier_categories sc
                      WHERE sc.supplier_id = s.id AND NOT sc.is_removed) AS categories_count,
                   (SELECT COUNT(*) FROM supplier_attributes sa
                      WHERE sa.supplier_id = s.id AND NOT sa.is_removed) AS attributes_count,
                   (SELECT COUNT(*) FROM import_jobs j WHERE j.supplier_id = s.id) AS imports_count,
                   (SELECT MAX(j.finished_at) FROM import_jobs j WHERE j.supplier_id = s.id) AS last_import_at
            FROM suppliers s
            WHERE {where}
            ORDER BY s.name
            LIMIT %s OFFSET %s
        """, params + [per_page, (page - 1) * per_page])
        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/suppliers/{sid}")
async def get_supplier(sid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT * FROM suppliers WHERE id = %s", (sid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Постачальника не знайдено")
        try:
            row["config"] = json.loads(row.pop("config_json") or "null")
        except (ValueError, TypeError):
            row["config"] = None
        cur.execute("""
            SELECT status, COUNT(*) AS c FROM import_jobs
            WHERE supplier_id = %s GROUP BY status
        """, (sid,))
        row["imports_by_status"] = {r["status"]: r["c"] for r in cur.fetchall()}
        row["is_system"] = row["code"] in SYSTEM_SUPPLIERS
        return row
    finally:
        conn.close()


