"""
Category filter models.
"""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String

from app.models.base import Base


class CategoryFilter(Base):
    """Category-specific filter configuration."""
    __tablename__ = "category_filters"

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)  # NULL = global default
    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    position = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    __table_args__ = (__sa_utils__.UniqueConstraint('category_id', 'attribute_id'),)

    # Relationships
    category = relationship("Category", back_populates="filters")
    attribute = relationship("Attribute", back_populates="category_filters")
