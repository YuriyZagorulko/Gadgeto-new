"""Admin export history API (reuses sync_runs table, run_type='EXPORT')."""
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

router = APIRouter()

RUN_TYPE = "EXPORT"
VALID_STATUSES = {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "PARTIAL", "CANCELLED"}
PER_PAGE_DEFAULT = 25


def _resolve_rozetka_channel(cur) -> dict:
    cur.execute("SELECT id, code, name FROM channels WHERE code='rozetka'")
    ch = cur.fetchone()
    if not ch:
        raise HTTPException(status_code=404, detail="Канал Rozetka не знайдено")
    return ch


def _populate_progress(run: dict) -> dict:
    """Parse progress_json into structured fields."""
    raw = run.pop("progress_json", None) or "{}"
    try:
        run["progress"] = json.loads(raw)
    except (ValueError, TypeError):
        run["progress"] = {}
    return run


def _fmt_duration(started_at, finished_at) -> Optional[int]:
    if not started_at:
        return None
    try:
        a = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00")) if finished_at else datetime.utcnow()
        return int((b - a).total_seconds())
    except (ValueError, TypeError):
        return None


@router.get("/export/channels/{code}/history")
def export_history_list(
    code: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(PER_PAGE_DEFAULT, ge=1, le=100),
    status: Optional[str] = Query(None),
    user=Depends(require_admin),
):
    """Paginated list of export runs for the given channel."""
    conn, cur = admin_cursor()
    try:
        ch = _resolve_rozetka_channel(cur)
        cid = ch["id"]

        conds = ["sr.channel_id=%s", "sr.run_type=%s"]
        params: list = [cid, RUN_TYPE]

        if status and status.upper() in VALID_STATUSES:
            conds.append("sr.status=%s")
            params.append(status.upper())
        elif status:
            raise HTTPException(status_code=400, detail="Невірний статус експорту")

        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) AS c FROM sync_runs sr WHERE {where}", params)
        total = cur.fetchone()["c"]

        cur.execute(f"""
            SELECT sr.id, sr.channel_id, sr.run_type, sr.status,
                   sr.started_at, sr.finished_at, sr.created_at,
                   sr.total_count, sr.processed_count,
                   sr.created_count, sr.updated_count,
                   sr.failed_count, sr.skipped_count,
                   sr.progress_json, sr.current_stage,
                   sr.cancel_requested,
                   sr.triggered_by_user_id
            FROM sync_runs sr
            WHERE {where}
            ORDER BY sr.id DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, (page - 1) * per_page])

        rows = cur.fetchall()
        for r in rows:
            r["duration"] = _fmt_duration(r.get("started_at"), r.get("finished_at"))

        return {
            "items": rows,
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    finally:
        conn.close()


@router.get("/export/channels/{code}/history/{run_id}")
def export_history_detail(
    code: str,
    run_id: int,
    user=Depends(require_admin),
):
    """Full detail of one export run, including progress/logs and per-product results."""
    conn, cur = admin_cursor()
    try:
        ch = _resolve_rozetka_channel(cur)
        cid = ch["id"]

        cur.execute("""
            SELECT sr.*
            FROM sync_runs sr
            WHERE sr.id=%s AND sr.channel_id=%s AND sr.run_type=%s
        """, (run_id, cid, RUN_TYPE))
        run = cur.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Експорт не знайдено")

        run = _populate_progress(run)
        run["duration"] = _fmt_duration(run.get("started_at"), run.get("finished_at"))

        prog = run.get("progress", {})

        # Extract logs from progress_json
        logs = prog.get("logs", [])
        run["logs"] = logs
        run["logs_count"] = len(logs)

        # Extract per-product results
        results = prog.get("results", [])
        run["results"] = results

        # Error details
        error_details = prog.get("error_details", None)
        run["error_details"] = error_details

        return run
    finally:
        conn.close()


@router.post("/export/channels/{code}/export/{run_id}/cancel")
def cancel_export_run(code: str, run_id: int, user=Depends(require_admin)):
    """Request cancellation of a running/queued export run.

    Sets cancel_requested so the worker stops at the next safe point.
    If the worker has no live heartbeat, transitions to CANCELLED immediately.
    """
    conn, cur = admin_cursor()
    try:
        ch = _resolve_rozetka_channel(cur)
        cid = ch["id"]

        cur.execute("""
            SELECT id, status, heartbeat_at FROM sync_runs
            WHERE id=%s AND channel_id=%s AND run_type=%s
        """, (run_id, cid, RUN_TYPE))
        run = cur.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Експорт не знайдено")

        status = run["status"]
        if status not in ("QUEUED", "RUNNING"):
            raise HTTPException(
                status_code=409,
                detail="Експорт можна скасувати лише у статусах QUEUED або RUNNING.",
            )

        heartbeat_at = run.get("heartbeat_at")
        worker_alive = status == "RUNNING" and heartbeat_at is not None

        if worker_alive:
            cur.execute(
                "UPDATE sync_runs SET cancel_requested=TRUE, updated_at=NOW()"
                " WHERE id=%s AND status='RUNNING'",
                (run_id,),
            )
            conn.commit()
            return {
                "cancelled_done": False,
                "detail": "Скасування запитано. Експорт зупиниться на безпечній точці.",
            }

        # No live worker — transition immediately
        cur.execute(
            "UPDATE sync_runs SET status='CANCELLED', finished_at=NOW(), updated_at=NOW(),"
            " cancel_requested=TRUE, heartbeat_at=NOW() WHERE id=%s",
            (run_id,),
        )
        conn.commit()
        return {
            "cancelled_done": True,
            "detail": "Експорт перервано адміністратором.",
        }
    finally:
        conn.close()


@router.delete("/export/channels/{code}/history/{run_id}")
def export_history_delete(
    code: str,
    run_id: int,
    user=Depends(require_admin),
):
    """Delete an export history record. Does NOT modify products or listings."""
    conn, cur = admin_cursor()
    try:
        ch = _resolve_rozetka_channel(cur)
        cid = ch["id"]

        cur.execute("""
            SELECT id, status FROM sync_runs
            WHERE id=%s AND channel_id=%s AND run_type=%s
        """, (run_id, cid, RUN_TYPE))
        run = cur.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Експорт не знайдено")

        if run["status"] in ("QUEUED", "RUNNING"):
            raise HTTPException(status_code=409,
                                detail="Неможливо видалити експорт, який виконується. Зачекайте завершення.")

        # Delete related sync_jobs and sync_logs (cascade handled by FK, but do explicitly)
        cur.execute("""
            DELETE FROM sync_logs
            WHERE job_id IN (SELECT id FROM sync_jobs WHERE run_id=%s)
        """, (run_id,))
        cur.execute("DELETE FROM sync_jobs WHERE run_id=%s", (run_id,))
        cur.execute("DELETE FROM sync_runs WHERE id=%s", (run_id,))
        conn.commit()
        return {"ok": True, "detail": "Експорт видалено"}
    finally:
        conn.close()