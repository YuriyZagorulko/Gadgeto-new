"""
Tests for Rozetka-specific export pricing logic.

Verifies that:
  1. When a Rozetka category pricing rule exists, only commission compensation
     is applied (no additional global business markup).
  2. When no rule exists, the fallback markup is applied.
  3. When no category is mapped, the fallback markup is applied.
"""

import pytest
from unittest.mock import MagicMock

from app.channels.export_settings import (
    calculate_rozetka_export_price,
    calculate_export_price,
)


class TestCalculateRozetkaExportPrice:
    """Tests for calculate_rozetka_export_price function."""

    def _make_resolver(self, rules=None):
        """Create a mock pricing resolver."""
        resolver = MagicMock()
        resolver.has_rules = rules is not None and len(rules) > 0
        resolver._rules = rules or []

        def calculate_price(ext_cat_id, base_kopecks, brand=None):
            for r in rules or []:
                if r.get('ext_cat_id') == ext_cat_id:
                    commission = r['commission_percent']
                    if commission >= 100:
                        return None
                    from decimal import ROUND_HALF_UP, Decimal
                    rate = Decimal(str(commission)) / Decimal('100')
                    divisor = Decimal('1') - rate
                    if divisor <= 0:
                        return None
                    price = Decimal(str(base_kopecks)) / divisor
                    return int(price.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            return None

        resolver.calculate_export_price = calculate_price
        return resolver

    def test_category_with_rule_uses_commission_only(self):
        """When a category rule exists, apply commission compensation only."""
        # Category with 20% commission
        resolver = self._make_resolver([
            {'ext_cat_id': '100', 'commission_percent': 20.0}
        ])
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        base_price = 100000  # 1000.00 UAH in kopecks
        result = calculate_rozetka_export_price(base_price, '100', resolver, settings)

        # Expected: 1000 / (1 - 0.20) = 1250.00 UAH (commission only, no 30% markup)
        assert abs(result - 1250.0) < 0.01, f"Expected 1250.00, got {result}"

    def test_category_without_rule_uses_fallback_markup(self):
        """When no category rule exists, use fallback markup."""
        resolver = self._make_resolver([])  # No rules
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        base_price = 100000  # 1000.00 UAH in kopecks
        result = calculate_rozetka_export_price(base_price, '999', resolver, settings)

        # Expected: 1000 * 1.30 = 1300.00 UAH (fallback 30% markup)
        assert abs(result - 1300.0) < 0.01, f"Expected 1300.00, got {result}"

    def test_no_category_uses_fallback_markup(self):
        """When no category is mapped, use fallback markup."""
        resolver = self._make_resolver([
            {'ext_cat_id': '100', 'commission_percent': 20.0}
        ])
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        base_price = 100000  # 1000.00 UAH in kopecks
        result = calculate_rozetka_export_price(base_price, None, resolver, settings)

        # Expected: 1000 * 1.30 = 1300.00 UAH (fallback, no category)
        assert abs(result - 1300.0) < 0.01, f"Expected 1300.00, got {result}"

    def test_resolver_without_rules_uses_fallback(self):
        """When resolver has no rules at all, use fallback markup."""
        resolver = self._make_resolver([])  # Empty rules
        resolver.has_rules = False
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        base_price = 100000
        result = calculate_rozetka_export_price(base_price, '100', resolver, settings)

        # Expected: fallback 30% markup
        assert abs(result - 1300.0) < 0.01, f"Expected 1300.00, got {result}"

    def test_fixed_fallback_markup(self):
        """Test fixed fallback markup when no rule exists."""
        resolver = self._make_resolver([])
        settings = {'price_markup_type': 'fixed', 'price_markup_value': 50.0, 'price_rounding': 0}

        base_price = 100000  # 1000.00 UAH
        result = calculate_rozetka_export_price(base_price, '999', resolver, settings)

        # Expected: 1000 + 50 = 1050.00 UAH
        assert abs(result - 1050.0) < 0.01, f"Expected 1050.00, got {result}"

    def test_fallback_with_rounding(self):
        """Test fallback markup with rounding."""
        resolver = self._make_resolver([])
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 10}

        base_price = 100000  # 1000.00 UAH
        result = calculate_rozetka_export_price(base_price, '999', resolver, settings)

        # Expected: 1000 * 1.30 = 1300, rounded to nearest 10 = 1300
        assert abs(result - 1300.0) < 0.01, f"Expected 1300.00, got {result}"

    def test_commission_rounding_half_up(self):
        """Test that commission compensation rounds half up."""
        resolver = self._make_resolver([
            {'ext_cat_id': '100', 'commission_percent': 10.0}
        ])
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        # 100001 kopecks = 1000.01 UAH
        # After 10% commission: 1000.01 / 0.9 = 1111.1222... -> 1111.12
        base_price = 100001
        result = calculate_rozetka_export_price(base_price, '100', resolver, settings)

        # Expected: 1000.01 / 0.9 = 1111.12 (rounded)
        assert abs(result - 1111.12) < 0.01, f"Expected 1111.12, got {result}"

    def test_brand_matching(self):
        """Test that brand parameter is passed to resolver."""
        resolver = self._make_resolver([
            {'ext_cat_id': '100', 'commission_percent': 15.0}
        ])
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        base_price = 100000
        result = calculate_rozetka_export_price(
            base_price, '100', resolver, settings, brand='TestBrand')

        # Expected: 1000 / (1 - 0.15) = 1176.47
        assert abs(result - 1176.47) < 0.01, f"Expected 1176.47, got {result}"

    def test_zero_base_price(self):
        """Test with zero base price."""
        resolver = self._make_resolver([
            {'ext_cat_id': '100', 'commission_percent': 20.0}
        ])
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        result = calculate_rozetka_export_price(0, '100', resolver, settings)
        assert result == 0.0, f"Expected 0.0, got {result}"

    def test_no_global_markup_when_rule_exists(self):
        """Critical test: verify NO global markup is added when rule exists.

        This is the core fix for the double-markup bug.
        """
        resolver = self._make_resolver([
            {'ext_cat_id': '100', 'commission_percent': 22.0}
        ])
        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}

        base_price = 30621  # 306.21 UAH (real product price)
        result = calculate_rozetka_export_price(base_price, '100', resolver, settings)

        # With rule: should be 306.21 / (1 - 0.22) = 392.58
        # NOT: 306.21 * 1.30 / (1 - 0.22) = 510.35 (old buggy behavior)
        expected_with_rule = 306.21 / (1 - 0.22)  # 392.58
        assert abs(result - expected_with_rule) < 0.01, (
            f"Expected {expected_with_rule:.2f} (commission only), got {result}. "
            f"This indicates double-markup bug is still present!"
        )

        # Verify it's NOT the old buggy calculation
        old_buggy_result = 306.21 * 1.30 / (1 - 0.22)  # 510.35
        assert abs(result - old_buggy_result) > 10, (
            f"Result {result} is too close to old buggy value {old_buggy_result:.2f}"
        )


class TestFallbackVsRule:
    """Tests to verify fallback is only used when no rule exists."""

    def test_fallback_different_from_rule(self):
        """Verify fallback and rule produce different results."""
        from decimal import ROUND_HALF_UP, Decimal

        # Mock resolver with rule for category 100
        resolver = MagicMock()
        resolver.has_rules = True
        resolver.calculate_export_price = lambda cat, price, brand: int(
            (Decimal(str(price)) / Decimal('0.8')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        ) if cat == '100' else None

        settings = {'price_markup_type': 'percentage', 'price_markup_value': 30.0, 'price_rounding': 0}
        base_price = 100000  # 1000 UAH

        # With rule (category 100): commission 20%
        result_with_rule = calculate_rozetka_export_price(base_price, '100', resolver, settings)
        # Expected: 1000 / 0.8 = 1250
        assert abs(result_with_rule - 1250.0) < 0.01

        # Without rule (category 999): fallback 30%
        result_fallback = calculate_rozetka_export_price(base_price, '999', resolver, settings)
        # Expected: 1000 * 1.30 = 1300
        assert abs(result_fallback - 1300.0) < 0.01

        # They should be different
        assert result_with_rule != result_fallback
