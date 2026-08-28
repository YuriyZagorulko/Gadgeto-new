"""Rozetka pricing rule resolver.

Given a base price and a Rozetka external category ID, finds the best
matching commission rule and computes the export selling price.

Commission is Rozetka's share — the seller receives (1 - commission) of
the final price.  The formula is:
    export_price = cost / (1 - commission_decimal)

For example, if cost = 10000 and commission = 18%:
    export_price = 10000 / (1 - 0.18) = 12195.12
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

logger = logging.getLogger("rozetka_pricing.resolver")


class PricingRule:
    """A single commission rule matched to a product."""

    def __init__(self, external_category_id: str, commission_percent: float,
                 brand: Optional[str] = None, price_min: Optional[int] = None,
                 price_max: Optional[int] = None):
        self.external_category_id = external_category_id
        self.commission_percent = commission_percent
        self.brand = brand
        self.price_min = price_min
        self.price_max = price_max

    def calculate_price(self, base_price: int) -> int:
        """Compute the export price from base price (cost).

        Commission is Rozetka's share of the final selling price.
        If commission = 18%, the seller keeps 82% of the final price.
        So: final_price = cost / (1 - 0.18) = cost / 0.82
        """
        if not base_price or base_price <= 0:
            return 0
        rate = Decimal(str(self.commission_percent)) / Decimal("100")
        if rate >= 1:
            return 0
        divisor = Decimal("1") - rate
        if divisor <= 0:
            return 0
        price = Decimal(str(base_price)) / divisor
        # Round to nearest integer (prices are in kopiykas)
        return int(price.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def __repr__(self) -> str:
        return (f"<PricingRule cat={self.external_category_id} "
                f"commission={self.commission_percent}%>")


class RozetkaPricingResolver:
    """Resolves the best commission rule for a Rozetka category + product.

    Rules are loaded from the active pricing import.  Matching priority:
      1. Exact category + brand + price range match
      2. Exact category + brand match (any price)
      3. Exact category + price range match (any brand)
      4. Exact category (any brand, any price)
      5. No match -> returns None (caller decides fallback)
    """

    def __init__(self, cur, channel_id: int):
        self._rules: list[PricingRule] = []
        self._load(cur, channel_id)

    def _load(self, cur, channel_id: int) -> None:
        """Load rules from the active pricing import."""
        cur.execute("""
            SELECT r.external_category_id, r.category_name, r.brand,
                   r.price_min, r.price_max, r.commission_percent
            FROM rozetka_category_pricing_rules r
            JOIN rozetka_pricing_imports i ON i.id = r.import_id
            WHERE i.is_active = true
            ORDER BY r.external_category_id, r.price_min NULLS LAST,
                     r.price_max NULLS LAST, r.brand NULLS LAST
        """)
        for row in cur.fetchall():
            self._rules.append(PricingRule(
                external_category_id=row["external_category_id"],
                commission_percent=row["commission_percent"],
                brand=row["brand"],
                price_min=row["price_min"],
                price_max=row["price_max"],
            ))

    @property
    def has_rules(self) -> bool:
        return len(self._rules) > 0

    def resolve(self, external_category_id: str,
                base_price: int = 0,
                brand: Optional[str] = None) -> Optional[PricingRule]:
        """Find the best matching rule for the given category/price/brand.

        Priority: brand+price > brand > price > category-only.
        Returns None when no rule matches.
        """
        candidates: list[PricingRule] = []
        for r in self._rules:
            if r.external_category_id != external_category_id:
                continue
            # Check brand match
            brand_match = r.brand is None or (brand and r.brand.lower() == brand.lower())
            # Check price range match
            price_match = True
            if r.price_min is not None and base_price < r.price_min:
                price_match = False
            if r.price_max is not None and base_price > r.price_max:
                price_match = False

            if brand_match and price_match:
                candidates.append(r)

        if not candidates:
            return None

        # Sort by specificity: brand+price > brand > price > category-only
        def specificity(r: PricingRule) -> int:
            score = 0
            if r.brand is not None:
                score += 2
            if r.price_min is not None:
                score += 1
            return score

        candidates.sort(key=specificity, reverse=True)
        return candidates[0]

    def calculate_export_price(self, external_category_id: str,
                               base_price: int,
                               brand: Optional[str] = None) -> Optional[int]:
        """Calculate the export price for a product, or None if no rule."""
        rule = self.resolve(external_category_id, base_price, brand)
        if rule is None:
            return None
        return rule.calculate_price(base_price)