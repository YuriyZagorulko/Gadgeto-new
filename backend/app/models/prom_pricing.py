"""Prom.ua pricing/commission models (infrastructure only).

Mirrors the Rozetka pricing model structure (see ``rozetka_pricing.py``) so
Prom.ua can eventually carry its OWN pricing rules — markup, category-specific
rules, commission, rounding — completely independently from Rozetka pricing.

NO Prom.ua commission rates or pricing rules are seeded or invented here;
these tables exist purely as prepared storage.  ``commission_percent`` is
kept for structural parity with the Rozetka importer; the Prom.ua formula
(the exact pricing semantics) will be defined when Prom.ua documentation is
available.
"""

from sqlalchemy import BigInteger, Boolean, Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


class PromPricingImport(Base):
    """One uploaded/imported Prom.ua pricing file version (future use)."""

    __tablename__ = "prom_pricing_imports"

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
    rules = relationship("PromCategoryPricingRule", back_populates="pricing_import",
                         cascade="all, delete-orphan")


class PromCategoryPricingRule(Base):
    """Prom.ua category pricing rule (future use; nothing seeded)."""

    __tablename__ = "prom_category_pricing_rules"

    import_id = Column(Integer, ForeignKey("prom_pricing_imports.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    external_category_id = Column(String(255), nullable=False, index=True)
    category_name = Column(String(500), nullable=False)
    brand = Column(String(255), nullable=True)  # NULL = all brands
    price_min = Column(BigInteger, nullable=True)  # NULL = no lower bound
    price_max = Column(BigInteger, nullable=True)  # NULL = no upper bound
    commission_percent = Column(Float, nullable=False)

    pricing_import = relationship("PromPricingImport", back_populates="rules")