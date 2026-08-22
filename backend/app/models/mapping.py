"""
Mapping models (category, attribute, value).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


class CategoryMapping(Base):
    """Category mapping: supplier category → internal category."""
    __tablename__ = "category_mappings"

    supplier_category_id = Column(Integer, ForeignKey("supplier_categories.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    supplier_category = relationship("SupplierCategory", back_populates="category_mappings")
    category = relationship("Category")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])


class AttributeMapping(Base):
    """Attribute mapping: supplier attribute → internal attribute."""
    __tablename__ = "attribute_mappings"

    supplier_attribute_id = Column(Integer, ForeignKey("supplier_attributes.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    supplier_attribute = relationship("SupplierAttribute", back_populates="attribute_mappings")
    attribute = relationship("Attribute")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])


class AttributeValueMapping(Base):
    """Attribute value mapping: supplier value → internal value."""
    __tablename__ = "attribute_value_mappings"

    supplier_attribute_value_id = Column(Integer, ForeignKey("supplier_attribute_values.id"), nullable=False)
    attribute_value_id = Column(Integer, ForeignKey("attribute_values.id"), nullable=True)  # NULL = drop
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    supplier_attribute_value = relationship("SupplierAttributeValue", back_populates="attribute_value_mappings")
    attribute_value = relationship("AttributeValue")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])


class MappingSource(Base):
    """Archived JSON mapping file with SHA256 checksum."""
    __tablename__ = "mapping_sources"

    file_name = Column(String(255), nullable=False, index=True)
    sha256 = Column(String(64), nullable=False, unique=True)
    content = Column(Text, nullable=False)  # Full JSON
    archived_at = Column(DateTime, default=datetime.utcnow, nullable=False)
