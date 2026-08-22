"""
Product relation models.
"""

from sqlalchemy import Column, ForeignKey, Integer

from app.models.base import Base


class ProductRelated(Base):
    """Related products model."""
    __tablename__ = "product_related"

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    related_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    # Relationships
    product = relationship("Product", foreign_keys=[product_id])
    related_product = relationship("Product", foreign_keys=[related_product_id])

    __table_args__ = (__sa_utils__.UniqueConstraint('product_id', 'related_product_id'),)
