"""
Attribute models.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class Attribute(Base):
    """Attribute definition model."""
    __tablename__ = "attributes"

    slug = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), default="select")  # select, text, number
    is_global = Column(Boolean, default=True, nullable=False)
    is_filterable = Column(Boolean, default=True, nullable=False)
    legacy_value_set = Column(Text, nullable=True)  # JSON array of values
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    values = relationship("AttributeValue", back_populates="attribute")
    product_attributes = relationship("ProductAttribute", back_populates="attribute")
    category_filters = relationship("CategoryFilter", back_populates="attribute")


class AttributeValue(Base):
    """Attribute value model."""
    __tablename__ = "attribute_values"

    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    value = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    sort = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    attribute = relationship("Attribute", back_populates="values")
    product_attributes = relationship("ProductAttribute", back_populates="attribute_value")
