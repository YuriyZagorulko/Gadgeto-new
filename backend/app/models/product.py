from enum import Enum
from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base

class ProductStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"
    ARCHIVED = "archived"

class Product(Base):
    __tablename__ = "products"
    legacy_id = Column(Integer, nullable=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_sku = Column(String(255), nullable=True, index=True)
    sku = Column(String(255), nullable=True, index=True)
    name = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    short_description = Column(Text, nullable=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    price = Column(Integer, nullable=False, default=0)
    old_price = Column(Integer, nullable=True)
    currency = Column(String(3), default="UAH", nullable=False)
    stock_status = Column(String(50), default="in_stock")
    stock_qty = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_visible = Column(Boolean, default=True, nullable=False)
    status = Column(SAEnum(ProductStatus), default=ProductStatus.DRAFT, nullable=False)
    meta_json = Column(Text, nullable=True)
    search_vector = Column(Text, nullable=True)
    imported_at = Column(DateTime, nullable=True)

    supplier = relationship("Supplier", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    images = relationship("ProductImage", back_populates="product")
    categories = relationship("ProductCategory", back_populates="product")
    attributes = relationship("ProductAttribute", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")

    __table_args__ = (UniqueConstraint('supplier_id', 'supplier_sku', name='uq_product_supplier'),)

class ProductImage(Base):
    __tablename__ = "product_images"
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    url = Column(String(1000), nullable=False)
    path = Column(String(500), nullable=True)
    alt = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    checksum = Column(String(64), nullable=True)
    product = relationship("Product", back_populates="images")

class ProductCategory(Base):
    __tablename__ = "product_categories"
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    product = relationship("Product", back_populates="categories")
    category = relationship("Category", back_populates="products")
    __table_args__ = (UniqueConstraint('product_id', 'category_id', name='uq_product_category'),)

class ProductAttribute(Base):
    __tablename__ = "product_attributes"
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    attribute_value_id = Column(Integer, ForeignKey("attribute_values.id"), nullable=True)
    value_text = Column(String(255), nullable=True)
    product = relationship("Product", back_populates="attributes")
    attribute = relationship("Attribute", back_populates="product_attributes")
    attribute_value = relationship("AttributeValue", back_populates="product_attributes")
    __table_args__ = (UniqueConstraint('product_id', 'attribute_id', name='uq_product_attribute'),)


class ProductReview(Base):
    """Customer review managed from the admin panel (migration 007)."""
    __tablename__ = "product_reviews"
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    author_name = Column(String(255), nullable=False)
    author_email = Column(String(255), nullable=True)
    rating = Column(Integer, nullable=False, default=5)
    content = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default='published')
    product = relationship("Product", backref="reviews")


class ProductVariation(Base):
    """Variable-product combination (migration 007). attrs_json maps attribute_id -> value text."""
    __tablename__ = "product_variations"
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku = Column(String(255), nullable=True)
    attrs_json = Column(Text, nullable=False, default='{}')
    price = Column(Integer, nullable=True)
    sale_price = Column(Integer, nullable=True)
    stock_qty = Column(Integer, nullable=False, default=0)
    stock_status = Column(String(50), nullable=False, default='in_stock')
    image_url = Column(String(1000), nullable=True)
    barcode = Column(String(64), nullable=True)
    supplier_sku = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    product = relationship("Product", backref="variations")

