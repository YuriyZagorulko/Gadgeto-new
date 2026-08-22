"""
Supplier models.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


class Supplier(Base):
    """Supplier model."""
    __tablename__ = "suppliers"

    code = Column(String(50), unique=True, nullable=False)  # itlink, dclink, manual
    name = Column(String(255), nullable=False)
    config_json = Column(Text, nullable=True)  # JSON config
    enabled = Column(Boolean, default=True, nullable=False)

    # Relationships
    products = relationship("Product", back_populates="supplier")
    supplier_categories = relationship("SupplierCategory", back_populates="supplier")
    supplier_attributes = relationship("SupplierAttribute", back_populates="supplier")
    import_jobs = relationship("ImportJob", back_populates="supplier")


class SupplierCategory(Base):
    """Supplier category mapping (verbatim copy from feed)."""
    __tablename__ = "supplier_categories"

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    external_id = Column(String(255), nullable=True, index=True)
    supplier_name = Column(String(500), nullable=False, index=True)  # verbatim
    is_removed = Column(Boolean, default=False, nullable=False)

    # Relationships
    supplier = relationship("Supplier", back_populates="supplier_categories")
    category_mappings = relationship("CategoryMapping", back_populates="supplier_category")


class SupplierAttribute(Base):
    """Supplier attribute mapping (verbatim copy from feed)."""
    __tablename__ = "supplier_attributes"

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    supplier_name = Column(String(500), nullable=False, index=True)  # verbatim
    is_removed = Column(Boolean, default=False, nullable=False)

    # Relationships
    supplier = relationship("Supplier", back_populates="supplier_attributes")
    attribute_mappings = relationship("AttributeMapping", back_populates="supplier_attribute")
    supplier_attribute_values = relationship("SupplierAttributeValue", back_populates="supplier_attribute")


class SupplierAttributeValue(Base):
    """Supplier attribute value (verbatim copy from feed)."""
    __tablename__ = "supplier_attribute_values"

    supplier_attribute_id = Column(Integer, ForeignKey("supplier_attributes.id"), nullable=False)
    supplier_value = Column(String(500), nullable=False, index=True)  # verbatim
    is_removed = Column(Boolean, default=False, nullable=False)

    # Relationships
    supplier_attribute = relationship("SupplierAttribute", back_populates="supplier_attribute_values")
    attribute_value_mappings = relationship("AttributeValueMapping", back_populates="supplier_attribute_value")


class SupplierProduct(Base):
    """Supplier product (ledger for idempotent imports)."""
    __tablename__ = "supplier_products"

    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    supplier_sku = Column(String(255), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    raw_json = Column(Text, nullable=True)  # Full JSON snapshot
    last_price = Column(Integer, nullable=True)  # in kopecks
    last_stock = Column(Integer, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    is_removed_from_feed = Column(Boolean, default=False, nullable=False)

    __table_args__ = (__sa_utils__.UniqueConstraint('supplier_id', 'supplier_sku'),)

    # Relationships
    supplier = relationship("Supplier")
    product = relationship("Product")
