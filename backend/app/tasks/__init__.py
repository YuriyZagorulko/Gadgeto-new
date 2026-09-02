"""Celery tasks for catalog automation.

Importing this package registers the tasks on the `celery_app` in
`app.tasks.celery_app` (used by the worker and by the admin API for manual
`run_catalog_sync.delay(...)` calls).
"""
from app.tasks.celery_app import celery_app  # noqa: F401
from app.tasks import supplier_import  # noqa: F401
from app.tasks import channel_export  # noqa: F401
from app.tasks import catalog_sync  # noqa: F401

__all__ = ["celery_app", "supplier_import", "channel_export", "catalog_sync"]