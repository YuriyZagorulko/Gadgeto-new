from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base

class ProductRelated(Base):
    __tablename__ = "product_related"
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    related_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    product = relationship("Product", foreign_keys=[product_id])
    related_product = relationship("Product", foreign_keys=[related_product_id])
    __table_args__ = (UniqueConstraint('product_id', 'related_product_id'),)
