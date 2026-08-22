"""
Cart models.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.models.base import Base


class Cart(Base):
    """Shopping cart model."""
    __tablename__ = "carts"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_token = Column(String(64), nullable=True, index=True)  # For guest carts
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    """Cart item model."""
    __tablename__ = "cart_items"

    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty = Column(Integer, default=1, nullable=False)
    price_at_addition = Column(Integer, nullable=False)  # in kopecks

    # Relationships
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")

    __table_args__ = (__sa_utils__.UniqueConstraint('cart_id', 'product_id'),)
