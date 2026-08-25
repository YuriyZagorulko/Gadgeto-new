"""Channel synchronization foundation models.

sync_runs / sync_jobs / sync_logs mirror the operational patterns already
proven by import_jobs / import_logs: heartbeat, cancel_requested, progress
counters.  The actual sync engine is intentionally NOT implemented here
(later phase); Phase 1 only establishes the data model.

Payload policy: `payload_json` is nullable and optional.  The future sync
engine MUST NOT store full request/response payloads per job by default.
"""

from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class SyncRunType(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    FULL = "full"
    DELTA = "delta"
    VALIDATION = "validation"
    TAXONOMY = "taxonomy"


class SyncRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class SyncJobOperation(str, Enum):
    PUBLISH = "publish"
    UPDATE = "update"
    PRICE_STOCK = "price_stock"
    UNPUBLISH = "unpublish"
    FULL = "full"


class SyncJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class SyncJobErrorType(str, Enum):
    """Error classification: retryable vs data errors is decided later by the
    sync engine's retry policy."""

    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_5XX = "server_5xx"
    AUTH = "auth"
    VALIDATION = "validation"
    MAPPING = "mapping"
    INVALID_DATA = "invalid_data"


class SyncLogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


class SyncRun(Base):
    """One logical synchronization operation over a channel."""

    __tablename__ = "sync_runs"

    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    run_type = Column(
        SAEnum(SyncRunType, name="syncruntype"),
        default=SyncRunType.MANUAL,
        nullable=False,
    )
    status = Column(
        SAEnum(SyncRunStatus, name="syncrunstatus"),
        default=SyncRunStatus.QUEUED,
        nullable=False,
    )

    total_count = Column(Integer, default=0)
    processed_count = Column(Integer, default=0)
    created_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)

    progress_json = Column(Text, nullable=True)
    current_stage = Column(String(255), nullable=True)

    heartbeat_at = Column(DateTime, nullable=True)
    cancel_requested = Column(Boolean, default=False, nullable=False)

    triggered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    channel = relationship("Channel")
    jobs = relationship("SyncJob", back_populates="run")

    __table_args__ = (
        Index("ix_sync_runs_channel_status", "channel_id", "status"),
        Index("ix_sync_runs_created_at", "created_at"),
    )


class SyncJob(Base):
    """Work unit for exactly one product/listing.  One failed job never blocks
    the rest of a run."""

    __tablename__ = "sync_jobs"

    run_id = Column(Integer, ForeignKey("sync_runs.id"), nullable=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("channel_listings.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    operation = Column(
        SAEnum(SyncJobOperation, name="syncjoboperation"), nullable=False
    )
    status = Column(
        SAEnum(SyncJobStatus, name="syncjobstatus"),
        default=SyncJobStatus.QUEUED,
        nullable=False,
    )

    attempt = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime, nullable=True)

    error_type = Column(SAEnum(SyncJobErrorType, name="syncjoberrortype"), nullable=True)
    error_message = Column(Text, nullable=True)

    # Optional, nullable — do NOT store large payloads by default.
    payload_json = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    run = relationship("SyncRun", back_populates="jobs")
    logs = relationship("SyncLog", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sync_jobs_status_next_retry", "status", "next_retry_at"),
        Index("ix_sync_jobs_run", "run_id"),
        Index("ix_sync_jobs_listing", "listing_id"),
        Index("ix_sync_jobs_product", "product_id"),
    )


class SyncLog(Base):
    """Lightweight per-job log line (same pattern as import_logs)."""

    __tablename__ = "sync_logs"

    job_id = Column(Integer, ForeignKey("sync_jobs.id"), nullable=False)
    level = Column(
        SAEnum(SyncLogLevel, name="syncloglevel"), default=SyncLogLevel.INFO
    )
    message = Column(Text, nullable=False)

    job = relationship("SyncJob", back_populates="logs")

    __table_args__ = (Index("ix_sync_logs_job", "job_id"),)