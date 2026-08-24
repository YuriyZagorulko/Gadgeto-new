"""
Pricing configuration models.

MarkupRule: tiered markup rules that can be global, per-supplier, or per-category.
"""

from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class MarkupRule(Base):
    """Tiered markup rule for a specific supplier and/or category.

    Evaluation order (within one scope: supplier+category):
      1. Rules are sorted by price_threshold (lowest first).
      2. The first rule where base_price_uah <= price_threshold wins.
      3. If no rule matches, the highest-threshold rule's multiplier applies.

    Scope priority (highest first) for finding applicable rules:
      1. Exact (supplier_code, category_id)
      2. (supplier_code, NULL)  — supplier-wide default
      3. ('*', category_id)     — cross-supplier category default
      4. ('*', NULL)           — global fallback

    price_threshold is in UAH (whole hryvnias).
    multiplier is the factor applied to the base UAH price.
      e.g. 1.50 = +50%, 1.30 = +30%.
    """
    __tablename__ = "markup_rules"

    supplier_code = Column(String(50), nullable=False, default="*")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    price_threshold = Column(Integer, nullable=False)     # UAH
    multiplier = Column(Float, nullable=False)             # e.g. 1.50
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    category = relationship("Category")