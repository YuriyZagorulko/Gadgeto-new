"""
Product models.
"""

from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class ProductStatus(str, Enum):
    """Product status enumeration."""
    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"
    ARCHIVED = "archived"


class Product(Base):
    """Product model."""
    __tablename__ = "products"

    legacy_id = Column(Integer, nullable=True, index=True)  # WC post ID
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_sku = Column(String(255), nullable=True, index=True)
    sku = Column(String(255), nullable=True, index=True)
    name = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    short_description = Column(Text, nullable=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    price = Column(Integer, nullable=False, default=0)  # in kopecks
    old_price = Column(Integer, nullable=True)  # in kopecks
    currency = Column(String(3), default="UAH", nullable=False)
    stock_status = Column(String(50), default="in_stock")  # in_stock, out_of_stock, on_backorder
    stock_qty = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_visible = Column(Boolean, default=True, nullable=False)
    status = Column(SAEnum(ProductStatus), default=ProductStatus.DRAFT, nullable=False)
    meta_json = Column(Text, nullable=True)  # Raw JSON from import
    search_vector = Column(Text, nullable=True)  # PostgreSQL tsvector
    imported_at = Column(DateTime, nullable=True)

    # Relationships
    supplier = relationship("Supplier", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    images = relationship("ProductImage", back_populates="product", order_by="ProductImage.sort_order")
    categories = relationship("ProductCategory", back_populates="product")
    attributes = relationship("ProductAttribute", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")


class ProductImage(Base):
    """Product image model."""
    __tablename__ = "product_images"

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    url = Column(String(1000), nullable=False)
    path = Column(String(500), nullable=True)  # Local path if stored
    alt = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    checksum = Column(String(64), nullable=True)  # SHA256

    # Relationships
    product = relationship("Product", back_populates="images")
