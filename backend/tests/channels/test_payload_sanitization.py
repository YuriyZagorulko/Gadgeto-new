"""Tests for Rozetka payload sanitization."""

import pytest

from app.channels.rozetka.payload import _sanitize_name


class TestSanitizeName:
    """Tests for _sanitize_name (HTML tag stripping from product names)."""

    def test_strips_leading_bracket(self):
        assert _sanitize_name("<Noctua NF-A6x15 FLX") == "Noctua NF-A6x15 FLX"

    def test_strips_trailing_bracket(self):
        assert _sanitize_name("Sound Card Manli C-Media 8738 > bulk") == "Sound Card Manli C-Media 8738  bulk"

    def test_strips_both_brackets(self):
        assert _sanitize_name("<19,8 dB(A)>") == "19,8 dB(A)"

    def test_strips_html_fragment(self):
        assert _sanitize_name("USB 3.0 < 5Gbps") == "USB 3.0  5Gbps"

    def test_preserves_legitimate_less_than_in_product_name(self):
        # These are legitimate characters in product names (e.g., "< 10")
        # but the function strips them per the audit requirement to fix
        # the 2 products with actual HTML-tag-like characters.
        # If Rozetka accepts "< 10"" this would need to be reverted.
        result = _sanitize_name("Cable < 10m")
        assert result == "Cable  10m"

    def test_preserves_numbers_and_units(self):
        assert _sanitize_name("SSD 1TB PCIe 4.0 NVMe") == "SSD 1TB PCIe 4.0 NVMe"

    def test_preserves_unicode(self):
        assert _sanitize_name("Ноутбук Lenovo ThinkPad < T14s") == "Ноутбук Lenovo ThinkPad  T14s"

    def test_strips_multiple_brackets(self):
        assert _sanitize_name("<A> Product <B>") == "A Product B"

    def test_empty_string(self):
        assert _sanitize_name("") == ""

    def test_strips_only_whitespace(self):
        assert _sanitize_name("  ") == ""

    def test_no_brackets_unchanged(self):
        original = "Noctua NF-A6x15 PWM"
        assert _sanitize_name(original) == original

    def test_real_product_name_from_audit(self):
        # These are the 2 real product names that caused Rozetka rejection
        # (names contain < and > characters)
        name1 = "Кулер Noctua NF-A6x15 FLX <19,8 dB(A)>"
        name2 = "Кулер Noctua NF-A6x15 PWM <19,8 dB(A)>"
        # After sanitization, both names should be clean
        assert "<" not in _sanitize_name(name1)
        assert ">" not in _sanitize_name(name1)
        assert "<" not in _sanitize_name(name2)
        assert ">" not in _sanitize_name(name2)
