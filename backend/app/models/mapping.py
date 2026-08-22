from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.base import Base

class CategoryMapping(Base):
    __tablename__ = "category_mappings"
    supplier_category_id = Column(Integer, ForeignKey("supplier_categories.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    supplier_category = relationship("SupplierCategory", back_populates="category_mappings")
    category = relationship("Category")

class AttributeMapping(Base):
    __tablename__ = "attribute_mappings"
    supplier_attribute_id = Column(Integer, ForeignKey("supplier_attributes.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    supplier_attribute = relationship("SupplierAttribute", back_populates="attribute_mappings")
    attribute = relationship("Attribute")

class AttributeValueMapping(Base):
    __tablename__ = "attribute_value_mappings"
    supplier_attribute_value_id = Column(Integer, ForeignKey("supplier_attribute_values.id"), nullable=False)
    attribute_value_id = Column(Integer, ForeignKey("attribute_values.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    supplier_attribute_value = relationship("SupplierAttributeValue", back_populates="attribute_value_mappings")
    attribute_value = relationship("AttributeValue")

class MappingSource(Base):
    __tablename__ = "mapping_sources"
    file_name = Column(String(255), nullable=False, index=True)
    sha256 = Column(String(64), nullable=False, unique=True)
    content = Column(Text, nullable=False)
    archived_at = Column(DateTime, default=datetime.utcnow, nullable=False)
