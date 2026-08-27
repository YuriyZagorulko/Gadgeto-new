from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base

class Attribute(Base):
    __tablename__ = "attributes"
    slug = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), default="select")
    is_global = Column(Boolean, default=True, nullable=False)
    is_filterable = Column(Boolean, default=True, nullable=False)
    legacy_value_set = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    values = relationship("AttributeValue", back_populates="attribute")
    product_attributes = relationship("ProductAttribute", back_populates="attribute")
    category_filters = relationship("CategoryFilter", back_populates="attribute")
    category_attributes = relationship("CategoryAttribute", back_populates="attribute")

class AttributeValue(Base):
    __tablename__ = "attribute_values"
    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    value = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    sort = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    attribute = relationship("Attribute", back_populates="values")
    product_attributes = relationship("ProductAttribute", back_populates="attribute_value")
    category_attribute_values = relationship("CategoryAttributeValue", back_populates="attribute_value")
    __table_args__ = (UniqueConstraint('attribute_id', 'value'),)
