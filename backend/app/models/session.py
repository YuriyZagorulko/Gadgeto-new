from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.base import Base

class UserSession(Base):
    __tablename__ = "sessions"
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ip = Column(String(45))
    user_agent = Column(Text, nullable=True)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="sessions")
