"""
Category models.
"""

from typing import Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class Category(Base):
    """Product category model."""
    __tablename__ = "categories"

    legacy_id = Column(Integer, nullable=True, index=True)  # WC term_id
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    seo_focus_keyphrase = Column(String(255), nullable=True)
    image = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("ProductCategory", back_populates="category")
    filters = relationship("CategoryFilter", back_populates="category")
    supplier_categories = relationship("SupplierCategory", back_populates="category")


class CategoryClosure(Base):
    """Category closure table for fast tree queries."""
    __tablename__ = "category_closure"

    ancestor_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)
    descendant_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)
    path_length = Column(Integer, nullable=False)

    # Relationships
    ancestor = relationship("Category", foreign_keys=[ancestor_id])
    descendant = relationship("Category", foreign_keys=[descendant_id])
