"""Background Rozetka taxonomy refresh runner.

The refresh runs as a background job (worker thread, never in the
request/event-loop thread) and reports live progress plus a rolling log into
`sync_runs` (run_type = TAXONOMY).  The admin UI polls a separate status
endpoint while the job runs.

Chosen storage:
  * run metadata / counters   -> sync_runs (existing table, run_type=TAXONOMY)
  * progress + rolling logs   -> sync_runs.progress_json

No new tables are required.  `sync_logs` is intentionally NOT used because it
is strictly per-job (job_id NOT NULL -> sync_jobs, which models one product
operation) and would need a synthetic SyncJob row per taxonomy run.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

from app.channels.rozetka.taxonomy import RozetkaTaxonomyService
from app.core.db_connect import DB

# A taxonomy run can legitimately take minutes.  Rows that remain QUEUED/RUNNING
# longer than this without a heartbeat are declared orphaned (e.g. restart).
STALE_RUN_MINUTES = int(os.getenv("TAXONOMY_STALE_MINUTES", "45"))
# Aggregate progress DB writes: never hammer the DB on a per-category basis.
WRITE_EVERY = 0.7  # seconds
MAX_LOGS = 300


class TaxonomyRunBusy(Exception):
    """A taxonomy run is already active for this channel."""


def reconcile_stale_runs(cur) -> int:
    """Mark orphaned QUEUED/RUNNING taxonomy runs as PARTIAL.

    Returns the number of reconciled rows.  Idempotent and cheap (one UPDATE).
    """
    cur.execute(
        f"""UPDATE sync_runs
            SET status='PARTIAL', finished_at=NOW(), updated_at=NOW(),
                heartbeat_at=NOW()
            WHERE run_type='TAXONOMY'
              AND status IN ('QUEUED','RUNNING')
              AND (heartbeat_at IS NULL
                   OR heartbeat_at < NOW() - interval '{STALE_RUN_MINUTES} minutes')
            RETURNING id"""
    )
    return len(cur.fetchall())


def start_taxonomy_refresh(channel_id: int, user_id: Optional[int] = None) -> int:
    """Create a QUEUED taxonomy run for the channel (after reconciling stale ones).

    Returns the new run id.  Raises `TaxonomyRunBusy` if a taxonomy run is
    already QUEUED/RUNNING for this channel.
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            reconcile_stale_runs(cur)
        except Exception:
            pass

        cur.execute(
            "SELECT count(*) AS c FROM sync_runs WHERE channel_id=%s"
            " AND run_type='TAXONOMY' AND status IN ('QUEUED','RUNNING')",
            (channel_id,),
        )
        if cur.fetchone()["c"]:
            raise TaxonomyRunBusy(
                "Таксономія Rozetka вже оновлюється. Дочекайтесь завершення поточного оновлення."
            )

        cur.execute(
            """INSERT INTO sync_runs
               (channel_id, run_type, status, total_count, processed_count,
                progress_json, heartbeat_at, triggered_by_user_id,
                started_at, created_at, updated_at)
               VALUES (%s, 'TAXONOMY', 'QUEUED', 0, 0, %s, NOW(), %s,
                       NOW(), NOW(), NOW())
               RETURNING id""",
            (channel_id, json.dumps({"logs": [], "errors": 0}), user_id),
        )
        run_id = cur.fetchone()["id"]
        cur.close()
        return run_id
    finally:
        conn.close()


def run_taxonomy_refresh(channel_id: int, run_id: int) -> dict:
    """Execute the full Rozetka taxonomy refresh in the current thread.

    Called from a worker thread.  Persists live progress + a rolling log into
    `sync_runs` for run_id.  One failed category never aborts the whole job;
    per-category failures increase the `errors` counter and the run finishes
    as PARTIAL (unless there was a fatal failure -> FAILED).
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    progress = {
        "categories": {"processed": 0, "total": 0, "created": 0, "updated": 0},
        "attributes": {"categories_processed": 0, "categories_total": 0,
                       "created": 0, "updated": 0},
        "values": {"created": 0, "updated": 0, "total": 0},
        "errors": 0,
        "current_operation": "Initializing...",
        "logs": [],
    }

    def _log(level: str, message: str) -> None:
        progress["logs"].append({
            "t": round(time.time(), 2),
            "ts": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        })
        if len(progress["logs"]) > MAX_LOGS:
            del progress["logs"][: len(progress["logs"]) - MAX_LOGS]

    last_write = [0.0]

    def _flush(force: bool = False) -> None:
        now = time.time()
        if not force and (now - last_write[0]) < WRITE_EVERY:
            return
        last_write[0] = now
        try:
            cur.execute(
                """UPDATE sync_runs
                   SET progress_json=%s, current_stage=%s, heartbeat_at=NOW(),
                       total_count=%s, processed_count=%s, updated_at=NOW()
                   WHERE id=%s""",
                (json.dumps(progress, ensure_ascii=False),
                 progress["current_operation"],
                 int(progress["categories"]["total"]),
                 int(progress["categories"]["processed"]),
                 run_id),
            )
        except Exception:
            pass

    def _progress_cb(stage: str, processed: int, total: int, message: str) -> None:
        stage = stage or "run"
        if stage == "categories":
            progress["categories"]["total"] = total or progress["categories"]["total"]
            progress["categories"]["processed"] = processed
            progress["current_operation"] = message or "Категорії"
            _log("INFO", message)
        elif stage == "attributes":
            progress["attributes"]["categories_total"] = total
            progress["attributes"]["categories_processed"] = processed
            progress["current_operation"] = message or "Атрибути"
            _log("ERROR" if ("FAILED" in message.upper() or "ERROR" in message.upper())
                 else "INFO", message)
        elif stage == "auth":
            progress["current_operation"] = message or "Аутентифікація"
            _log("INFO", message or "Authentication successful")
        elif stage == "init":
            progress["current_operation"] = message or "Таксономія оновлюється"
            _log("INFO", message or "Taxonomy refresh started")
        else:
            _log("INFO", message)
        _flush(force=(stage in ("auth", "init")))
# Mark RUNNING (started_at is set when the row was created).
    cur.execute(
        """UPDATE sync_runs
           SET status='RUNNING', heartbeat_at=NOW(), updated_at=NOW()
           WHERE id=%s""",
        (run_id,),
    )
    _flush(force=True)

    try:
        service = RozetkaTaxonomyService()
        stats = service.refresh(channel_id, "rozetka", progress_cb=_progress_cb)

        progress["categories"]["created"] = stats.get("categories_created", 0)
        progress["categories"]["updated"] = stats.get("categories_updated", 0)
        progress["attributes"]["created"] = stats.get("attributes_created", 0)
        progress["attributes"]["updated"] = stats.get("attributes_updated", 0)
        progress["values"]["created"] = stats.get("values_created", 0)
        progress["values"]["updated"] = stats.get("values_updated", 0)
        progress["errors"] = stats.get("errors", 0)

        try:
            cur.execute(
                "SELECT count(*) AS c FROM channel_external_values WHERE channel_id=%s",
                (channel_id,),
            )
            row = cur.fetchone()
            progress["values"]["total"] = row["c"] if row else 0
        except Exception:
            pass

        if progress["errors"] == 0:
            final_status = "SUCCEEDED"
            progress["current_operation"] = "Completed"
        else:
            final_status = "PARTIAL"
            progress["current_operation"] = "Completed with warnings"
        _log("INFO" if final_status == "SUCCEEDED" else "WARNING",
             f"Taxonomy refresh completed "
             f"(categories={progress['categories']['total']}, "
             f"attributes={progress['attributes']['created'] + progress['attributes']['updated']}, "
             f"values={progress['values']['created'] + progress['values']['updated']}, "
             f"errors={progress['errors']})")

        cur.execute(
            """UPDATE sync_runs
               SET status=%s, finished_at=NOW(), heartbeat_at=NOW(), updated_at=NOW(),
                   created_count=%s, updated_count=%s, failed_count=%s,
                   total_count=%s, processed_count=%s,
                   progress_json=%s, current_stage=%s
               WHERE id=%s""",
            (final_status,
             progress["categories"]["created"], progress["categories"]["updated"],
             progress["errors"],
             progress["categories"]["total"], progress["categories"]["processed"],
             json.dumps(progress, ensure_ascii=False), progress["current_operation"],
             run_id),
        )
        return {"success": True, "run_id": run_id, "status": final_status}
    except Exception as exc:
        progress["errors"] = int(progress.get("errors") or 0) + 1
        progress["current_operation"] = "Failed"
        _log("ERROR", f"Taxonomy refresh failed: {exc}")
        _flush(force=True)
        try:
            cur.execute(
                "UPDATE sync_runs SET status='FAILED', finished_at=NOW(), updated_at=NOW(), "
                "failed_count=%s, progress_json=%s, current_stage='Failed' WHERE id=%s",
                (progress["errors"], json.dumps(progress, ensure_ascii=False), run_id),
            )
        except Exception:
            pass
        return {"success": False, "status": "FAILED", "error": str(exc)}
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def get_taxonomy_run_status(cur, channel_id: int):
    """Return a UI-friendly summary of the latest taxonomy run (or None).

    Reconciles stale runs first so an orphaned RUNNING row cannot block the
    status screen or a subsequent refresh forever.
    """
    try:
        reconcile_stale_runs(cur)
    except Exception:
        pass
    cur.execute(
        "SELECT * FROM sync_runs WHERE channel_id=%s AND run_type='TAXONOMY'"
        " ORDER BY id DESC LIMIT 1",
        (channel_id,),
    )
    run = cur.fetchone()
    if not run:
        return None

    progress = {}
    if run.get("progress_json"):
        try:
            progress = json.loads(run["progress_json"]) or {}
        except (ValueError, TypeError):
            progress = {}
    if not isinstance(progress, dict):
        progress = {}
    logs = progress.get("logs") or []
    started_at = run.get("started_at")
    finished_at = run.get("finished_at")
    duration = None
    if started_at:
        delta = (finished_at or datetime.now()) - started_at
        duration = max(0, round(delta.total_seconds()))

    cat = progress.get("categories") or {}
    attrs = progress.get("attributes") or {}
    vals = progress.get("values") or {}
    return {
        "run_id": run["id"],
        "status": run.get("status"),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "categories": {
            "processed": int(cat.get("processed") or 0),
            "total": int(cat.get("total") or 0),
            "created": int(cat.get("created") or 0),
            "updated": int(cat.get("updated") or 0),
        },
        "attributes": {
            "categories_processed": int(attrs.get("categories_processed") or 0),
            "categories_total": int(attrs.get("categories_total") or 0),
            "total": int(attrs.get("created") or 0) + int(attrs.get("updated") or 0),
            "created": int(attrs.get("created") or 0),
            "updated": int(attrs.get("updated") or 0),
        },
        "values": {
            "total": int(vals.get("total") or 0),
            "created": int(vals.get("created") or 0),
            "updated": int(vals.get("updated") or 0),
        },
        "errors": int(progress.get("errors") or 0),
        "current_operation": progress.get("current_operation") or run.get("current_stage"),
        "logs": logs,
    }