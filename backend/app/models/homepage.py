"""Homepage content models: slider slides and recommended products."""

from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from app.models.base import Base


class HomepageSlide(Base):
    __tablename__ = "homepage_slides"

    image = Column(String(500), nullable=False)
    title = Column(String(255), nullable=True)
    subtitle = Column(String(500), nullable=True)
    button_text = Column(String(255), nullable=True)
    url = Column(String(1000), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)


class HomepageRecommendedProduct(Base):
    __tablename__ = "homepage_recommended_products"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)