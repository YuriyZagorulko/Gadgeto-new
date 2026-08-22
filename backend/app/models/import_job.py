from datetime import datetime
from enum import Enum
from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.base import Base

class ImportJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"

class ImportJob(Base):
    __tablename__ = "import_jobs"
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    import_type = Column(String(50), default="full")
    status = Column(SAEnum(ImportJobStatus), default=ImportJobStatus.QUEUED, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    stats_json = Column(Text, nullable=True)
    error_details_json = Column(Text, nullable=True)
    triggered_by_user_id = Column(Integer, nullable=True)
    raw_config_json = Column(Text, nullable=True)
    supplier = relationship("Supplier", back_populates="import_jobs")
    logs = relationship("ImportLog", back_populates="job", cascade="all, delete-orphan")

class ImportLog(Base):
    __tablename__ = "import_logs"
    job_id = Column(Integer, ForeignKey("import_jobs.id"), nullable=False)
    level = Column(String(20), default="info")
    message = Column(Text, nullable=False)
    item_ref = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    job = relationship("ImportJob", back_populates="logs")
