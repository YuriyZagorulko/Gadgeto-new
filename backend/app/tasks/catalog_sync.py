"""Catalog sync orchestration (Celery).

run_catalog_sync
    │ acquire distributed lock (single full sync at a time)
    ├── chord: import_supplier per ENABLED supplier   (separate jobs)
    │        └── after_supplier_imports               (all completed)
    │              ├── any supplier FAILED → run FAILED, NO export (safe policy)
    │              └── all SUCCEEDED     → chord: export_channel per ENABLED
    │                                          channel (separate runs)
    │                                          └── after_channel_exports
    │                                                → SUCCEEDED / PARTIAL / FAILED
    └── release lock

Every stage is a distinct task with its own status — the workflow is NOT one
giant task.  Beat (`catalog_sync_scheduled`) and the admin manual button both
enter through run_catalog_sync.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from celery import chord

from app.core.config import settings
from app.services.email import send_catalog_sync_failure_email
from app.tasks import state
from app.tasks.celery_app import celery_app
from app.tasks.channel_export import export_channel
from app.tasks.lock import CatalogSyncLock
from app.tasks.supplier_import import import_supplier

logger = logging.getLogger("tasks.catalog_sync")


# Indirections used by tests to avoid a live broker.
def _enqueue_imports(import_sigs: list, run_id: int) -> None:
    chord(import_sigs)(after_supplier_imports.s(run_id))


def _enqueue_exports(export_sigs: list, run_id: int) -> None:
    chord(export_sigs)(after_channel_exports.s(run_id))


def reconcile_and_release_stale() -> None:
    """Mark dead RUNNING runs FAILED and release their (expired) lock tokens."""
    try:
        state.reconcile_catalog_sync_runs()
    except Exception:
        logger.warning("Could not reconcile stale catalog sync runs", exc_info=True)
    try:
        lock = CatalogSyncLock()
        for r in state.terminal_runs_with_lock_tokens(limit=50):
            token = r.get("lock_token")
            if token:
                lock.release(token)
                state.clear_lock_token(r["id"])
    except Exception:
        logger.warning("Could not release stale lock tokens", exc_info=True)


def _release_run_lock(run: Optional[dict]) -> None:
    if not run:
        return
    token = run.get("lock_token")
    if token:
        try:
            CatalogSyncLock().release(token)
            state.clear_lock_token(run["id"])
        except Exception:
            logger.warning("Could not release lock for run %s", run.get("id"),
                          exc_info=True)


def _notify_failure(run_id: int, status: str, trigger: str,
                    failures: list) -> None:
    """Best-effort admin email about a failed/partial catalog sync run.

    Email problems must never affect the run result — everything is caught.
    """
    try:
        run = state.load_catalog_run(run_id) or {}
        sent = send_catalog_sync_failure_email(
            run_id=run_id, status=status, trigger=trigger, failures=failures,
            started_at=run.get("started_at"), finished_at=run.get("finished_at"),
        )
        if sent:
            state.append_run_log(
                run_id, "INFO",
                f"Admin failure notification email sent ({status})",
            )
    except Exception:
        logger.warning("Could not send catalog sync failure email (run #%s)",
                       run_id, exc_info=True)


@celery_app.task(name="app.tasks.catalog_sync.run_catalog_sync")
def run_catalog_sync(trigger: str = "scheduler",
                     triggered_by_user_id: Optional[int] = None) -> dict:
    """Entry point used by BOTH the scheduler and the admin manual button."""
    return _start_catalog_sync(trigger, triggered_by_user_id)


@celery_app.task(name="app.tasks.catalog_sync.catalog_sync_scheduled")
def catalog_sync_scheduled() -> dict:
    """Beat entry (fires hourly) — only initiates the sync when it is due.

    Gating order:
      1. automation master switch (DB `settings.catalog_sync_enabled`);
      2. stale-run reconciliation (always, cheap);
      3. interval check (DB `settings.catalog_sync_interval_hours` vs the
         START of the previous sync) — admin interval changes apply without
         restarting Beat;
      4. the distributed-lock probe inside `_start_catalog_sync` fails
         CLOSED: if Redis is unavailable an automatic sync is never started
         (no lock → no safe overlap protection).
    """
    if not state.is_automation_enabled():
        return {"status": "skipped", "reason": "automation-disabled"}
    reconcile_and_release_stale()
    if not state.catalog_sync_due():
        return {"status": "skipped", "reason": "not-due"}
    return _start_catalog_sync("scheduler", None)


def _start_catalog_sync(trigger: str,
                        triggered_by_user_id: Optional[int]) -> dict:
    if trigger == "scheduler" and not state.is_automation_enabled():
        return {"status": "skipped", "reason": "automation-disabled"}

    reconcile_and_release_stale()
    token = uuid.uuid4().hex
    lock = CatalogSyncLock()
    timeout = int(settings.CATALOG_SYNC_LOCK_TIMEOUT or 6 * 3600)

    # Fail CLOSED when the lock backend is unreachable — without the
    # distributed lock we cannot guarantee a single concurrent sync, so
    # nothing is started and no misleading SKIPPED run is recorded.
    probe = lock.peek()
    if not probe.get("available"):
        logger.error(
            "Catalog sync lock backend unavailable — refusing to start (%s): %s",
            trigger, probe.get("error"),
        )
        return {"status": "skipped", "reason": "lock-backend-unavailable"}

    if not lock.acquire(token, timeout):
        run_id = state.create_catalog_run(
            trigger, triggered_by_user_id, lock_token=token,
            status=state.RUN_SKIPPED,
            error_details={"reason": "Previous catalog sync is still running"},
        )
        state.append_run_log(
            run_id, "WARNING", "Skipped: previous catalog sync is still running",
        )
        return {"status": "skipped", "run_id": run_id,
                "reason": "previous catalog sync is still running"}

    run_id = state.create_catalog_run(trigger, triggered_by_user_id, lock_token=token)
    state.append_run_log(run_id, "INFO", "Starting catalog sync")

    suppliers = state.resolve_enabled_suppliers()
    if not suppliers:
        state.append_run_log(run_id, "INFO", "No enabled suppliers — nothing to sync")
        state.finish_catalog_run(run_id, state.RUN_SUCCEEDED,
                                 {"note": "no enabled suppliers"})
        _release_run_lock(state.load_catalog_run(run_id))
        return {"status": "succeeded", "run_id": run_id, "suppliers": []}

    import_sigs = []
    supplier_refs = []
    for s in suppliers:
        job_id = state.create_import_job(s["id"], "full", triggered_by_user_id)
        supplier_refs.append({"code": s["code"], "name": s["name"],
                              "job_id": job_id, "status": "QUEUED"})
        import_sigs.append(import_supplier.s(
            supplier_code=s["code"], job_id=job_id,
            supplier_id=s["id"], run_id=run_id))

    state.update_catalog_run_progress(
        run_id, {"phase": "import", "suppliers": supplier_refs, "exports": []},
    )
    _enqueue_imports(import_sigs, run_id)
    return {"status": "started", "run_id": run_id,
            "suppliers": [s["code"] for s in suppliers]}
@celery_app.task(name="app.tasks.catalog_sync.after_supplier_imports")
def after_supplier_imports(results: list, run_id: int) -> dict:
    """Runs once all supplier import tasks finished (success or fail).

    Exports start ONLY when every enabled supplier import succeeded — an
    incomplete catalog must never be pushed to a marketplace (safe policy).
    """
    run = state.load_catalog_run(run_id)
    if not run or run["status"] != state.RUN_RUNNING:
        return {"status": run["status"] if run else "unknown", "run_id": run_id}

    state.append_run_log(run_id, "INFO", "All suppliers completed")
    failed = [r for r in results if r.get("status") == "FAILED"]

    if failed:
        error_details = {
            "failed_suppliers": [
                {"supplier": f.get("supplier"), "error": f.get("error")} for f in failed
            ],
            "policy": "export skipped because a supplier import failed",
        }
        state.finish_catalog_run(run_id, state.RUN_FAILED, error_details)
        state.append_run_log(
            run_id, "ERROR",
            "Catalog sync failed — marketplace export skipped"
            " (supplier import failed)",
        )
        _release_run_lock(state.load_catalog_run(run_id))
        _notify_failure(
            run_id, state.RUN_FAILED, run.get("trigger") or "manual",
            [{"source": "supplier", "name": f.get("supplier"),
              "status": "FAILED", "error": f.get("error")} for f in failed],
        )
        return {"status": "FAILED", "run_id": run_id,
                "failed_suppliers": [f.get("supplier") for f in failed]}

    channels = state.resolve_enabled_channels()
    if not channels:
        state.append_run_log(run_id, "INFO",
                             "Catalog sync completed (no enabled channels)")
        state.finish_catalog_run(run_id, state.RUN_SUCCEEDED,
                                 {"note": "no enabled channels"})
        _release_run_lock(state.load_catalog_run(run_id))
        return {"status": "SUCCEEDED", "run_id": run_id, "exports": []}

    state.append_run_log(run_id, "INFO", "Export phase started")
    export_sigs = [
        export_channel.s(channel_code=c["code"], run_id=run_id,
                         triggered_by_user_id=run.get("triggered_by_user_id"))
        for c in channels
    ]
    state.update_catalog_run_progress(run_id, {"phase": "export"})
    _enqueue_exports(export_sigs, run_id)
    return {"status": "EXPORT_PHASE", "run_id": run_id,
            "channels": [c["code"] for c in channels]}


@celery_app.task(name="app.tasks.catalog_sync.after_channel_exports")
def after_channel_exports(results: list, run_id: int) -> dict:
    """Runs once all channel export tasks finished. Finalizes the run and
    releases the distributed lock."""
    run = state.load_catalog_run(run_id)
    if not run or run["status"] != state.RUN_RUNNING:
        return {"status": run["status"] if run else "unknown", "run_id": run_id}

    state.append_run_log(run_id, "INFO", "All exports completed")

    export_info = [
        {"channel": r.get("channel"), "status": r.get("status"),
         "run_id": r.get("run_id"), "error": r.get("error")}
        for r in results
    ]
    state.merge_catalog_run_progress(
        run_id, {"exports": export_info, "phase": "done"},
    )

    failed = [r for r in results if r.get("status") == "FAILED"]
    partial = [r for r in results if r.get("status") == "PARTIAL"]
    if failed and len(failed) == len(results):
        final = state.RUN_FAILED
    elif failed or partial:
        final = state.RUN_PARTIAL
    else:
        final = state.RUN_SUCCEEDED

    state.finish_catalog_run(run_id, final)
    state.append_run_log(run_id, "INFO", f"Catalog sync completed ({final})")
    _release_run_lock(state.load_catalog_run(run_id))
    if final in (state.RUN_FAILED, state.RUN_PARTIAL):
        _notify_failure(
            run_id, final, run.get("trigger") or "manual",
            [{"source": "channel", "name": r.get("channel"),
              "status": r.get("status"), "error": r.get("error")}
             for r in results if r.get("status") in ("FAILED", "PARTIAL")],
        )
    return {"status": final, "run_id": run_id, "exports": export_info}