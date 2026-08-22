"""Admin suppliers API."""
import json
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class SupplierIn(BaseModel):
    code: str
    name: str
    enabled: bool = True
    config: Optional[dict] = None


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
        return row
    finally:
        conn.close()


@router.post("/suppliers")
async def create_supplier(data: SupplierIn, user: dict = Depends(require_admin)):
    if not data.code.strip() or not data.name.strip():
        raise HTTPException(status_code=400, detail="Код та назва обов'язкові")
    conn, cur = db()
    try:
        try:
            cur.execute(
                "INSERT INTO suppliers (code, name, enabled, config_json) VALUES (%s,%s,%s,%s) RETURNING id",
                (data.code.strip(), data.name.strip(), data.enabled,
                 json.dumps(data.config) if data.config is not None else None),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="Постачальник з таким кодом вже існує")
        return {"ok": True, "id": cur.fetchone()["id"]}
    finally:
        conn.close()


@router.put("/suppliers/{sid}")
async def update_supplier(sid: int, data: SupplierIn, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT id FROM suppliers WHERE id = %s", (sid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Постачальника не знайдено")
        try:
            cur.execute(
                "UPDATE suppliers SET code=%s, name=%s, enabled=%s, config_json=%s WHERE id=%s",
                (data.code.strip(), data.name.strip(), data.enabled,
                 json.dumps(data.config) if data.config is not None else None, sid),
            )
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="Постачальник з таким кодом вже існує")
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/suppliers/{sid}")
async def delete_supplier(sid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT (SELECT COUNT(*) FROM products WHERE supplier_id=%s)"
                    " + (SELECT COUNT(*) FROM import_jobs WHERE supplier_id=%s) AS c", (sid, sid))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409,
                                detail="Постачальника не можна видалити: існують пов'язані товари або імпорти")
        cur.execute("DELETE FROM supplier_attribute_values sav USING supplier_attributes sa"
                    " WHERE sav.supplier_attribute_id = sa.id AND sa.supplier_id = %s", (sid,))
        cur.execute("DELETE FROM supplier_attributes WHERE supplier_id = %s", (sid,))
        cur.execute("DELETE FROM supplier_categories WHERE supplier_id = %s", (sid,))
        cur.execute("DELETE FROM suppliers WHERE id = %s", (sid,))
        return {"ok": True}
    finally:
        conn.close()

