"""
Celery application configuration.
"""

from celery import Celery

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "gadgeto_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.imports.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
)
