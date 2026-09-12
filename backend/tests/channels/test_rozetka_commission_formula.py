"""Focused audit: category percentage must compensate commission.

Required: final = P / (1 - r/100).  NOT P * (1 + r/100).
Invariant: final * (1 - r/100) ~= base (within rounding tolerance).
"""

from app.channels.export_settings import (
    apply_rozetka_export_settings,
    calculate_rozetka_export_price,
)
from app.services.rozetka_pricing import PricingRule

BASE_KOP = 100_000  # 1000.00 UAH


def _rule_resolver(commission_percent):
    class _R:
        has_rules = True

        def calculate_export_price(self, ext_cat_id, base_kopecks, brand=None):
            rule = PricingRule(str(ext_cat_id), float(commission_percent))
            return rule.calculate_price(int(base_kopecks))

    return _R()


def _no_rule_resolver():
    class _R:
        has_rules = False

        def calculate_export_price(self, ext_cat_id, base_kopecks, brand=None):
            return None

    return _R()


def _settings():
    return {"price_markup_type": "percentage", "price_markup_value": 30.0,
            "price_rounding": 0}


def _invariant_ok(base_uah, final_uah, pct, tol=1.0):
    return abs(final_uah * (1.0 - pct / 100.0) - base_uah) <= tol


def test_zero_percent_unchanged():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(0.0), _settings())
    assert abs(res - 1000.0) < 0.01
    assert _invariant_ok(1000.0, res, 0.0)


def test_ten_percent():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(10.0), _settings())
    assert abs(res - 1111.11) < 0.01
    assert _invariant_ok(1000.0, res, 10.0)
    assert abs(res - 1100.0) > 5.0  # wrong formula would give 1100


def test_twenty_percent():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(20.0), _settings())
    assert abs(res - 1250.0) < 0.01
    assert _invariant_ok(1000.0, res, 20.0)


def test_twenty_two_percent():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(22.0), _settings())
    assert abs(res - 1282.05) < 0.01
    assert _invariant_ok(1000.0, res, 22.0)


def test_thirty_percent():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(30.0), _settings())
    assert abs(res - 1428.57) < 0.01
    assert _invariant_ok(1000.0, res, 30.0)


def test_fifty_percent():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(50.0), _settings())
    assert abs(res - 2000.0) < 0.01
    assert _invariant_ok(1000.0, res, 50.0)
def test_hundred_percent_safe():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(100.0), _settings())
    assert res == 0.0  # no ZeroDivisionError


def test_over_hundred_percent_safe():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(150.0), _settings())
    assert res == 0.0


def test_missing_rule_uses_fallback():
    res = calculate_rozetka_export_price(BASE_KOP, "999", _no_rule_resolver(), _settings())
    assert abs(res - 1300.0) < 0.01  # 1000 * 1.30 fallback


def test_no_category_uses_fallback():
    res = calculate_rozetka_export_price(BASE_KOP, None, _rule_resolver(20.0), _settings())
    assert abs(res - 1300.0) < 0.01


def test_no_double_application():
    res = calculate_rozetka_export_price(BASE_KOP, "100", _rule_resolver(20.0), _settings())
    assert abs(res - 1625.0) > 10.0  # buggy: 1000*1.30/0.80
    assert abs(res - 1250.0) < 0.01


def test_apply_once_via_applicator():
    t = {"price": BASE_KOP, "external_category_id": "100"}
    out = apply_rozetka_export_settings(dict(t), _settings(), _rule_resolver(20.0))
    assert abs(out["export_price"] - 1250.0) < 0.01
    out2 = apply_rozetka_export_settings(dict(t), _settings(), _rule_resolver(20.0))
    assert abs(out2["export_price"] - 1250.0) < 0.01
