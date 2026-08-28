"""Rozetka pricing/commission models.

Commission is Rozetka's share of the selling price.
The selling price is calculated as: price = cost / (1 - commission_decimal).

For example, if cost = 10000 and commission = 18%:
  price = 10000 / (1 - 0.18) = 12195.12
"""

from sqlalchemy import BigInteger, Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class RozetkaPricingImport(Base):
    """One uploaded/imported Rozetka pricing file version."""

    __tablename__ = "rozetka_pricing_imports"

    original_filename = Column(String(500), nullable=False)
    status = Column(String(50), server_default="PROCESSING", nullable=False)
    total_rows = Column(Integer, server_default="0", nullable=False)
    categories_found = Column(Integer, server_default="0", nullable=False)
    rules_imported = Column(Integer, server_default="0", nullable=False)
    invalid_rows = Column(Integer, server_default="0", nullable=False)
    duplicate_rows = Column(Integer, server_default="0", nullable=False)
    is_active = Column(Boolean, server_default="false", nullable=False)
    errors_json = Column(Text, nullable=True)
    imported_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    imported_by = relationship("User")
    rules = relationship("RozetkaCategoryPricingRule", back_populates="pricing_import",
                         cascade="all, delete-orphan")


class RozetkaCategoryPricingRule(Base):
    """Commission rule for a Rozetka category (with optional brand/price tier)."""

    __tablename__ = "rozetka_category_pricing_rules"

    import_id = Column(Integer, ForeignKey("rozetka_pricing_imports.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    external_category_id = Column(String(255), nullable=False, index=True)
    category_name = Column(String(500), nullable=False)
    brand = Column(String(255), nullable=True)  # NULL = all brands
    price_min = Column(BigInteger, nullable=True)  # NULL = no lower bound
    price_max = Column(BigInteger, nullable=True)  # NULL = no upper bound
    commission_percent = Column(Float, nullable=False)

    pricing_import = relationship("RozetkaPricingImport", back_populates="rules")