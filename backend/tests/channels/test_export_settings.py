"""
Regression tests for export_settings price calculation.

Verifies the correct conversion from minor units (kopiykas) to major units
(UAH) before markup/rounding, so the Rozetka API receives correct prices.
"""

from decimal import Decimal
from app.channels.export_settings import calculate_export_price, parse_float


def test_calculate_export_price_no_markup():
    """175408 kop = 1754.08 UAH, 0% markup, no rounding."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": 0}
    result = calculate_export_price(175408, settings)
    assert abs(result - 1754.08) < 0.001, f"Expected 1754.08, got {result}"


def test_calculate_export_price_percentage_markup():
    """175408 kop = 1754.08 UAH * 1.30 = 2280.304 UAH."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 30.0, "price_rounding": 0}
    result = calculate_export_price(175408, settings)
    assert abs(result - 2280.30) < 0.01, f"Expected ~2280.30, got {result}"


def test_calculate_export_price_fixed_markup():
    """175408 kop = 1754.08 UAH + 50.00 = 1804.08 UAH."""
    settings = {"price_markup_type": "fixed", "price_markup_value": 50.0, "price_rounding": 0}
    result = calculate_export_price(175408, settings)
    assert abs(result - 1804.08) < 0.001, f"Expected 1804.08, got {result}"


def test_calculate_export_price_rounding():
    """Round to nearest 10 UAH: 1754.08 -> 1750.00."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": 10}
    result = calculate_export_price(175408, settings)
    assert abs(result - 1750.0) < 0.001, f"Expected 1750.0, got {result}"


def test_calculate_export_price_whole_number():
    """100000 kop = 1000.00 UAH, 0% markup -> 1000.00."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": 0}
    result = calculate_export_price(100000, settings)
    assert abs(result - 1000.0) < 0.001, f"Expected 1000.00, got {result}"


def test_calculate_export_price_one_kop():
    """100001 kop = 1000.01 UAH."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": 0}
    result = calculate_export_price(100001, settings)
    assert abs(result - 1000.01) < 0.001, f"Expected 1000.01, got {result}"


def test_calculate_export_price_one_hryvnia():
    """100050 kop = 1000.50 UAH."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": 0}
    result = calculate_export_price(100050, settings)
    assert abs(result - 1000.50) < 0.001, f"Expected 1000.50, got {result}"


def test_calculate_export_price_zero():
    """Zero price -> 0."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": 0}
    result = calculate_export_price(0, settings)
    assert result == 0.0, f"Expected 0.0, got {result}"


def test_calculate_export_price_negative_handled():
    """Negative base should not go negative (clamped to 0)."""
    settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": 0}
    result = calculate_export_price(-100, settings)
    assert result >= 0, f"Expected >= 0, got {result}"


def test_calculate_export_price_empty_settings():
    """Empty settings use defaults: percentage, 0% markup."""
    result = calculate_export_price(175408, {})
    assert abs(result - 1754.08) < 0.001, f"Expected 1754.08 (defaults), got {result}"


def test_calculate_export_price_rounding_variants():
    """Rounding to various steps (uses ROUND_HALF_UP, so .5 rounds up)."""
    for kop, step, expected in [
        (100000, 10, 1000.0),     # 1000.00 UAH, step 10 -> 1000
        (100099, 10, 1000.0),     # 1000.99 UAH, step 10 -> 1000
        (100100, 10, 1000.0),     # 1001.00 UAH, step 10 -> 1000 (rounds to nearest 10)
        (101000, 10, 1010.0),     # 1010.00 UAH, step 10 -> 1010
        (101099, 10, 1010.0),     # 1010.99 UAH, step 10 -> 1010
        (101500, 10, 1020.0),     # 1015.00 UAH -> 1015/10=101.5 HALF_UP=102 *10=1020
        (100500, 10, 1010.0),     # 1005.00 UAH -> 1005/10=100.5 HALF_UP=101 *10=1010
        (120000, 50, 1200.0),     # 1200.00 UAH, step 50 -> 1200
        (122500, 50, 1250.0),     # 1225/50=24.5 HALF_UP=25 *50=1250
        (100050, 100, 1000.0),    # 1000.50/100=10.005 HALF_UP=10 *100=1000
        (100999, 100, 1000.0),    # 1009.99/100=10.0999 HALF_UP=10 *100=1000
        (105000, 100, 1100.0),    # 1050.00/100=10.5 HALF_UP=11 *100=1100
    ]:
        settings = {"price_markup_type": "percentage", "price_markup_value": 0.0, "price_rounding": step}
        result = calculate_export_price(kop, settings)
        assert abs(result - expected) < 1.0, f"For {kop} kop, step={step}: expected {expected}, got {result}"


def test_parse_float_variants():
    """parse_float handles various inputs correctly."""
    assert parse_float(175408) == 175408.0
    assert parse_float("175408") == 175408.0
    assert parse_float("1754,08") == 1754.08
    assert parse_float("1 754,08") == 1.0  # stops at space
    assert parse_float(None) == 0.0
    assert parse_float("") == 0.0
    assert parse_float("abc") == 0.0