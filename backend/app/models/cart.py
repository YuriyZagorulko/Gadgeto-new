from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class Cart(Base):
    __tablename__ = "carts"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_token = Column(String(64), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

class CartItem(Base):
    __tablename__ = "cart_items"
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    qty = Column(Integer, default=1, nullable=False)
    price_at_addition = Column(Integer, nullable=False)
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")
    __table_args__ = (UniqueConstraint('cart_id', 'product_id'),)
