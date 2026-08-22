"""
Import job models.
"""

from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


class ImportJobStatus(str, Enum):
    """Import job status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"


class ImportJob(Base):
    """Import job model."""
    __tablename__ = "import_jobs"

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    import_type = Column(String(50), default="full")  # full, delta, manual
    status = Column(SAEnum(ImportJobStatus), default=ImportJobStatus.QUEUED, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    stats_json = Column(Text, nullable=True)  # JSON with created/updated/skipped/failed
    error_details_json = Column(Text, nullable=True)  # JSON with error details
    triggered_by_user_id = Column(Integer, nullable=True)
    raw_config_json = Column(Text, nullable=True)  # Config used for this import

    # Relationships
    supplier = relationship("Supplier", back_populates="import_jobs")
    triggered_by_user = relationship("User", foreign_keys=[triggered_by_user_id])
    logs = relationship("ImportLog", back_populates="job", cascade="all, delete-orphan")


class ImportLog(Base):
    """Import log entry."""
    __tablename__ = "import_logs"

    job_id = Column(Integer, ForeignKey("import_jobs.id"), nullable=False)
    level = Column(String(20), default="info")  # debug, info, warning, error, critical
    message = Column(Text, nullable=False)
    item_ref = Column(String(255), nullable=True)  # SKU or name
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    job = relationship("ImportJob", back_populates="logs")
