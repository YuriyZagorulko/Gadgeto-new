"""Supplier import Celery task.

Wraps the EXISTING tracked import pipeline (app.imports.importer_service.
run_full_import) so the full lifecycle (QUEUED → RUNNING → SUCCEEDED/FAILED,
heartbeat, stats, import_logs) is preserved.  Adds a bounded retry policy for
TRANSIENT failures only (network/timeout/5xx) with exponential backoff.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.imports.registry import SUPPLIERS
from app.tasks import state
from app.tasks.celery_app import celery_app

logger = logging.getLogger("tasks.supplier_import")

#: Substrings that mark a failure as transient (retryable).  Business/data
#: errors never match — they fail fast without pointless retries.
TRANSIENT_MARKERS = (
    "timeout", "timed out", "connection", "econnrefused", "econnreset",
    "unreachable", "network", "dns", "ssl", "read timed out",
    "connect timed out", "temporarily unavailable", "internal server error",
    "bad gateway", "service unavailable", "http 500", "http 502",
    "http 503", "http 504", "status 5", "5xx", "429", "too many requests",
    "rate limit",
)


def is_transient_error(text) -> bool:
    if not text:
        return False
    lowered = str(text).lower()
    return any(marker in lowered for marker in TRANSIENT_MARKERS)


@celery_app.task(bind=True, name="app.tasks.supplier_import.import_supplier")
def import_supplier(self, supplier_code: str, job_id: int, supplier_id: int,
                    run_id: int = 0, import_type: str = "full") -> dict:
    """Run one supplier import (a separate job per supplier)."""
    return _execute_supplier_import(
        self, supplier_code, job_id, supplier_id, run_id, import_type,
    )


def _execute_supplier_import(task, supplier_code, job_id, supplier_id,
                             run_id, import_type="full") -> dict:
    from app.imports.importer_service import run_full_import

    entry = SUPPLIERS.get(supplier_code)
    name = entry["name"] if entry else supplier_code
    state.append_run_log(run_id, "INFO", f"{name} import started")

    try:
        result = run_full_import(supplier_code, job_id, supplier_id, import_type,
                                 run_id=run_id or None)
    except Exception as exc:  # defensive — run_full_import normally swallows
        result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    if result.get("success"):
        stats = result.get("stats") or {}
        products = int(stats.get("processed") or 0)
        state.append_run_log(run_id, "INFO",
                             f"{name} import completed: {products:,} products")
        state.touch_catalog_run(run_id)
        return {"status": "SUCCEEDED", "supplier": supplier_code,
                "job_id": job_id, "stats": stats}

    error = str(result.get("error") or "Unknown import error")
    state.append_run_log(run_id, "ERROR", f"{name} import failed: {error}")

    max_retries = max(0, int(settings.CATALOG_SYNC_MAX_RETRIES or 0))
    if task.request.retries < max_retries and is_transient_error(error):
        logger.warning("Transient failure for %s (attempt %s/%s): %s",
                       supplier_code, task.request.retries + 1, max_retries, error)
        try:
            state.reset_import_job_for_retry(job_id)
        except Exception:  # pragma: no cover - best effort
            logger.warning("Could not re-arm import job %s for retry", job_id)
        backoff = int(settings.CATALOG_SYNC_RETRY_BACKOFF or 60)
        countdown = backoff * (2 ** task.request.retries)
        raise task.retry(exc=RuntimeError(error), countdown=countdown)

    return {"status": "FAILED", "supplier": supplier_code,
            "job_id": job_id, "error": error}