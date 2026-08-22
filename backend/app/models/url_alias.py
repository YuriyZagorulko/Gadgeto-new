from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from app.models.base import Base

class URLAlias(Base):
    __tablename__ = "url_aliases"
    old_url = Column(String(500), nullable=False, index=True)
    new_url = Column(String(500), nullable=False)
    http_status = Column(Integer, default=301, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
