"""Admin imports API (history, details, launching the EXISTING import runner)."""
import json
from dataclasses import asdict, is_dataclass

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Any, Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import DB
from app.imports.registry import SUPPLIERS as SYSTEM_SUPPLIERS
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
    if data.supplier_code not in SYSTEM_SUPPLIERS:
        raise HTTPException(status_code=404, detail="Постачальника з таким кодом не знайдено")
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


@router.post("/imports/start")
async def start_import(
    data: ImportRun,
    background: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Create an import job and start it in the background with full persistence."""
    if data.import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=400, detail="Невірний тип імпорту")
    if data.supplier_code not in SYSTEM_SUPPLIERS:
        raise HTTPException(status_code=400, detail="Невірний постачальник")

    conn, cur = db()
    try:
        # Guard: no concurrent import for the same supplier
        cur.execute(
            "SELECT COUNT(*) AS c FROM import_jobs j"
            " JOIN suppliers s ON s.id=j.supplier_id"
            " WHERE s.code=%s AND j.status IN ('QUEUED','RUNNING')",
            (data.supplier_code,),
        )
        if cur.fetchone()["c"]:
            raise HTTPException(
                status_code=409,
                detail=f"Імпорт {data.supplier_code} вже виконується",
            )

        cur.execute("SELECT id FROM suppliers WHERE code=%s", (data.supplier_code,))
        supplier = cur.fetchone()
        if not supplier:
            raise HTTPException(status_code=404, detail="Постачальника не знайдено")

        cur.execute(
            """INSERT INTO import_jobs (supplier_id, import_type, status,
                                        triggered_by_user_id, created_at, updated_at)
               VALUES (%s, %s, 'QUEUED', %s, NOW(), NOW()) RETURNING id""",
            (supplier["id"], data.import_type, user.get("id")),
        )
        job_id = cur.fetchone()["id"]
    finally:
        conn.close()

    from app.imports.importer_service import run_full_import

    background.add_task(run_full_import, data.supplier_code, job_id, supplier["id"], data.import_type)
    return {"ok": True, "job_id": job_id, "detail": f"Імпорт {data.supplier_code} запущено (job #{job_id})"}


@router.get("/imports/jobs/{jid}/progress")
async def get_import_progress(jid: int, user: dict = Depends(require_admin)):
    """Return the current progress of an import job (for frontend polling)."""
    conn, cur = db()
    try:
        cur.execute(
            """SELECT j.id, j.status, j.stats_json, j.error_details_json,
                      j.progress_json, j.current_stage, j.started_at,
                      j.finished_at, s.name AS supplier_name, s.code AS supplier_code
               FROM import_jobs j
               LEFT JOIN suppliers s ON s.id=j.supplier_id
               WHERE j.id=%s""",
            (jid,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Завдання імпорту не знайдено")

        result = {
            "id": row["id"],
            "status": row["status"],
            "supplier_name": row["supplier_name"],
            "supplier_code": row["supplier_code"],
            "current_stage": row["current_stage"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

        if row["progress_json"]:
            try:
                result["progress"] = json.loads(row["progress_json"])
            except (ValueError, TypeError):
                pass
        if row["stats_json"]:
            try:
                result["stats"] = json.loads(row["stats_json"])
            except (ValueError, TypeError):
                pass
        if row["error_details_json"]:
            try:
                result["error_details"] = json.loads(row["error_details_json"])
            except (ValueError, TypeError):
                pass

        # Include recent logs from import_logs table
        cur.execute(
            """SELECT id, level, message, item_ref, created_at
               FROM import_logs WHERE job_id = %s
               ORDER BY id ASC LIMIT 500""",
            (jid,),
        )
        result["logs"] = [
            {
                "id": r["id"],
                "level": r["level"],
                "message": r["message"],
                "item_ref": r["item_ref"],
                "created_at": r["created_at"],
            }
            for r in cur.fetchall()
        ]

        return result
    finally:
        conn.close()


# ------------------------------------------------------------- global actions

GLOBAL_ACTION_TYPES: dict[str, tuple[str, ...]] = {
    "import": ("full",),           # Імпортувати всі товари
    "update": ("prices", "stock"),  # Оновити всі товари (ціни + залишки)
}


def _stats_to_jsonable(value: Any) -> Any:
    """Best-effort conversion of importer stats (dataclass / dict / list) to JSON-safe data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _stats_to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_stats_to_jsonable(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _stats_to_jsonable(asdict(value))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _stats_to_jsonable(to_dict())
    if hasattr(value, "__dict__"):
        return _stats_to_jsonable(vars(value))
    return str(value)


def _run_tracked_import(job_id: int, supplier_code: str, import_type: str) -> None:
    """Background wrapper around the EXISTING ``run_import`` runner that tracks
    execution status/statistics in import_jobs (QUEUED → RUNNING → SUCCEEDED/FAILED)."""
    conn, cur = db()
    try:
        cur.execute(
            "UPDATE import_jobs SET status='RUNNING', started_at=NOW(), updated_at=NOW() WHERE id=%s",
            (job_id,),
        )
    finally:
        conn.close()

    result = run_import(supplier_code, import_type)

    conn, cur = db()
    try:
        if result.get("success"):
            stats = _stats_to_jsonable(result.get("stats"))
            cur.execute(
                "UPDATE import_jobs SET status='SUCCEEDED', finished_at=NOW(), updated_at=NOW(),"
                " stats_json=%s WHERE id=%s",
                (json.dumps(stats, ensure_ascii=False), job_id),
            )
        else:
            cur.execute(
                "UPDATE import_jobs SET status='FAILED', finished_at=NOW(), updated_at=NOW(),"
                " error_details_json=%s WHERE id=%s",
                (json.dumps({"error": result.get("error")}, ensure_ascii=False), job_id),
            )
    finally:
        conn.close()


class GlobalImportRun(BaseModel):
    action: str  # 'import' | 'update'


@router.post("/imports/run-all")
async def run_all_imports(
    data: GlobalImportRun,
    background: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Глобальні дії: launch the EXISTING import runner for ALL enabled suppliers."""
    types = GLOBAL_ACTION_TYPES.get(data.action)
    if not types:
        raise HTTPException(status_code=400, detail="Невірна глобальна дія")

    conn, cur = db()
    try:
        cur.execute("SELECT COUNT(*) AS c FROM import_jobs WHERE status IN ('QUEUED','RUNNING')")
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=409,
                                detail="Наразі вже виконується імпорт. Дочекайтеся завершення активних завдань.")
        cur.execute("SELECT id, code, name FROM suppliers WHERE enabled ORDER BY id")
        suppliers = [s for s in cur.fetchall() if s["code"] in SYSTEM_SUPPLIERS]
    finally:
        conn.close()

    if not suppliers:
        raise HTTPException(status_code=400, detail="Немає активних постачальників для імпорту")

    # Create QUEUED jobs up-front — real progress tracking, and the running-jobs
    # guard above stays effective for requests that arrive while tasks are pending.
    scheduled: list[tuple[int, str, str]] = []
    conn, cur = db()
    try:
        for s in suppliers:
            for t in types:
                cur.execute(
                    """INSERT INTO import_jobs (supplier_id, import_type, status,
                                                triggered_by_user_id, created_at, updated_at)
                       VALUES (%s, %s, 'QUEUED', %s, NOW(), NOW()) RETURNING id""",
                    (s["id"], t, user.get("id")),
                )
                scheduled.append((cur.fetchone()["id"], s["code"], t))
    finally:
        conn.close()

    # Starlette executes background tasks sequentially in insertion order, so
    # suppliers are imported one-by-one without concurrent runs.
    for job_id, code, t in scheduled:
        background.add_task(_run_tracked_import, job_id, code, t)

    verb = "Імпорт" if data.action == "import" else "Оновлення"
    names = ", ".join(s["name"] for s in suppliers)
    return {
        "ok": True,
        "jobs": len(scheduled),
        "suppliers": [s["name"] for s in suppliers],
        "detail": f"{verb} запущено для {len(suppliers)} постачальників ({names}). Завдань у черзі: {len(scheduled)}.",
    }

