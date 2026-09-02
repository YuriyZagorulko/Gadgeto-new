"""Admin API for catalog automation (Автоматизація).

All endpoints are synchronous (sync psycopg2) — they run on the FastAPI
threadpool, never on the event loop.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.admin.deps import require_admin, require_admin_role
from app.core.db_connect import admin_cursor
from app.tasks import state
from app.tasks.catalog_sync import run_catalog_sync
from app.tasks.lock import CatalogSyncLock

logger = logging.getLogger("api.admin.automation")
router = APIRouter(tags=["admin-automation"])


class IntervalUpdate(BaseModel):
    """Body for POST /automation/interval (hours between sync STARTs)."""
    interval_hours: int = Field(ge=1, le=8760)


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_run_logs(run_id: int, limit: int = 50) -> list[dict]:
    conn, cur = admin_cursor()
    try:
        cur.execute(
            "SELECT level, message, created_at FROM catalog_sync_logs"
            " WHERE run_id = %s ORDER BY id DESC LIMIT %s",
            (run_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _supplier_summary(run: dict) -> list[dict]:
    import json
    raw = run.get("progress_json")
    if not raw:
        return []
    try:
        prog = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    suppliers = prog.get("suppliers") or []
    out = []
    for s in suppliers:
        job_id = s.get("job_id")
        stats = {}
        if job_id:
            conn2, cur2 = admin_cursor()
            try:
                cur2.execute(
                    "SELECT status, stats_json, error_details_json"
                    " FROM import_jobs WHERE id = %s", (job_id,)
                )
                row = cur2.fetchone()
                if row:
                    stats["status"] = row["status"]
                    try:
                        stats["stats"] = json.loads(row["stats_json"]) if row["stats_json"] else {}
                    except (json.JSONDecodeError, TypeError):
                        stats["stats"] = {}
                    try:
                        stats["error"] = json.loads(row["error_details_json"]) if row["error_details_json"] else None
                    except (json.JSONDecodeError, TypeError):
                        stats["error"] = None
            finally:
                conn2.close()
        out.append({
            "code": s.get("code"),
            "name": s.get("name"),
            "job_id": job_id,
            **stats,
        })
    return out


def _export_summary(run: dict) -> list[dict]:
    import json
    raw = run.get("progress_json")
    if not raw:
        return []
    try:
        prog = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    exports = prog.get("exports") or []
    return list(exports)


# ── endpoints ─────────────────────────────────────────────────────────────────


@router.get("/automation/status")
def automation_status(user=Depends(require_admin)):
    """Current automation status: toggle, schedule, current/last/next run."""
    enabled = state.is_automation_enabled()
    interval = state.get_automation_interval_hours()

    current_run = state.get_running_catalog_run()
    running_run_logs = []
    if current_run:
        running_run_logs = _load_run_logs(current_run["id"], limit=30)
        current_run["logs"] = running_run_logs
        current_run["suppliers"] = _supplier_summary(current_run)
        current_run["exports"] = _export_summary(current_run)

    last_run = None
    conn, cur = admin_cursor()
    try:
        cur.execute(
            "SELECT id, status, trigger, started_at, finished_at,"
            "       progress_json, error_details_json"
            " FROM catalog_sync_runs"
            " WHERE status IN ('SUCCEEDED', 'PARTIAL', 'FAILED', 'SKIPPED')"
            " ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            last_run = dict(row)
            last_run["suppliers"] = _supplier_summary(last_run)
            last_run["exports"] = _export_summary(last_run)
    finally:
        conn.close()

    next_run = state.compute_next_run_at()
    lock_info = CatalogSyncLock().peek()

    return {
        "enabled": enabled,
        "interval_hours": interval,
        "current_run": current_run,
        "last_run": last_run,
        "next_run_at": next_run.isoformat() if next_run else None,
        "lock": lock_info,
    }


@router.get("/automation/history")
def automation_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    user=Depends(require_admin),
):
    """Paginated history of catalog sync runs."""
    result = state.list_catalog_runs(page=page, per_page=per_page)
    runs = result.get("items", [])
    for r in runs:
        r["suppliers"] = _supplier_summary(r)
        r["exports"] = _export_summary(r)
    return result


@router.get("/automation/runs/{run_id}")
def automation_run_detail(run_id: int, user=Depends(require_admin)):
    """Full detail of one catalog sync run."""
    run = state.load_catalog_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Запуск не знайдено")
    run["suppliers"] = _supplier_summary(run)
    run["exports"] = _export_summary(run)
    run["logs"] = _load_run_logs(run_id, limit=100)
    return run


@router.post("/automation/run")
def automation_run_manual(user=Depends(require_admin)):
    """Manual trigger — uses the same orchestrator as the scheduler."""
    if not state.is_automation_enabled():
        raise HTTPException(status_code=409, detail="Автоматизація вимкнена")
    result = run_catalog_sync(trigger="manual", triggered_by_user_id=user.get("id"))
    if result.get("status") == "skipped":
        reason = result.get("reason")
        if reason == "lock-backend-unavailable":
            raise HTTPException(
                status_code=503,
                detail="Служба блокування (Redis) недоступна — запуск неможливий",
            )
        if reason == "automation-disabled":
            raise HTTPException(status_code=409, detail="Автоматизація вимкнена")
        raise HTTPException(
            status_code=409,
            detail="Попередня синхронізація ще виконується",
        )
    return {
        "detail": "Синхронізацію запущено",
        "status": result.get("status"),
        "run_id": result.get("run_id"),
    }


@router.post("/automation/interval")
def automation_set_interval(
    payload: IntervalUpdate,
    user=Depends(require_admin_role),
):
    """Persist the automation interval (hours between sync STARTs).

    The scheduler reads this value from the DB on every hourly Beat tick,
    so the change takes effect without restarting celery-beat.
    """
    try:
        interval = state.set_automation_interval_hours(payload.interval_hours)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="Інтервал має бути додатним цілим числом (годин)",
        )
    next_run = state.compute_next_run_at()
    return {
        "detail": f"Інтервал автоматизації оновлено: кожні {interval} год.",
        "interval_hours": interval,
        "next_run_at": next_run.isoformat() if next_run else None,
    }


@router.post("/automation/enable")
def automation_enable(user=Depends(require_admin_role)):
    """Enable scheduled automation."""
    state.set_automation_enabled(True)
    return {"detail": "Автоматизацію увімкнено", "enabled": True}


@router.post("/automation/disable")
def automation_disable(user=Depends(require_admin_role)):
    """Disable scheduled automation."""
    state.set_automation_enabled(False)
    return {"detail": "Автоматизацію вимкнено", "enabled": False}