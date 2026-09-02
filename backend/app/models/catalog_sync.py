"""Top-level catalog sync run model.

Represents ONE full automated cycle:

    Scheduler/Manual → run_catalog_sync
      ├── supplier import jobs (separate import_jobs rows)
      └── channel exports     (separate sync_runs EXPORT rows)

Supplier/export details are NOT duplicated here — progress_json only keeps
references (job ids / sync run ids) plus the phase and the live status.
The per-supplier/per-channel lifecycle lives in the existing import_jobs and
sync_runs tables.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.models.base import Base


# Recognised run statuses (stored as plain strings, mirrored by the admin UI).
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_SUCCEEDED = "SUCCEEDED"
RUN_STATUS_PARTIAL = "PARTIAL"
RUN_STATUS_FAILED = "FAILED"
RUN_STATUS_SKIPPED = "SKIPPED"

RUN_TRIGGER_SCHEDULER = "scheduler"
RUN_TRIGGER_MANUAL = "manual"


class CatalogSyncRun(Base):
    __tablename__ = "catalog_sync_runs"

    id = Column(Integer, primary_key=True)
    status = Column(String(20), nullable=False, default=RUN_STATUS_RUNNING)
    trigger = Column(String(20), nullable=False, default=RUN_TRIGGER_SCHEDULER)
    triggered_by_user_id = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    # {"phase": "import"|"export"|"done",
    #  "suppliers": [{"code","name","job_id","status"}...],
    #  "exports":   [{"code","name","run_id","status"}...]}
    progress_json = Column(Text, nullable=True)
    error_details_json = Column(Text, nullable=True)
    lock_token = Column(String(64), nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CatalogSyncLog(Base):
    """User-facing log lines for one catalog sync run (mirrors import_logs)."""

    __tablename__ = "catalog_sync_logs"

    run_id = Column(Integer, nullable=False, index=True)
    level = Column(String(20), nullable=False, default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)