"""Tests for the Rozetka pricing/commission resolver.

Covers:
  1. PricingRule.calculate_price — exact percentage formula
  2. RozetkaPricingResolver — exact category, parent inheritance,
     multiple hierarchy levels, no-rule fallback, brand+price specificity
"""

from unittest.mock import MagicMock

import pytest

from app.services.rozetka_pricing import PricingRule, RozetkaPricingResolver


# ── Fake cursor for resolver tests ──────────────────────────────────────


class FakeCursor:
    """Mimics psycopg2 RealDictCursor for RozetkaPricingResolver._load()."""

    def __init__(self, rules_rows: list[dict], parent_rows: list[dict]):
        self._rules = rules_rows
        self._parents = parent_rows
        self._call_count = 0

    def execute(self, sql, params=()):
        self._call_count += 1

    def fetchall(self):
        if self._call_count == 1:
            return self._rules
        if self._call_count == 2:
            return self._parents
        return []

    def close(self):
        pass


# ── PricingRule.calculate_price tests ──────────────────────────────────


class TestPricingRuleCalculate:
    """Verify the commission formula: export_price = cost / (1 - rate)."""

    def test_zero_commission(self):
        """0% commission -> price unchanged."""
        rule = PricingRule("123", 0.0)
        result = rule.calculate_price(100000)
        assert result == 100000

    def test_ten_percent(self):
        """10% -> 100000 / 0.90 = 111111... -> 111111."""
        rule = PricingRule("123", 10.0)
        result = rule.calculate_price(100000)
        assert result == 111111

    def test_fifteen_percent(self):
        """15% -> 175408 / 0.85 = 206362... -> 206363."""
        rule = PricingRule("123", 15.0)
        result = rule.calculate_price(175408)
        assert result == 206362

    def test_twenty_percent(self):
        """20% -> 100000 / 0.80 = 125000."""
        rule = PricingRule("123", 20.0)
        result = rule.calculate_price(100000)
        assert result == 125000

    def test_five_percent(self):
        """5% -> 175408 / 0.95 = 184640."""
        rule = PricingRule("123", 5.0)
        result = rule.calculate_price(175408)
        assert result == 184640

    def test_zero_price(self):
        """Zero base price -> 0."""
        rule = PricingRule("123", 15.0)
        result = rule.calculate_price(0)
        assert result == 0

    def test_negative_price(self):
        """Negative base price -> 0."""
        rule = PricingRule("123", 15.0)
        result = rule.calculate_price(-100)
        assert result == 0

    def test_100_percent_commission(self):
        """100% -> divisor=0 -> returns 0."""
        rule = PricingRule("123", 100.0)
        result = rule.calculate_price(100000)
        assert result == 0

    def test_over_100_percent_commission(self):
        """>100% -> rate >= 1 -> returns 0."""
        rule = PricingRule("123", 150.0)
        result = rule.calculate_price(100000)
        assert result == 0

    def test_rounding_half_up(self):
        """ROUND_HALF_UP: 100001 / 0.90 = 111112.22... -> 111112."""
        rule = PricingRule("123", 10.0)
        result = rule.calculate_price(100001)
        assert result == 111112

# ── RozetkaPricingResolver tests ──────────────────────────────────────


class TestRozetkaPricingResolver:
    """Verify category matching with parent inheritance."""

    def _make_resolver(self, rules: list[dict], parents: list[dict]):
        """Build a resolver without DB by populating internals directly."""
        resolver = RozetkaPricingResolver.__new__(RozetkaPricingResolver)
        resolver._rules = []
        resolver._parents = {}
        for row in rules:
            resolver._rules.append(PricingRule(
                external_category_id=row["external_category_id"],
                commission_percent=row["commission_percent"],
                brand=row.get("brand"),
                price_min=row.get("price_min"),
                price_max=row.get("price_max"),
            ))
        for row in parents:
            resolver._parents[row["external_id"]] = row["parent_external_id"]
        return resolver

    def test_exact_category(self):
        """Exact category match returns the correct rule."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 15.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"}],
        )
        rule = resolver.resolve("100", 100000)
        assert rule is not None
        assert rule.commission_percent == 15.0

    def test_no_match_returns_none(self):
        """No matching category -> None."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 15.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"},
                     {"external_id": "200", "parent_external_id": "100"}],
        )
        rule = resolver.resolve("999", 100000)
        assert rule is None

    def test_parent_inheritance(self):
        """Child without rule inherits from parent."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 15.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"},
                     {"external_id": "200", "parent_external_id": "100"}],
        )
        rule = resolver.resolve("200", 100000)
        assert rule is not None
        assert rule.commission_percent == 15.0

    def test_child_overrides_parent(self):
        """Exact child rule wins over parent rule."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 15.0},
                   {"external_category_id": "200", "commission_percent": 20.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"},
                     {"external_id": "200", "parent_external_id": "100"}],
        )
        rule = resolver.resolve("200", 100000)
        assert rule is not None
        assert rule.commission_percent == 20.0

    def test_two_level_inheritance(self):
        """Grandparent rule used when parent and child have no rule."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 10.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"},
                     {"external_id": "200", "parent_external_id": "100"},
                     {"external_id": "300", "parent_external_id": "200"}],
        )
        rule = resolver.resolve("300", 100000)
        assert rule is not None
        assert rule.commission_percent == 10.0

    def test_three_level_inheritance(self):
        """Great-grandparent rule inherited through chain."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 5.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"},
                     {"external_id": "200", "parent_external_id": "100"},
                     {"external_id": "300", "parent_external_id": "200"},
                     {"external_id": "400", "parent_external_id": "300"}],
        )
        rule = resolver.resolve("400", 100000)
        assert rule is not None
        assert rule.commission_percent == 5.0

    def test_no_rule_in_full_hierarchy(self):
        """No rule anywhere in the hierarchy -> None."""
        resolver = self._make_resolver(
            rules=[],
            parents=[{"external_id": "100", "parent_external_id": "0"},
                     {"external_id": "200", "parent_external_id": "100"}],
        )
        rule = resolver.resolve("200", 100000)
        assert rule is None

    def test_brand_and_price_specificity(self):
        """Brand+price rule wins over generic rules."""
        resolver = self._make_resolver(
            rules=[
                {"external_category_id": "100", "commission_percent": 15.0},
                {"external_category_id": "100", "commission_percent": 10.0,
                 "brand": "Logitech"},
                {"external_category_id": "100", "commission_percent": 12.0,
                 "price_min": 50000, "price_max": 500000},
            ],
            parents=[{"external_id": "100", "parent_external_id": "0"}],
        )
        rule = resolver.resolve("100", 100000, "Logitech")
        assert rule is not None
        assert rule.commission_percent == 10.0


    def test_calculate_export_price_exact(self):
        """calculate_export_price returns commission-adjusted kopecks."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 15.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"}],
        )
        result = resolver.calculate_export_price("100", 175408)
        assert result == 206362

    def test_calculate_export_price_no_rule(self):
        """No rule -> None returned."""
        resolver = self._make_resolver(rules=[], parents=[])
        result = resolver.calculate_export_price("100", 175408)
        assert result is None

    def test_calculate_export_price_parent_inheritance(self):
        """Parent rule inherited when child has no rule."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 10.0}],
            parents=[{"external_id": "100", "parent_external_id": "0"},
                     {"external_id": "200", "parent_external_id": "100"}],
        )
        result = resolver.calculate_export_price("200", 100000)
        assert result == 111111

    def test_calculate_export_price_with_price_range(self):
        """Price range filtering: correct range selected."""
        resolver = self._make_resolver(
            rules=[
                {"external_category_id": "100", "commission_percent": 20.0,
                 "price_min": None, "price_max": None},
                {"external_category_id": "100", "commission_percent": 5.0,
                 "price_min": 100000, "price_max": 999999999},
            ],
            parents=[{"external_id": "100", "parent_external_id": "0"}],
        )
        result = resolver.calculate_export_price("100", 175408)
        assert result == 184640

    def test_has_rules_true_when_rules_loaded(self):
        """has_rules returns True when there are rules."""
        resolver = self._make_resolver(
            rules=[{"external_category_id": "100", "commission_percent": 15.0}],
            parents=[],
        )
        assert resolver.has_rules is True

    def test_has_rules_false_when_no_rules(self):
        """has_rules returns False when there are no rules."""
        resolver = self._make_resolver(rules=[], parents=[])
        assert resolver.has_rules is False