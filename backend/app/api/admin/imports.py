"""Admin imports API (history, details, launching the EXISTING import runner)."""
import json
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import DB
from app.imports.tasks import run_import

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


IMPORT_STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "ABORTED")
IMPORT_TYPES = ("full", "prices", "stock")


def _parse_job(row: dict) -> dict:
    for src, dst in (("stats_json", "stats"), ("error_details_json", "error_details"),
                     ("raw_config_json", "raw_config")):
        raw = row.pop(src, None)
        if raw:
            try:
                row[dst] = json.loads(raw)
            except (ValueError, TypeError):
                row[dst] = None
        else:
            row[dst] = None
    return row


@router.get("/imports/jobs")
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    supplier_id: Optional[int] = None,
    user: dict = Depends(require_admin),
):
    conn, cur = db()
    try:
        conds, params = ["1=1"], []
        if status:
            if status not in IMPORT_STATUSES:
                raise HTTPException(status_code=400, detail="Невірний статус імпорту")
            conds.append("j.status = %s")
            params.append(status)
        if supplier_id:
            conds.append("j.supplier_id = %s")
            params.append(supplier_id)
        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) AS c FROM import_jobs j WHERE {where}", params)
        total = cur.fetchone()["c"]

        cur.execute(f"""
            SELECT j.id, j.supplier_id, s.name AS supplier_name, j.import_type,
                   j.status, j.started_at, j.finished_at, j.stats_json,
                   j.triggered_by_user_id, j.created_at
            FROM import_jobs j
            LEFT JOIN suppliers s ON s.id = j.supplier_id
            WHERE {where}
            ORDER BY j.id DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, (page - 1) * per_page])
        items = [_parse_job(r) for r in cur.fetchall()]
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/imports/jobs/{jid}")
async def get_job(jid: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("""
            SELECT j.*, s.name AS supplier_name FROM import_jobs j
            LEFT JOIN suppliers s ON s.id = j.supplier_id WHERE j.id = %s
        """, (jid,))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Імпорт не знайдено")
        job = _parse_job(job)

        cur.execute("""SELECT id, level, message, item_ref, created_at
                       FROM import_logs WHERE job_id = %s ORDER BY id DESC LIMIT 200""", (jid,))
        job["logs"] = cur.fetchall()
        return job
    finally:
        conn.close()


class ImportRun(BaseModel):
    supplier_code: str
    import_type: str = "full"


@router.post("/imports/run")
async def run_import_job(
    data: ImportRun,
    background: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Launch the existing import runner in the background."""
    if data.import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=400, detail="Невірний тип імпорту")
    conn, cur = db()
    try:
        cur.execute("SELECT id, name FROM suppliers WHERE code = %s", (data.supplier_code,))
        supplier = cur.fetchone()
    finally:
        conn.close()
    if not supplier:
        raise HTTPException(status_code=404, detail="Постачальника з таким кодом не знайдено")

    background.add_task(run_import, data.supplier_code, data.import_type)
    return {"ok": True, "detail": f"Імпорт '{data.import_type}' для {supplier['name']} запущено"}

