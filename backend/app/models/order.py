"""
Order models.
"""

from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(Base):
    """Order model."""
    __tablename__ = "orders"

    number = Column(String(50), unique=True, nullable=False)  # Display order number
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    buyer_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    total_amount = Column(Integer, nullable=False)  # in kopecks
    subtotal_amount = Column(Integer, nullable=False)  # in kopecks
    shipping_amount = Column(Integer, default=0, nullable=False)  # in kopecks
    payment_method = Column(String(50), nullable=True)
    payment_status = Column(String(50), default="pending")
    shipping_address_json = Column(Text, nullable=True)  # For NovaPoshta
    city_ref = Column(String(255), nullable=True)  # NovaPoshta city reference
    warehouse_ref = Column(String(255), nullable=True)  # NovaPoshta warehouse reference
    warehouse_number = Column(String(50), nullable=True)
    area_name = Column(String(255), nullable=True)  # NovaPoshta region
    delivery_address = Column(String(500), nullable=True)
    recipient_name = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    events = relationship("OrderEvent", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Order item model."""
    __tablename__ = "order_items"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name = Column(String(500), nullable=False)  # Snapshot
    product_sku = Column(String(255), nullable=True)
    qty = Column(Integer, default=1, nullable=False)
    price = Column(Integer, nullable=False)  # in kopecks
    total = Column(Integer, nullable=False)  # qty * price

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class OrderEvent(Base):
    """Order event log."""
    __tablename__ = "order_events"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    event = Column(String(100), nullable=False)  # created, paid, shipped, etc.
    actor = Column(String(50), nullable=True)  # user, system, admin
    payload_json = Column(Text, nullable=True)  # Additional data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="events")


class Payment(Base):
    """Payment record."""
    __tablename__ = "payments"

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    payment_id = Column(String(255), unique=True, nullable=False)
    liqpay_order_id = Column(String(255), nullable=True)
    status = Column(String(50), default="pending")
    amount = Column(Integer, nullable=False)  # in kopecks
    currency = Column(String(3), default="UAH")
    card_mask = Column(String(20), nullable=True)
    card_type = Column(String(50), nullable=True)
    raw_callback_json = Column(Text, nullable=True)  # Full LiqPay callback
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="payments")


class ShippingAddress(Base):
    """Shipping address model."""
    __tablename__ = "shipping_addresses"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    city = Column(String(255), nullable=True)
    city_ref = Column(String(255), nullable=True)
    warehouse = Column(String(255), nullable=True)
    warehouse_ref = Column(String(255), nullable=True)
    warehouse_number = Column(String(50), nullable=True)
    area_name = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="shipping_addresses")
