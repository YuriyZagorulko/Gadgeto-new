from sqlalchemy import Boolean, Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base

class CategoryFilter(Base):
    __tablename__ = "category_filters"
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    attribute_id = Column(Integer, ForeignKey("attributes.id"), nullable=False)
    position = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    category = relationship("Category", back_populates="filters")
    attribute = relationship("Attribute", back_populates="category_filters")
    __table_args__ = (UniqueConstraint('category_id', 'attribute_id'),)
