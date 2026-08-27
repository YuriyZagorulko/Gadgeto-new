"""Admin imports API (history, details, launching the EXISTING import runner)."""
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Any, Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor
from app.imports.registry import SUPPLIERS as SYSTEM_SUPPLIERS
from app.imports.tasks import run_import
from app.imports.job_health import reconcile_stale_jobs, request_cancellation

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


IMPORT_STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "ABORTED", "STALE", "CANCELLED")
IMPORT_TYPES = ("full", "prices", "stock")


def _parse_job(row: dict) -> dict:
    for src, dst in (("stats_json", "stats"), ("error_details_json", "error_details"),
                     ("raw_config_json", "raw_config"), ("progress_json", "progress")):
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
def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    supplier_id: Optional[int] = None,
    user: dict = Depends(require_admin),
):
    conn, cur = admin_cursor()
    try:
        # Source of truth for staleness lives in the DB — reconcile stale
        # jobs every time the history is viewed.
        try:
            reconcile_stale_jobs()
        except Exception:
            pass

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
                   j.triggered_by_user_id, j.created_at,
                   j.progress_json, j.current_stage, j.current_item,
                   j.heartbeat_at, j.last_activity_at,
                   j.total_count, j.processed_count, j.created_count,
                   j.updated_count, j.skipped_count, j.failed_count,
                   j.error_count, j.warning_count, j.cancel_requested
            FROM import_jobs j
            LEFT JOIN suppliers s ON s.id = j.supplier_id
            WHERE {where}
            ORDER BY j.id DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, (page - 1) * per_page])
        items = [_parse_job(r) for r in cur.fetchall()]
        for item in items:
            item["percent"] = _progress_percent(item)
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


def _progress_percent(item: dict) -> Optional[int]:
    total = item.get("total_count") or 0
    processed = item.get("processed_count") or 0
    if total and total > 0:
        return min(100, round(processed * 100 / total))
    progress = item.get("progress") or {}
    t, p = progress.get("total") or 0, progress.get("processed") or 0
    if t and t > 0:
        return min(100, round(p * 100 / t))
    return None


@router.get("/imports/jobs/{jid}")
def get_job(jid: int, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        try:
            reconcile_stale_jobs()
        except Exception:
            pass
        cur.execute("""
            SELECT j.*, s.name AS supplier_name FROM import_jobs j
            LEFT JOIN suppliers s ON s.id = j.supplier_id WHERE j.id = %s
        """, (jid,))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Імпорт не знайдено")
        job = _parse_job(job)
        job["percent"] = _progress_percent(job)

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
def run_import_job(
    data: ImportRun,
    background: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Launch the existing import runner in a background thread."""
    if data.import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=400, detail="Невірний тип імпорту")
    if data.supplier_code not in SYSTEM_SUPPLIERS:
        raise HTTPException(status_code=404, detail="Постачальника з таким кодом не знайдено")
    conn, cur = admin_cursor()
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
        cur.execute("SELECT id, name FROM suppliers WHERE code = %s", (data.supplier_code,))
        supplier = cur.fetchone()
    finally:
        conn.close()
    if not supplier:
        raise HTTPException(status_code=404, detail="Постачальника з таким кодом не знайдено")

    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_import, data.supplier_code, data.import_type)
    return {"ok": True, "detail": f"Імпорт '{data.import_type}' для {supplier['name']} запущено"}


@router.post("/imports/start")
def start_import(
    data: ImportRun,
    background: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Create an import job and start it in a background thread."""
    if data.import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=400, detail="Невірний тип імпорту")
    if data.supplier_code not in SYSTEM_SUPPLIERS:
        raise HTTPException(status_code=400, detail="Невірний постачальник")

    conn, cur = admin_cursor()
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

    # Offload the blocking import to a thread pool so the async event
    # loop remains free to serve HTTP requests (health, admin API, …).
    # BackgroundTasks runs synchronously in the event loop and would
    # block all request handling for the duration of the import.
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None, run_full_import, data.supplier_code, job_id, supplier["id"], data.import_type,
    )
    return {"ok": True, "job_id": job_id, "detail": f"Імпорт {data.supplier_code} запущено (job #{job_id})"}


@router.get("/imports/jobs/{jid}/progress")
def get_import_progress(jid: int, user: dict = Depends(require_admin)):
    """Return the current progress of an import job (for frontend polling)."""
    conn, cur = admin_cursor()
    try:
        try:
            reconcile_stale_jobs()
        except Exception:
            pass
        cur.execute(
            """SELECT j.id, j.status, j.stats_json, j.error_details_json,
                      j.progress_json, j.current_stage, j.current_item,
                      j.heartbeat_at, j.last_activity_at,
                      j.total_count, j.processed_count, j.created_count,
                      j.updated_count, j.skipped_count, j.failed_count,
                      j.error_count, j.warning_count, j.cancel_requested,
                      j.started_at, j.finished_at,
                      s.name AS supplier_name, s.code AS supplier_code
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
            "current_item": row["current_item"],
            "heartbeat_at": row["heartbeat_at"],
            "last_activity_at": row["last_activity_at"],
            "total_count": row["total_count"],
            "processed_count": row["processed_count"],
            "created_count": row["created_count"],
            "updated_count": row["updated_count"],
            "skipped_count": row["skipped_count"],
            "failed_count": row["failed_count"],
            "error_count": row["error_count"],
            "warning_count": row["warning_count"],
            "cancel_requested": row["cancel_requested"],
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
        result["percent"] = _progress_percent(result)

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


@router.post("/imports/jobs/{jid}/cancel")
def cancel_import_job(jid: int, user: dict = Depends(require_admin)):
    """Request cancellation of a running/queued import job.

    Does NOT delete the record. If the worker has a live heartbeat it will
    stop cooperatively at the next safe point; otherwise the job is marked
    CANCELLED immediately.
    """
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT status FROM import_jobs WHERE id=%s", (jid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Імпорт не знайдено")
        if row["status"] not in ("QUEUED", "RUNNING", "STALE"):
            raise HTTPException(
                status_code=409,
                detail="Імпорт можна скасувати лише у статусах QUEUED/RUNNING/STALE.",
            )
    finally:
        conn.close()

    result = request_cancellation(jid)
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return {"ok": True, "job_id": jid, **result}


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
    """Background wrapper around the FULL import pipeline that tracks
    execution status/statistics in import_jobs (QUEUED → RUNNING → SUCCEEDED/FAILED)."""
    # Get supplier_id from the job
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT supplier_id FROM import_jobs WHERE id=%s", (job_id,))
        row = cur.fetchone()
        if not row:
            return  # job vanished — nothing to do
        supplier_id = row["supplier_id"]
        cur.execute(
            "UPDATE import_jobs SET status='RUNNING', started_at=NOW(), "
            "heartbeat_at=NOW(), last_activity_at=NOW(), updated_at=NOW() WHERE id=%s",
            (job_id,),
        )
    finally:
        conn.close()

    # Call the FULL import pipeline that parses AND persists products
    from app.imports.importer_service import run_full_import
    result = run_full_import(supplier_code, job_id, supplier_id, import_type)

    # Stats are already saved by run_full_import — update job status if needed
    # (run_full_import handles status/success/failure internally)


class BulkDeleteRequest(BaseModel):
    ids: list[int]


class BulkDeleteResponse(BaseModel):
    deleted: int
    skipped: int
    errors: list[dict]


@router.delete("/imports/jobs/{jid}")
def delete_job(jid: int, user: dict = Depends(require_admin)):
    """Видалити окремий запис історії імпорту."""
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id, status FROM import_jobs WHERE id = %s", (jid,))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Імпорт не знайдено")
        if job["status"] in ("QUEUED", "RUNNING"):
            raise HTTPException(
                status_code=409,
                detail="Не можна видалити активний імпорт (статус: QUEUED або RUNNING).",
            )
        # Delete dependent logs first (no CASCADE on FK)
        cur.execute("DELETE FROM import_logs WHERE job_id = %s", (jid,))
        cur.execute("DELETE FROM import_jobs WHERE id = %s", (jid,))
        return {"ok": True, "detail": "Імпорт #{} видалено.".format(jid)}
    finally:
        conn.close()


@router.post("/imports/jobs/bulk-delete")
def bulk_delete_jobs(data: BulkDeleteRequest, user: dict = Depends(require_admin)):
    """Видалити декілька записів історії імпорту (транзакційно)."""
    if not data.ids:
        raise HTTPException(status_code=400, detail="Список ID для видалення порожній.")
    conn, cur = admin_cursor()
    try:
        cur.execute(
            "SELECT id, status FROM import_jobs WHERE id = ANY(%s)",
            (data.ids,),
        )
        jobs = {r["id"]: r["status"] for r in cur.fetchall()}
        to_delete = []
        errors = []
        for jid in data.ids:
            if jid not in jobs:
                errors.append({"id": jid, "reason": "Імпорт не знайдено."})
            elif jobs[jid] in ("QUEUED", "RUNNING"):
                errors.append({"id": jid, "reason": "Активний імпорт не можна видалити."})
            else:
                to_delete.append(jid)
        if to_delete:
            cur.execute("DELETE FROM import_logs WHERE job_id = ANY(%s)", (to_delete,))
            cur.execute("DELETE FROM import_jobs WHERE id = ANY(%s)", (to_delete,))
        return {
            "deleted": len(to_delete),
            "skipped": len(errors),
            "errors": errors,
            "detail": "Видалено: {}, пропущено: {}.".format(len(to_delete), len(errors)),
        }
    finally:
        conn.close()


class GlobalImportRun(BaseModel):
    action: str  # 'import' | 'update'


@router.post("/imports/run-all")
def run_all_imports(
    data: GlobalImportRun,
    background: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Глобальні дії: launch the EXISTING import runner for ALL enabled suppliers."""
    types = GLOBAL_ACTION_TYPES.get(data.action)
    if not types:
        raise HTTPException(status_code=400, detail="Невірна глобальна дія")

    conn, cur = admin_cursor()
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
    conn, cur = admin_cursor()
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

    # Offload each scheduled job to the thread pool via a single wrapper
    # that runs all jobs sequentially (the DB-level concurrency guard
    # prevents duplicate jobs).
    import asyncio
    loop = asyncio.get_event_loop()

    def _run_all():
        for job_id, code, t in scheduled:
            _run_tracked_import(job_id, code, t)

    loop.run_in_executor(None, _run_all)

    verb = "Імпорт" if data.action == "import" else "Оновлення"
    names = ", ".join(s["name"] for s in suppliers)
    return {
        "ok": True,
        "jobs": len(scheduled),
        "suppliers": [s["name"] for s in suppliers],
        "detail": f"{verb} запущено для {len(suppliers)} постачальників ({names}). Завдань у черзі: {len(scheduled)}.",
    }



@router.get("/imports/jobs/{jid}/report")
def get_job_report(jid: int, user: dict = Depends(require_admin)):
    """Detailed import report with structured unmapped data."""
    conn, cur = admin_cursor()
    try:
        try:
            reconcile_stale_jobs()
        except Exception:
            pass
        cur.execute("""
            SELECT j.*, s.name AS supplier_name FROM import_jobs j
            LEFT JOIN suppliers s ON s.id = j.supplier_id WHERE j.id = %s
        """, (jid,))
        job = cur.fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Імпорт не знайдено")
        job = _parse_job(job)
        job["percent"] = _progress_percent(job)

        stats = job.get("stats") or {}
        report = _build_import_report(job, stats)

        cur.execute("""SELECT id, level, message, item_ref, created_at
                       FROM import_logs WHERE job_id = %s ORDER BY id DESC LIMIT 500""", (jid,))
        report["logs"] = cur.fetchall()
        return report
    finally:
        conn.close()


def _build_import_report(job: dict, stats: dict) -> dict:
    """Build standardized import report from job + stats."""
    def _parse_legacy(d, legacy_key):
        if d:
            return d
        lc = stats.get(legacy_key, 0)
        if lc:
            return {"*": {"count": lc, "id": None, "skus": []}}
        return {}

    report = {
        "id": job["id"],
        "supplier_id": job.get("supplier_id"),
        "supplier_name": job.get("supplier_name"),
        "import_type": job.get("import_type"),
        "status": job.get("status"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "created_at": job.get("created_at"),
        "duration": _calc_duration(job.get("started_at"), job.get("finished_at")),
        "percent": job.get("percent"),
        "current_stage": job.get("current_stage"),
        "total_count": job.get("total_count", 0) or 0,
        "processed_count": job.get("processed_count", 0) or 0,
        "created_count": job.get("created_count", 0) or 0,
        "updated_count": job.get("updated_count", 0) or 0,
        "skipped_count": job.get("skipped_count", 0) or 0,
        "failed_count": job.get("failed_count", 0) or 0,
        "error_count": job.get("error_count", 0) or 0,
        "warning_count": job.get("warning_count", 0) or 0,
    }

    report["unmapped_categories"] = _parse_legacy(
        stats.get("unmapped_categories") or {}, "unknown_categories")
    report["unmapped_attributes"] = _parse_legacy(
        stats.get("unmapped_attributes") or {}, "unknown_attributes")

    unmapped_vals = stats.get("unmapped_attribute_values") or {}
    if not unmapped_vals and stats.get("unknown_attribute_values"):
        uv = stats["unknown_attribute_values"]
        unmapped_vals = {"*": {"*": {"count": uv, "skus": []}}} if uv else {}
    report["unmapped_attribute_values"] = unmapped_vals

    report["unmapped_categories_count"] = (
        len(report["unmapped_categories"]) if report["unmapped_categories"]
        else (stats.get("unknown_categories", 0) or 0))
    report["unmapped_attributes_count"] = (
        len(report["unmapped_attributes"]) if report["unmapped_attributes"]
        else (stats.get("unknown_attributes", 0) or 0))
    total_val_groups = 0
    for v in report["unmapped_attribute_values"].values():
        if isinstance(v, dict):
            total_val_groups += len(v)
    report["unmapped_attribute_values_count"] = (
        total_val_groups or (stats.get("unknown_attribute_values", 0) or 0))

    report["warnings"] = stats.get("warnings", []) or []
    report["errors"] = stats.get("errors", []) or []
    has_unmapped = (report["unmapped_categories_count"] > 0
                    or report["unmapped_attributes_count"] > 0
                    or report["unmapped_attribute_values_count"] > 0)
    report["has_unmapped"] = has_unmapped
    report["has_errors"] = bool(report["errors"])

    raw = (job.get("status") or "").strip().upper()
    if raw == "SUCCEEDED":
        report["display_status"] = "COMPLETED_WITH_WARNINGS" if has_unmapped else "COMPLETED"
    else:
        report["display_status"] = raw

    err = job.get("error_details")
    if err:
        if isinstance(err, dict) and "error" in err:
            report["error_message"] = err["error"]
        elif isinstance(err, str):
            report["error_message"] = err
        else:
            report["error_message"] = str(err)

    return report


def _calc_duration(started: Optional[str], finished: Optional[str]) -> Optional[int]:
    """Duration in seconds, or None."""
    if not started:
        return None
    try:
        a = datetime.fromisoformat(started)
        b = datetime.fromisoformat(finished) if finished else datetime.utcnow()
        return int((b - a).total_seconds())
    except (ValueError, TypeError):
        return None
