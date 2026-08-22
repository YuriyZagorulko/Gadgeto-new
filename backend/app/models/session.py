"""
User session model.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class UserSession(Base):
    """User session model."""
    __tablename__ = "sessions"

    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    ip = Column(String(45))  # IPv4 and IPv6
    user_agent = Column(Text, nullable=True)
    last_activity_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sessions")
