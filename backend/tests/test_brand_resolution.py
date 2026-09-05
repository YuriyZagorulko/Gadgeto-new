"""Tests for the Brand Resolution Layer."""

import sys
import types

if "app.core.database" not in sys.modules:
    _db_stub = types.ModuleType("app.core.database")
    _db_stub.engine = None
    sys.modules["app.core.database"] = _db_stub

import pytest
from app.imports.brand_normalizer import (
    normalize_brand, get_brand_confidence, is_generic_term, is_too_short,
)


class TestBrandNormalization:
    """Test brand name normalization."""

    def test_case_preserved(self):
        assert normalize_brand("MSI") == "MSI"
        assert normalize_brand("msi") == "MSI"
        assert normalize_brand("Asus") == "ASUS"

    def test_whitespace_normalized(self):
        assert normalize_brand("  MSI  ") == "MSI"
        assert normalize_brand("Deep  Cool") == "Deep Cool"

    def test_punctuation_stripped(self):
        assert normalize_brand("MSI,") == "MSI"
        assert normalize_brand("ASUS!") == "ASUS"

    def test_alias_asus(self):
        assert normalize_brand("ASUSTeK") == "ASUS"
        assert normalize_brand("asustek") == "ASUS"

    def test_alias_deepcool(self):
        assert normalize_brand("DEEP COOL") == "Deepcool"
        assert normalize_brand("DeepCool") == "Deepcool"

    def test_generic_terms_rejected(self):
        assert normalize_brand("USB") is None
        assert normalize_brand("HDMI") is None
        assert normalize_brand("Gaming") is None

    def test_too_short_rejected(self):
        assert normalize_brand("A") is None
        assert normalize_brand("AB") is None

    def test_empty_returns_none(self):
        assert normalize_brand("") is None
        assert normalize_brand(None) is None
        assert normalize_brand("   ") is None

    def test_multi_word_brands(self):
        assert normalize_brand("Lian Li") == "Lian Li"
        assert normalize_brand("Cooler Master") == "Cooler Master"
        assert normalize_brand("G.Skill") == "G.Skill"


class TestShortBrandWhitelist:
    """Test that known short brands are accepted."""

    def test_hp_accepted(self):
        """HP is a valid 2-character brand."""
        assert normalize_brand("HP") == "HP"
        assert normalize_brand("hp") is not None  # Case normalized
        assert is_too_short("HP") is False

    def test_2e_accepted(self):
        """2E is a valid 2-character brand."""
        assert normalize_brand("2E") == "2E"
        assert normalize_brand("2e") is not None
        assert is_too_short("2E") is False

    def test_xo_accepted(self):
        """XO is a valid 2-character brand."""
        assert normalize_brand("XO") == "XO"
        assert normalize_brand("xo") is not None
        assert is_too_short("XO") is False

    def test_wd_accepted(self):
        """WD is a valid 2-character brand."""
        assert normalize_brand("WD") == "WD"
        assert normalize_brand("wd") is not None
        assert is_too_short("WD") is False

    def test_random_2char_rejected(self):
        """Random 2-character strings should be rejected."""
        assert normalize_brand("AB") is None
        assert normalize_brand("CD") is None
        assert normalize_brand("XY") is None
        assert normalize_brand("12") is None
        assert normalize_brand("PC") is None
        assert normalize_brand("TV") is None
        assert normalize_brand("IT") is None


class TestBeQuietAlias:
    """Test be quiet! brand alias normalization."""

    def test_be_quiet_lowercase(self):
        assert normalize_brand("be quiet") == "be quiet!"

    def test_be_quiet_with_exclamation(self):
        assert normalize_brand("be quiet!") == "be quiet!"

    def test_be_quiet_uppercase(self):
        assert normalize_brand("BE QUIET") == "be quiet!"

    def test_be_quiet_uppercase_with_exclamation(self):
        assert normalize_brand("BE QUIET!") == "be quiet!"


class TestBrandConfidence:
    """Test confidence detection."""

    def test_direct_match_high(self):
        assert get_brand_confidence("MSI", "MSI") == "HIGH"

    def test_alias_medium(self):
        assert get_brand_confidence("ASUSTeK", "ASUS") == "MEDIUM"

    def test_empty_low(self):
        assert get_brand_confidence("", "MSI") == "LOW"


class TestSupplierExtraction:
    """Test supplier-specific extraction."""

    def test_dclink_extraction(self):
        from app.imports.brand_resolver import extract_brand_dclink, BrandSource
        result = extract_brand_dclink("Корпус DeepCool AG620")
        assert result is not None
        assert result.source == BrandSource.EXTRACTED_FROM_NAME

    def test_dclink_no_brand(self):
        from app.imports.brand_resolver import extract_brand_dclink
        result = extract_brand_dclink("Generic Product XYZ123")
        assert result is None

    def test_itlink_vendor(self):
        from app.imports.brand_resolver import extract_brand_itlink, BrandSource, BrandConfidence
        result = extract_brand_itlink("Noctua", "")
        assert result is not None
        assert result.source == BrandSource.VENDOR_FIELD
        assert result.confidence == BrandConfidence.HIGH


class TestEdgeCases:
    """Test edge cases."""

    def test_none_input(self):
        assert normalize_brand(None) is None

    def test_whitespace_only(self):
        assert normalize_brand("   ") is None

    def test_numbers_not_brands(self):
        assert normalize_brand("123") is None
