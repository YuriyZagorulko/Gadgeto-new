"""Database state helpers for the catalog automation.

Owns every write to `catalog_sync_runs` / `catalog_sync_logs` and the small
amount of orchestration bookkeeping on the EXISTING tables (creating import
jobs, resetting a job for a retry).  Import/export engines keep their own
state in import_jobs / sync_runs — nothing here duplicates that.

All functions are plain synchronous psycopg2 (they run inside Celery workers
or the admin API, never on the FastAPI event loop path directly).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from app.core.config import settings
from app.core.db_connect import DB, connect as db_connect
from app.imports.registry import SUPPLIERS as SYSTEM_SUPPLIERS

logger = logging.getLogger("tasks.state")

SETTING_ENABLED_KEY = "catalog_sync_enabled"

_REAL_DICT = psycopg2.extras.RealDictCursor

RUN_RUNNING = "RUNNING"
RUN_SUCCEEDED = "SUCCEEDED"
RUN_PARTIAL = "PARTIAL"
RUN_FAILED = "FAILED"
RUN_SKIPPED = "SKIPPED"

_TRUTHY = {"true", "1", "yes", "on", "так"}


# ── connections ─────────────────────────────────────────────────────────────

def _cur():
    conn = db_connect()
    return conn, conn.cursor(cursor_factory=_REAL_DICT)


# ── automation master switch (DB `settings` overrides env default) ──────────

def is_automation_enabled() -> bool:
    conn, cur = _cur()
    try:
        cur.execute("SELECT value FROM settings WHERE key = %s", (SETTING_ENABLED_KEY,))
        row = cur.fetchone()
        if row and row["value"] is not None:
            return str(row["value"]).strip().lower() in _TRUTHY
    except Exception:
        logger.warning("Could not read automation toggle, using env default", exc_info=True)
    finally:
        conn.close()
    return bool(settings.CATALOG_SYNC_ENABLED)


def set_automation_enabled(enabled: bool) -> None:
    conn, cur = _cur()
    try:
        value = "true" if enabled else "false"
        cur.execute(
            "INSERT INTO settings (key, value, is_secret, created_at, updated_at)"
            " VALUES (%s, %s, FALSE, NOW(), NOW())"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
            (SETTING_ENABLED_KEY, value),
        )
    finally:
        conn.close()


# ── automation interval (DB `settings` overrides env default) ────────────────

SETTING_INTERVAL_KEY = "catalog_sync_interval_hours"


def get_automation_interval_hours() -> int:
    """Interval between catalog sync STARTs, in whole hours.

    Stored in the DB `settings` table so the admin UI can change it at
    runtime; falls back to CATALOG_SYNC_INTERVAL_HOURS (default 4) when the
    row is missing or unreadable.
    """
    conn, cur = _cur()
    try:
        cur.execute("SELECT value FROM settings WHERE key = %s", (SETTING_INTERVAL_KEY,))
        row = cur.fetchone()
        if row and row["value"] is not None:
            hours = int(str(row["value"]).strip())
            if hours >= 1:
                return hours
    except Exception:
        logger.warning("Could not read automation interval, using env default", exc_info=True)
    finally:
        conn.close()
    return max(1, int(settings.CATALOG_SYNC_INTERVAL_HOURS or 4))


def set_automation_interval_hours(hours: int) -> int:
    """Persist the interval; returns the stored (validated) value."""
    hours = int(hours)
    if hours < 1:
        raise ValueError("interval_hours must be a positive integer")
    conn, cur = _cur()
    try:
        cur.execute(
            "INSERT INTO settings (key, value, is_secret, created_at, updated_at)"
            " VALUES (%s, %s, FALSE, NOW(), NOW())"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
            (SETTING_INTERVAL_KEY, str(hours)),
        )
    finally:
        conn.close()
    return hours


def get_last_catalog_sync_start() -> Optional[datetime]:
    """START time (naive **UTC**) of the most recent catalog sync.

    SKIPPED runs are excluded — they never actually started syncing.
    The DB column is `timestamp without time zone` and the Postgres session
    timezone may be non-UTC (e.g. Europe/Kyiv on the host server), so the
    value is explicitly converted to UTC here: all Python scheduling math
    (catalog_sync_due / compute_next_run_at) works in UTC.
    Interval semantics: minimum gap between the START of one sync and the
    START of the next.
    """
    conn, cur = _cur()
    try:
        cur.execute(
            "SELECT (started_at AT TIME ZONE current_setting('TIMEZONE'))"
            " AT TIME ZONE 'UTC' AS started_utc"
            " FROM catalog_sync_runs"
            " WHERE status <> 'SKIPPED' AND started_at IS NOT NULL"
            " ORDER BY started_at DESC LIMIT 1",
        )
        row = cur.fetchone()
        return row["started_utc"] if row else None
    finally:
        conn.close()


def catalog_sync_due(now: Optional[datetime] = None,
                     interval_hours: Optional[int] = None,
                     last_started_at: Optional[datetime] = None) -> bool:
    """Is it time for the scheduler to start the next catalog sync?

    The hourly Beat task calls this on every tick; the interval lives in the
    DB, so admin changes take effect WITHOUT restarting celery-beat.
    A sync is due when `interval` hours have elapsed since the previous
    sync START (or when there has never been one).  Overlap protection is
    handled separately by the distributed lock.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    interval = int(interval_hours or get_automation_interval_hours())
    last = last_started_at if last_started_at is not None else get_last_catalog_sync_start()
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)  # DB column is timestamp WITHOUT tz (UTC)
    return now >= last + timedelta(hours=interval)


# ── catalog sync runs ───────────────────────────────────────────────────────

def create_catalog_run(trigger: str, triggered_by_user_id: Optional[int],
                       lock_token: str,
                       status: str = RUN_RUNNING,
                       error_details: Optional[dict] = None) -> int:
    conn, cur = _cur()
    try:
        cur.execute(
            "INSERT INTO catalog_sync_runs"
            " (status, trigger, triggered_by_user_id, started_at, heartbeat_at,"
            "  lock_token, error_details_json, created_at, updated_at)"
            " VALUES (%s, %s, %s, NOW(), NOW(), %s, %s, NOW(), NOW()) RETURNING id",
            (status, trigger, triggered_by_user_id, lock_token,
             json.dumps(error_details, ensure_ascii=False) if error_details else None),
        )
        return cur.fetchone()["id"]
    finally:
        conn.close()


def load_catalog_run(run_id: int) -> Optional[dict]:
    conn, cur = _cur()
    try:
        cur.execute("SELECT * FROM catalog_sync_runs WHERE id = %s", (run_id,))
        return cur.fetchone()
    finally:
        conn.close()


def get_running_catalog_run() -> Optional[dict]:
    """Latest RUNNING run (only one is possible thanks to the lock)."""
    conn, cur = _cur()
    try:
        cur.execute(
            "SELECT * FROM catalog_sync_runs WHERE status = 'RUNNING'"
            " ORDER BY id DESC LIMIT 1",
        )
        return cur.fetchone()
    finally:
        conn.close()


def list_catalog_runs(page: int = 1, per_page: int = 25,
                      status: Optional[str] = None) -> dict:
    conn, cur = _cur()
    try:
        where, params = ["1 = 1"], []
        if status:
            where.append("status = %s")
            params.append(status)
        condition = " AND ".join(where)
        cur.execute(
            f"SELECT COUNT(*) AS c FROM catalog_sync_runs WHERE {condition}", params,
        )
        total = cur.fetchone()["c"]
        cur.execute(
            f"SELECT * FROM catalog_sync_runs WHERE {condition}"
            " ORDER BY id DESC LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page],
        )
        rows = cur.fetchall()
        for r in rows:
            r["duration_seconds"] = _duration(r.get("started_at"), r.get("finished_at"))
        return {"items": rows, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


def append_run_log(run_id: int, level: str, message: str) -> None:
    """Insert a user-facing log line and refresh the run heartbeat."""
    if not run_id:
        return
    conn, cur = _cur()
    try:
        cur.execute(
            "INSERT INTO catalog_sync_logs (run_id, level, message, created_at)"
            " VALUES (%s, %s, %s, NOW())",
            (run_id, level, message),
        )
        cur.execute(
            "UPDATE catalog_sync_runs SET heartbeat_at = NOW(), updated_at = NOW()"
            " WHERE id = %s",
            (run_id,),
        )
    finally:
        conn.close()


def get_run_logs(run_id: int, limit: int = 300) -> list[dict]:
    conn, cur = _cur()
    try:
        cur.execute(
            "SELECT id, level, message, created_at FROM catalog_sync_logs"
            " WHERE run_id = %s ORDER BY id ASC LIMIT %s",
            (run_id, limit),
        )
        return cur.fetchall()
    finally:
        conn.close()


def update_catalog_run_progress(run_id: int, progress: dict) -> None:
    conn, cur = _cur()
    try:
        cur.execute(
            "UPDATE catalog_sync_runs SET progress_json = %s, updated_at = NOW()"
            " WHERE id = %s",
            (json.dumps(progress, ensure_ascii=False), run_id),
        )
    finally:
        conn.close()
def merge_catalog_run_progress(run_id: int, patch: dict) -> bool:
    """Merge `patch` into progress_json under a row lock (few concurrent
    writers — one per parallel export task)."""
    conn = psycopg2.connect(DB)
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=_REAL_DICT)
        cur.execute(
            "SELECT progress_json FROM catalog_sync_runs WHERE id = %s FOR UPDATE",
            (run_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return False
        progress = {}
        if row["progress_json"]:
            try:
                parsed = json.loads(row["progress_json"])
                if isinstance(parsed, dict):
                    progress = parsed
            except (ValueError, TypeError):
                progress = {}
        for key, value in patch.items():
            progress[key] = value
        cur.execute(
            "UPDATE catalog_sync_runs SET progress_json = %s, updated_at = NOW()"
            " WHERE id = %s",
            (json.dumps(progress, ensure_ascii=False), run_id),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def touch_catalog_run(run_id: int) -> None:
    if not run_id:
        return
    conn, cur = _cur()
    try:
        cur.execute(
            "UPDATE catalog_sync_runs SET heartbeat_at = NOW(), updated_at = NOW()"
            " WHERE id = %s",
            (run_id,),
        )
    finally:
        conn.close()


def finish_catalog_run(run_id: int, status: str,
                       error_details: Optional[dict] = None) -> None:
    conn, cur = _cur()
    try:
        cur.execute(
            "UPDATE catalog_sync_runs SET status = %s, finished_at = NOW(),"
            " heartbeat_at = NOW(), updated_at = NOW(), error_details_json = %s"
            " WHERE id = %s",
            (status,
             json.dumps(error_details, ensure_ascii=False) if error_details else None,
             run_id),
        )
    finally:
        conn.close()


def reconcile_catalog_sync_runs() -> int:
    """Mark RUNNING runs whose heartbeat is older than the lock timeout as
    FAILED (worker/container restart safety). Returns the affected count.

    Staleness is derived ONLY from `heartbeat_at` (driven by the supplier
    import / channel export tasks) compared to the configurable
    `CATALOG_SYNC_LOCK_TIMEOUT`.  A healthy sync never stops heartbeating,
    so a run that is simply long-running (e.g. DC-Link ~9k products, well
    over 5 minutes) is never marked stale merely for being old.

    A previous age-only rule (`created_at < NOW() - interval '5 minutes'`)
    was a false positive: it aborted in-flight imports whose supplier task
    was still working but had not yet emitted a second heartbeat.
    """
    timeout_sec = int(settings.CATALOG_SYNC_LOCK_TIMEOUT)
    reason = json.dumps(
        {"reason": "Catalog sync interrupted: worker heartbeat expired"},
        ensure_ascii=False,
    )
    conn, cur = _cur()
    try:
        cur.execute(
            "UPDATE catalog_sync_runs SET status = 'FAILED', finished_at = NOW(),"
            " error_details_json = %s, updated_at = NOW()"
            " WHERE status = 'RUNNING'"
            "   AND (heartbeat_at IS NULL"
            "        OR heartbeat_at < NOW() - make_interval(secs => %s))"
            " RETURNING id",
            (reason, timeout_sec),
        )
        affected = [r["id"] for r in cur.fetchall()]
        return len(affected)
    finally:
        conn.close()


def _duration(started, finished) -> Optional[int]:
    if not started:
        return None
    try:
        a = started if started.tzinfo else started.replace(tzinfo=timezone.utc)
        if finished:
            b = finished if finished.tzinfo else finished.replace(tzinfo=timezone.utc)
        else:
            b = datetime.now(timezone.utc)
        return max(0, int((b - a).total_seconds()))
    except (TypeError, ValueError):
        return None


def terminal_runs_with_lock_tokens(limit: int = 50) -> list[dict]:
    """Finished runs whose lock token was never explicitly released
    (e.g. worker died before the final callback)."""
    conn, cur = _cur()
    try:
        cur.execute(
            "SELECT id, lock_token FROM catalog_sync_runs"
            " WHERE status <> 'RUNNING' AND lock_token IS NOT NULL"
            " ORDER BY id DESC LIMIT %s",
            (limit,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def clear_lock_token(run_id: int) -> None:
    conn, cur = _cur()
    try:
        cur.execute(
            "UPDATE catalog_sync_runs SET lock_token = NULL, updated_at = NOW()"
            " WHERE id = %s",
            (run_id,),
        )
    finally:
        conn.close()
# ── suppliers / channels (from existing tables — never hardcoded) ───────────

def list_suppliers() -> list[dict]:
    conn, cur = _cur()
    try:
        codes = list(SYSTEM_SUPPLIERS.keys())
        cur.execute(
            "SELECT id, code, name, enabled FROM suppliers"
            " WHERE code = ANY(%s) ORDER BY name",
            (codes,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def resolve_enabled_suppliers() -> list[dict]:
    return [s for s in list_suppliers() if s["enabled"]]


def get_supplier_by_code(code: str) -> Optional[dict]:
    conn, cur = _cur()
    try:
        cur.execute("SELECT id, code, name, enabled FROM suppliers WHERE code = %s", (code,))
        return cur.fetchone()
    finally:
        conn.close()


def list_channels() -> list[dict]:
    """All channels with the adapter-support flag (only syncable channels may
    participate in the export phase)."""
    conn, cur = _cur()
    result = []
    try:
        cur.execute("SELECT id, code, name, is_enabled FROM channels ORDER BY code")
        for ch in cur.fetchall():
            result.append({**ch, "has_adapter": _channel_has_adapter(ch["code"])})
        return result
    finally:
        conn.close()


def _channel_has_adapter(code: str) -> bool:
    try:
        from app.channels.base import get_adapter
        get_adapter(code)
        return True
    except LookupError:
        return False
    except Exception:
        return False


def resolve_enabled_channels() -> list[dict]:
    return [ch for ch in list_channels() if ch["is_enabled"] and ch["has_adapter"]]


def get_channel_by_code(code: str) -> Optional[dict]:
    conn, cur = _cur()
    try:
        cur.execute("SELECT id, code, name, is_enabled FROM channels WHERE code = %s", (code,))
        return cur.fetchone()
    finally:
        conn.close()


def export_public_base_url() -> Optional[str]:
    """Image base URL baked into exported payloads. Empty → existing behaviour."""
    base = (settings.CATALOG_SYNC_PUBLIC_BASE_URL or "").strip()
    if base:
        return base.rstrip("/")
    if str(settings.FRONTEND_URL or "").startswith("http"):
        return settings.FRONTEND_URL.rstrip("/")
    return None


# ── import jobs bookkeeping ──────────────────────────────────────────────────

def create_import_job(supplier_id: int, import_type: str = "full",
                      triggered_by_user_id: Optional[int] = None) -> int:
    conn, cur = _cur()
    try:
        cur.execute(
            "INSERT INTO import_jobs (supplier_id, import_type, status,"
            " triggered_by_user_id, created_at, updated_at)"
            " VALUES (%s, %s, 'QUEUED', %s, NOW(), NOW()) RETURNING id",
            (supplier_id, import_type, triggered_by_user_id),
        )
        return cur.fetchone()["id"]
    finally:
        conn.close()


def reset_import_job_for_retry(job_id: int) -> None:
    """Re-arm a FAILED import job for one more attempt (transient failure)."""
    conn, cur = _cur()
    try:
        cur.execute(
            "UPDATE import_jobs SET status = 'QUEUED', started_at = NULL,"
            " finished_at = NULL, stats_json = NULL, error_details_json = NULL,"
            " progress_json = NULL, current_stage = NULL, cancel_requested = FALSE,"
            " updated_at = NOW() WHERE id = %s AND status = 'FAILED'",
            (job_id,),
        )
    finally:
        conn.close()


# ── deletion ─────────────────────────────────────────────────────────────────

def delete_catalog_run(run_id: int) -> tuple[bool, str]:
    """Delete one catalog_sync_runs record and its logs.

    Returns (success, message).  Does NOT delete RUNNING records.
    """
    conn, cur = _cur()
    try:
        cur.execute(
            "SELECT id, status FROM catalog_sync_runs WHERE id = %s", (run_id,)
        )
        row = cur.fetchone()
        if not row:
            return False, "Запуск не знайдено."
        if row["status"] == RUN_RUNNING:
            return False, "Активний запуск (RUNNING) не можна видалити."
        # Delete logs first (no FK cascade)
        cur.execute(
            "DELETE FROM catalog_sync_logs WHERE run_id = %s", (run_id,)
        )
        cur.execute("DELETE FROM catalog_sync_runs WHERE id = %s", (run_id,))
        return True, f"Запуск #{run_id} видалено."
    finally:
        conn.close()


def delete_catalog_runs(run_ids: list[int]) -> dict:
    """Delete multiple catalog_sync_runs records and their logs.

    RUNNING records are skipped.  Returns statistics.
    """
    if not run_ids:
        return {"deleted": 0, "skipped": 0, "errors": []}
    conn, cur = _cur()
    try:
        cur.execute(
            "SELECT id, status FROM catalog_sync_runs WHERE id = ANY(%s)",
            (run_ids,),
        )
        rows = {r["id"]: r["status"] for r in cur.fetchall()}
        to_delete, errors = [], []
        for rid in run_ids:
            if rid not in rows:
                errors.append({"id": rid, "reason": "Запуск не знайдено."})
            elif rows[rid] == RUN_RUNNING:
                errors.append(
                    {"id": rid, "reason": "Активний запуск (RUNNING) не можна видалити."}
                )
            else:
                to_delete.append(rid)
        if to_delete:
            cur.execute(
                "DELETE FROM catalog_sync_logs WHERE run_id = ANY(%s)",
                (to_delete,),
            )
            cur.execute(
                "DELETE FROM catalog_sync_runs WHERE id = ANY(%s)",
                (to_delete,),
            )
        return {
            "deleted": len(to_delete),
            "skipped": len(errors),
            "errors": errors,
        }
    finally:
        conn.close()


# ── export product selection (mirrors the existing export-all resolution) ───

def resolve_auto_export_product_ids(channel_id: int) -> list[int]:
    """All catalog products for the automated export phase.

    The existing export engine applies hash-skip per product, so unchanged
    products cost no API calls even though the whole catalog is selected.
    """
    conn = psycopg2.connect(DB)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT p.id FROM products p"
            " LEFT JOIN channel_listings cl ON cl.product_id = p.id"
            "   AND cl.channel_id = %s"
            " WHERE 1 = 1 ORDER BY p.id",
            (channel_id,),
        )
        return [r["id"] for r in cur.fetchall()]
    finally:
        conn.close()


# ── next-run computation (mirrors the scheduler gating decision) ────────────

def compute_next_run_at(now: Optional[datetime] = None,
                        interval_hours: Optional[int] = None,
                        last_started_at: Optional[datetime] = None) -> datetime:
    """When the scheduler will START the next catalog sync (aware UTC).

    Must stay consistent with `catalog_sync_due` + the hourly Beat tick:
    Beat fires at minute=0 of every hour, and a sync starts on the first
    tick where `interval` hours have elapsed since the previous START.
    The interval is read from the DB `settings` unless passed explicitly
    (tests / the admin API pass it to preview a not-yet-saved value).
    """
    interval = int(interval_hours or get_automation_interval_hours())
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    last = last_started_at if last_started_at is not None else get_last_catalog_sync_start()

    if last is None:
        ready_at = now                      # never ran → due on the next tick
    else:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        ready_at = max(now, last + timedelta(hours=interval))

    # Round UP to the next hourly tick (Beat only checks at minute=0).
    next_tick = ready_at.replace(minute=0, second=0, microsecond=0)
    if next_tick < ready_at:
        next_tick += timedelta(hours=1)
    return next_tick