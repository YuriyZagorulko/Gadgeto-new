"""Celery application for the Gadgeto catalog automation.

Worker executes the real import/export jobs; Beat only triggers the scheduled
catalog sync.  The broker/result backend is the single project Redis instance
(see docker-compose `redis` service and app.core.config).
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "gadgeto",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.supplier_import",
        "app.tasks.channel_export",
        "app.tasks.catalog_sync",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1,  # importers are long-running + hold DB conns
    result_expires=86400,
    task_ignore_result=False,
)


def build_beat_schedule() -> dict:
    """Build the periodic schedule.

    Beat fires `catalog_sync_scheduled` EVERY HOUR (minute=0).  The task
    itself decides at run time whether a sync is actually due: it reads the
    interval from the DB `settings` table (`catalog_sync_interval_hours`,
    default 4) and compares it with the START of the previous sync.  This
    keeps the interval runtime-editable from the admin UI — no celery-beat
    restart is required after a change.
    """
    return {
        "catalog-sync-periodic": {
            "task": "app.tasks.catalog_sync.catalog_sync_scheduled",
            "schedule": crontab(minute=0, hour="*"),  # hourly tick; gating in the task
        },
    }


celery_app.conf.beat_schedule = build_beat_schedule()