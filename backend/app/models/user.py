from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship
from app.models.base import Base

class UserRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BANNED = "banned"

class User(Base):
    __tablename__ = "users"
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    phone = Column(String(50))
    role = Column(SAEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    status = Column(SAEnum(UserStatus), default=UserStatus.PENDING, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    verification_token_hash = Column(String(64), nullable=True, index=True)
    verification_token_expires_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0)

    orders = relationship("Order", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    carts = relationship("Cart", back_populates="user")
    shipping_addresses = relationship("ShippingAddress", back_populates="user")

    def set_password(self, password: str) -> None:
        from app.core.security import get_password_hash
        self.password_hash = get_password_hash(password)

    def verify_password(self, password: str) -> bool:
        from app.core.security import verify_password
        return verify_password(password, self.password_hash)
