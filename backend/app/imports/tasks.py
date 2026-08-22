"""
Import tasks for Celery worker.
"""

import json
from datetime import datetime
from typing import Optional

from celery import Celery, signature

from app.core.celery_app import celery_app
from app.core.config import settings
from app.imports.itlink import ITLinkImporter
from app.imports.dclink import DCLinkImporter


@celery_app.task(bind=True, max_retries=3)
def run_import_task(self, supplier_code: str, import_type: str = "full") -> dict:
    """
    Run a supplier import task.

    Args:
        supplier_code: 'itlink' or 'dclink'
        import_type: 'full' or 'delta'

    Returns:
        Import statistics dict
    """
    try:
        if supplier_code == "itlink":
            importer = ITLinkImporter()
            stats = importer.run(import_type)
        elif supplier_code == "dclink":
            importer = DCLinkImporter()
            stats = importer.run(import_type)
        else:
            raise ValueError(f"Unknown supplier: {supplier_code}")

        return {
            "success": True,
            "supplier": supplier_code,
            "import_type": import_type,
            "stats": stats,
        }
    except Exception as exc:
        self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        return {"success": False, "error": str(exc)}


@celery_app.task
def notify_import_complete(import_id: int, stats: dict) -> None:
    """
    Notify about import completion.

    Args:
        import_id: Import job ID
        stats: Import statistics
    """
    # TODO: Send email notification, update import job status, etc.
    pass
