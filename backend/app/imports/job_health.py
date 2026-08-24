"""Import job lifecycle helpers.

Central place for:
- stale-job reconciliation (jobs left RUNNING/QUEUED with no heartbeat),
- cooperative cancellation,
- label maps for import stages/statuses.

The heartbeat/status columns are persisted on `import_jobs`; the importer
writes them directly. This module only reads/transitions state.
"""

import json
import os
from typing import Optional

import psycopg2

from app.core.db_connect import DB

# Default staleness threshold. The import runner reports progress at least
# every N products and also runs a lightweight heartbeat thread, so a
# RUNNING job without a fresh heartbeat genuinely means the worker is gone,
# hung, or the process/container restarted. Configurable via env
# IMPORT_STALE_TIMEOUT_MIN if a given supplier stage legitimately runs longer.
DEFAULT_STALE_TIMEOUT_MIN = 10

RESTART_REASON = "Import interrupted because the backend process/container restarted."
CANCEL_DONE_MSG = "Імпорт скасовано адміністратором."
CANCEL_PENDING_MSG = "Скасування імпорту запитане адміністратором. Робота зупинниться на безпечній точці."

# Human-readable Ukrainian labels for the progress stages the importers emit.
STAGE_LABELS = {
    "initializing": "Ініціалізація імпорту",
    "authenticating": "Авторизація",
    "downloading": "Завантаження каталогу",
    "parsing": "Розбір каталогу",
    "products": "Обробка товарів",
    "finalizing": "Завершення",
    "completed": "Імпорт завершено",
}


def stale_timeout_seconds() -> int:
    return int(os.getenv("IMPORT_STALE_TIMEOUT_MIN", str(DEFAULT_STALE_TIMEOUT_MIN))) * 60


def _stale_where() -> str:
    """SQL predicate that is TRUE when a RUNNING/QUEUED job is stale.

    A job is stale when its heartbeat is older than the timeout. Jobs that
    never got a heartbeat (QUEUED, or RUNNING with NULL heartbeat) fall back
    to `updated_at` so they cannot remain QUEUED/RUNNING forever either.
    """
    timeout_min = int(os.getenv("IMPORT_STALE_TIMEOUT_MIN", str(DEFAULT_STALE_TIMEOUT_MIN)))
    return (
        "(status IN ('QUEUED','RUNNING') AND ("
        f" (heartbeat_at IS NOT NULL AND heartbeat_at < NOW() - interval '{timeout_min} minutes')"
        f" OR (heartbeat_at IS NULL AND last_activity_at IS NOT NULL AND last_activity_at < NOW() - interval '{timeout_min} minutes')"
        f" OR (heartbeat_at IS NULL AND last_activity_at IS NULL AND updated_at < NOW() - interval '{timeout_min} minutes')"
        "))"
    )


def reconcile_stale_jobs(reason: Optional[str] = None) -> list[int]:
    """Mark RUNNING/QUEUED jobs whose heartbeat is stale as STALE.

    Returns the ids of affected jobs. Safe, idempotent, cheap (one UPDATE).
    `reason` is stored in error_details_json (used on backend startup).
    """
    if reason is None:
        timeout_min = int(os.getenv("IMPORT_STALE_TIMEOUT_MIN", str(DEFAULT_STALE_TIMEOUT_MIN)))
        reason = f"Імпорт зависнув: активність (heartbeat) не оновлювалась понад {timeout_min} хвилин."
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE import_jobs SET status='STALE', finished_at=NOW(), updated_at=NOW(), "
            f"error_details_json=%s WHERE {_stale_where()} RETURNING id",
            (json.dumps({"reason": reason}, ensure_ascii=False),),
        )
        affected = [r[0] for r in cur.fetchall()]
        cur.close()
        for jid in affected:
            try:
                _append_log(conn, jid, "ERROR", reason)
            except Exception:
                pass
        return affected
    finally:
        conn.close()


def refresh_heartbeat(job_id: int) -> None:
    """Touch heartbeat_at for a RUNNING job (called periodically)."""
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE import_jobs SET heartbeat_at=NOW(), updated_at=NOW()"
            " WHERE id=%s AND status='RUNNING'",
            (job_id,),
        )
        cur.close()
    finally:
        conn.close()


def is_cancelled(job_id: int) -> bool:
    """True if the job should stop cooperatively (CANCELLED or requested)."""
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, cancel_requested FROM import_jobs WHERE id=%s",
            (job_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return True
        status, cancel_requested = row
        return status == "CANCELLED" or bool(cancel_requested)
    finally:
        conn.close()


def request_cancellation(job_id: int) -> dict:
    """Request cancellation of a running job.

    - If the job has no live heartbeat (worker gone/hung), transition it
      immediately to CANCELLED.
    - Otherwise set cancel_requested and let the worker stop at a safe point.
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status, heartbeat_at FROM import_jobs WHERE id=%s",
            (job_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"error": "Імпорт не знайдено"}
        status = row[0]
        if status not in ("QUEUED", "RUNNING", "STALE"):
            return {"error": "Активний імпорт можна скасувати лише у статусі QUEUED/RUNNING/STALE."}

        heartbeat_at = row[1]
        worker_alive = status != "STALE" and heartbeat_at is not None and _is_fresh(heartbeat_at)

        if worker_alive:
            cur.execute(
                "UPDATE import_jobs SET cancel_requested=TRUE, updated_at=NOW()"
                " WHERE id=%s AND status='RUNNING'",
                (job_id,),
            )
            try:
                _append_log(conn, job_id, "INFO", CANCEL_PENDING_MSG)
            except Exception:
                pass
            return {
                "status": status,
                "cancelled_done": False,
                "detail": "Скасування запитано. Робота зупиниться на безпечній точці.",
            }

        # No live worker — transition immediately (this also covers STALE).
        cur.execute(
            "UPDATE import_jobs SET status='CANCELLED', finished_at=NOW(), updated_at=NOW(), "
            "cancel_requested=TRUE, error_details_json=%s WHERE id=%s",
            (json.dumps({"reason": CANCEL_DONE_MSG}, ensure_ascii=False), job_id),
        )
        try:
            _append_log(conn, job_id, "INFO", CANCEL_DONE_MSG)
        except Exception:
            pass
        return {
            "status": "CANCELLED",
            "cancelled_done": True,
            "detail": "Імпорт перервано адміністратором.",
        }
    finally:
        conn.close()


def _is_fresh(ts) -> bool:
    from datetime import datetime, timedelta, timezone

    if not ts:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts) < timedelta(seconds=stale_timeout_seconds())


def _append_log(conn, job_id: int, level: str, message: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO import_logs (job_id, level, message, created_at, updated_at)"
            " VALUES (%s, %s, %s, NOW(), NOW())",
            (job_id, level, message),
        )
    finally:
        cur.close()