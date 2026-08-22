"""
User and authentication models.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"


class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BANNED = "banned"


class User(Base):
    """User account model."""
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    phone = Column(String(50))
    role = Column(SAEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    status = Column(SAEnum(UserStatus), default=UserStatus.PENDING, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0)

    # Relationships
    orders = relationship("Order", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        from app.core.security import get_password_hash
        self.password_hash = get_password_hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password."""
        from app.core.security import verify_password
        return verify_password(password, self.password_hash)
