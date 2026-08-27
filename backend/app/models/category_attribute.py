"""
Category-oriented attribute models.

Attribute → CategoryAttribute → Category
Attribute → AttributeValue
CategoryAttribute → CategoryAttributeValue → AttributeValue

An Attribute is a reusable canonical definition.
A CategoryAttribute represents the usage/configuration of that Attribute
in a particular Category.
"""
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base


class CategoryAttribute(Base):
    """Configuration of an Attribute within a specific Category.

    This is the core of the category-oriented attribute architecture.
    It defines how an attribute behaves when used in a particular category:
    whether it's required, multiple, filterable, etc.
    """
    __tablename__ = "category_attributes"

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    required = Column(Boolean, default=False, nullable=False)
    multiple = Column(Boolean, default=False, nullable=False)
    filterable = Column(Boolean, default=True, nullable=False)
    searchable = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    filter_type = Column(String(50), nullable=True)  # Future: checkbox, multi_select, select, range, etc.

    category = relationship("Category", back_populates="category_attributes")
    attribute = relationship("Attribute", back_populates="category_attributes")
    category_attribute_values = relationship(
        "CategoryAttributeValue", back_populates="category_attribute",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("category_id", "attribute_id",
                         name="uq_category_attribute"),
    )


class CategoryAttributeValue(Base):
    """Bridge between CategoryAttribute and AttributeValue.

    Represents which canonical AttributeValues are available/allowed
    for an Attribute in a particular Category.
    """
    __tablename__ = "category_attribute_values"

    category_attribute_id = Column(
        Integer, ForeignKey("category_attributes.id"), nullable=False,
    )
    attribute_value_id = Column(
        Integer, ForeignKey("attribute_values.id"), nullable=False,
    )

    category_attribute = relationship(
        "CategoryAttribute", back_populates="category_attribute_values",
    )
    attribute_value = relationship("AttributeValue", back_populates="category_attribute_values")

    __table_args__ = (
        UniqueConstraint("category_attribute_id", "attribute_value_id",
                         name="uq_category_attribute_value"),
    )
