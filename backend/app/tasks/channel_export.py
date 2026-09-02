"""Channel export Celery task.

Wraps the EXISTING export engine (app.channels.export_run.start_export_run +
run_export) for ONE marketplace/channel.  Only enabled channels are scheduled
by the orchestrator; a disabled channel is simply never enqueued.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.tasks import state
from app.tasks.celery_app import celery_app
from app.tasks.supplier_import import is_transient_error

logger = logging.getLogger("tasks.channel_export")

EXPORT_RUN_TYPE = "EXPORT"


@celery_app.task(bind=True, name="app.tasks.channel_export.export_channel")
def export_channel(self, channel_code: str, run_id: int = 0,
                   triggered_by_user_id: int = 0) -> dict:
    """Export the catalog to one channel (a separate run per channel)."""
    return _execute_channel_export(channel_code, run_id, triggered_by_user_id)


def _execute_channel_export(channel_code: str, run_id: int,
                            triggered_by_user_id: int = 0) -> dict:
    from app.channels.export_run import (
        ExportRunBusy,
        ExportSelectionEmpty,
        run_export,
        start_export_run,
    )

    channel = state.get_channel_by_code(channel_code)
    base_result = {"channel": channel_code, "status": "FAILED"}
    if not channel:
        state.append_run_log(run_id, "ERROR", f"Канал '{channel_code}' не знайдено")
        return base_result

    name = channel["name"]
    state.append_run_log(run_id, "INFO", f"{name} export started")

    try:
        product_ids = state.resolve_auto_export_product_ids(channel["id"])
    except Exception as exc:
        state.append_run_log(run_id, "ERROR",
                             f"{name} export failed: cannot resolve products: {exc}")
        return base_result

    if not product_ids:
        state.append_run_log(run_id, "INFO", f"{name} export skipped: no products")
        state.touch_catalog_run(run_id)
        return {"channel": channel_code, "status": "SUCCEEDED", "products": 0}

    public_base_url = state.export_public_base_url()
    try:
        export_run_id = start_export_run(
            channel["id"], product_ids, public_base_url,
            user_id=triggered_by_user_id or None,
        )
    except ExportRunBusy as exc:
        state.append_run_log(run_id, "ERROR", f"{name} export skipped: {exc}")
        return {**base_result, "run_id": 0, "error": str(exc)}
    except ExportSelectionEmpty as exc:
        state.append_run_log(run_id, "INFO", f"{name} export skipped: {exc}")
        return {"channel": channel_code, "status": "SUCCEEDED", "products": 0}
    except Exception as exc:
        state.append_run_log(run_id, "ERROR",
                             f"{name} export failed to start: {type(exc).__name__}: {exc}")
        return {**base_result, "error": str(exc)}

    try:
        outcome = run_export(channel["id"], channel_code, export_run_id,
                             product_ids, public_base_url)
    except Exception as exc:
        state.append_run_log(run_id, "ERROR",
                             f"{name} export failed: {type(exc).__name__}: {exc}")
        return {**base_result, "run_id": export_run_id, "error": str(exc)}

    status = str(outcome.get("status") or "FAILED")
    state.append_run_log(run_id, "INFO", f"{name} export completed ({status})")
    state.touch_catalog_run(run_id)
    return {"channel": channel_code, "status": status,
            "run_id": export_run_id, "error": outcome.get("error")}