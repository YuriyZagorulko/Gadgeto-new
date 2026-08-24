import json
from typing import Optional, List
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query, Depends

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
            SELECT s.id, s.code, s.name, s.enabled, s.config_json,
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
        items = cur.fetchall()
        # Parse config_json for each item
        for item in items:
            try:
                item["config"] = json.loads(item.pop("config_json")) if item.get("config_json") else {}
            except (ValueError, TypeError):
                item["config"] = {}
        return {"items": items, "total": total, "page": page, "per_page": per_page}
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


class SupplierConfigUpdate(BaseModel):
    config: dict


@router.put("/suppliers/{sid}/config")
async def update_supplier_config(sid: int, body: SupplierConfigUpdate, user: dict = Depends(require_admin)):
    """Update supplier config_json (e.g. image storage settings)."""
    conn, cur = db()
    try:
        cur.execute("SELECT id FROM suppliers WHERE id = %s", (sid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Постачальника не знайдено")
        cur.execute(
            "UPDATE suppliers SET config_json = %s WHERE id = %s",
            (json.dumps(body.config, ensure_ascii=False), sid),
        )
        return {"ok": True, "config": body.config}
    finally:
        conn.close()


