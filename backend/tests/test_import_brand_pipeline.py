"""Integration tests for brand resolution in import pipeline.

Tests the complete flow from supplier data to brand_id assignment.
"""

import sys
import types
from unittest.mock import MagicMock, patch

# Stub database module
if "app.core.database" not in sys.modules:
    _db_stub = types.ModuleType("app.core.database")
    _db_stub.engine = None
    sys.modules["app.core.database"] = _db_stub

import pytest
from app.imports.brand_normalizer import normalize_brand
from app.imports.brand_resolver import BrandResolver, BrandSource, BrandConfidence


class TestBrandNormalization:
    """Test brand normalization edge cases."""

    def test_hp_normalized(self):
        """HP should normalize to HP (short brand whitelist)."""
        assert normalize_brand("HP") == "HP"
        assert normalize_brand("hp") == "Hp"

    def test_2e_normalized(self):
        """2E should normalize to 2E (short brand whitelist)."""
        assert normalize_brand("2E") == "2E"

    def test_xo_normalized(self):
        """XO should normalize to XO (short brand whitelist)."""
        assert normalize_brand("XO") == "XO"

    def test_wd_normalized(self):
        """WD should normalize to WD (short brand whitelist)."""
        assert normalize_brand("WD") == "WD"

    def test_be_quiet_alias(self):
        """be quiet variations should normalize to be quiet!."""
        assert normalize_brand("be quiet") == "be quiet!"
        assert normalize_brand("be quiet!") == "be quiet!"
        assert normalize_brand("BE QUIET") == "be quiet!"
        assert normalize_brand("BE QUIET!") == "be quiet!"

    def test_random_2char_rejected(self):
        """Random 2-char strings should be rejected."""
        assert normalize_brand("AB") is None
        assert normalize_brand("PC") is None
        assert normalize_brand("TV") is None

    def test_generic_terms_rejected(self):
        """Generic terms should be rejected."""
        assert normalize_brand("USB") is None
        assert normalize_brand("HDMI") is None


class TestBrandResolver:
    """Test BrandResolver with short brands and aliases."""

    @pytest.fixture
    def resolver(self):
        """Create a BrandResolver instance."""
        return BrandResolver(auto_create_brands=False)

    def test_resolve_hp(self, resolver):
        """HP should resolve to brand_id=19."""
        result = resolver.resolve("HP", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert result is not None
        assert result.name == "HP"
        assert result.id == 19  # HP brand_id in DB

    def test_resolve_2e(self, resolver):
        """2E should resolve to brand_id=64."""
        result = resolver.resolve("2E", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert result is not None
        assert result.name == "2E"
        assert result.id == 64  # 2E brand_id in DB

    def test_resolve_xo(self, resolver):
        """XO should resolve to brand_id=95."""
        result = resolver.resolve("XO", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert result is not None
        assert result.name == "XO"
        assert result.id == 95  # XO brand_id in DB

    def test_resolve_wd(self, resolver):
        """WD should resolve to brand_id=102."""
        result = resolver.resolve("WD", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert result is not None
        assert result.name == "WD"
        assert result.id == 102  # WD brand_id in DB

    def test_resolve_be_quiet_alias(self, resolver):
        """be quiet should resolve to be quiet! (id=61)."""
        result = resolver.resolve("be quiet!", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert result is not None
        assert result.name == "be quiet!"
        assert result.id == 61  # be quiet! brand_id in DB

    def test_resolve_unknown_brand(self, resolver):
        """Unknown brand should return None (not auto-create)."""
        result = resolver.resolve("SomeUnknownBrand", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert result is None

    def test_resolve_normalized_unknown(self, resolver):
        """Brand that normalizes but not in DB returns None."""
        result = resolver.resolve("EnerGenie", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert result is None  # Not in brands table


class TestImportRunnerBrandResolution:
    """Test ImportRunner brand resolution logic."""

    @pytest.fixture
    def runner(self):
        """Create ImportRunner instance."""
        from app.imports.import_runner import ImportRunner
        return ImportRunner(supplier_id=1, supplier_code='test')

    @pytest.fixture
    def mock_product(self):
        """Create a mock NormalizedProduct."""
        from dataclasses import dataclass, field
        @dataclass
        class MockProduct:
            supplier_sku: str = "TEST001"
            sku: str = "TEST-SKU-001"
            name: str = "Test Product"
            brand: str = ""
            category_path: str = "Electronics"
            price: int = 1000
            old_price: int = None
            in_stock: bool = True
            images: list = field(default_factory=list)
            attributes: list = field(default_factory=list)
            raw_attributes: list = field(default_factory=list)
            seo_title: str = ""
            seo_description: str = ""
            focus_keyphrase: str = ""
        return MockProduct()

    def test_resolve_brand_hp(self, runner, mock_product):
        """HP brand should resolve correctly."""
        mock_product.brand = "HP"
        with patch.object(runner, 'brand_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = MagicMock(id=19, name="HP")
            with patch('psycopg2.connect'):
                brand_id = runner._resolve_brand(None, mock_product)
                assert brand_id == 19
                assert runner.brands_resolved == 1

    def test_resolve_brand_2e(self, runner, mock_product):
        """2E brand should resolve correctly."""
        mock_product.brand = "2E"
        with patch.object(runner, 'brand_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = MagicMock(id=64, name="2E")
            with patch('psycopg2.connect'):
                brand_id = runner._resolve_brand(None, mock_product)
                assert brand_id == 64

    def test_resolve_brand_be_quiet(self, runner, mock_product):
        """be quiet should resolve to be quiet!."""
        mock_product.brand = "be quiet"
        with patch.object(runner, 'brand_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = MagicMock(id=61, name="be quiet!")
            with patch('psycopg2.connect'):
                brand_id = runner._resolve_brand(None, mock_product)
                assert brand_id == 61

    def test_preserve_existing_brand(self, runner, mock_product):
        """Existing brand should be preserved when no new brand."""
        mock_product.brand = ""
        with patch.object(runner, 'brand_resolver') as mock_resolver:
            # No new brand, but existing brand_id
            brand_id = runner._resolve_brand(None, mock_product, existing_brand_id=42)
            assert brand_id == 42
            assert runner.brands_preserved == 1

    def test_new_brand_overwrites_existing(self, runner, mock_product):
        """New valid brand should overwrite existing."""
        mock_product.brand = "HP"
        with patch.object(runner, 'brand_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = MagicMock(id=19, name="HP")
            with patch('psycopg2.connect'):
                # Existing brand is different
                brand_id = runner._resolve_brand(None, mock_product, existing_brand_id=42)
                assert brand_id == 19  # Should use new brand, not existing

    def test_unknown_brand_no_auto_create(self, runner, mock_product):
        """Unknown brand should not auto-create and return None."""
        mock_product.brand = "SomeUnknownBrand"
        with patch.object(runner, 'brand_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = None  # Not found
            with patch('psycopg2.connect'):
                brand_id = runner._resolve_brand(None, mock_product)
                assert brand_id is None
                assert runner.brands_unresolved == 1

    def test_unresolved_brand_tracking(self, runner, mock_product):
        """Unresolved brands should be tracked for audit."""
        mock_product.brand = "EnerGenie"
        with patch.object(runner, 'brand_resolver') as mock_resolver:
            mock_resolver.resolve.return_value = None
            with patch('psycopg2.connect'):
                runner._resolve_brand(None, mock_product)
        
        stats = runner.get_brand_stats()
        assert stats['unresolved'] == 1
        assert 'EnerGenie' in stats['unresolved_brands']


class TestImportPipelineDryRun:
    """Dry-run tests for the import pipeline."""

    def test_dclink_hp_product_flow(self):
        """Test DC-Link HP product through full flow."""
        # Simulate what DCLinkImporter would produce
        from dataclasses import dataclass, field
        @dataclass
        class MockProduct:
            supplier_sku: str = "HP001"
            sku: str = "DCL-HP001"
            name: str = "Багатофункціональний пристрій HP LaserJet Pro M141a"
            brand: str = ""  # Will be extracted by find_brand_in_name
            category_path: str = "Принтери та МФУ"
            price: int = 500000
            old_price: int = None
            in_stock: bool = True
            images: list = field(default_factory=list)
            attributes: list = field(default_factory=list)
            raw_attributes: list = field(default_factory=list)
            seo_title: str = ""
            seo_description: str = ""
            focus_keyphrase: str = ""
        
        product = MockProduct()
        
        # Step 1: Extract brand from name
        from app.imports.brand_extractor import find_brand_in_name
        extracted = find_brand_in_name(product.name)
        assert extracted == "HP", f"Expected 'HP', got '{extracted}'"
        
        # Step 2: Normalize
        normalized = normalize_brand(extracted)
        assert normalized == "HP", f"Expected 'HP', got '{normalized}'"
        
        # Step 3: Resolve
        resolver = BrandResolver(auto_create_brands=False)
        resolved = resolver.resolve("HP", BrandSource.EXTRACTED_FROM_NAME, BrandConfidence.HIGH)
        assert resolved is not None, "HP should resolve to brand_id=19"
        assert resolved.id == 19, f"Expected brand_id=19, got {resolved.id}"

    def test_dclink_be_quiet_product_flow(self):
        """Test DC-Link be quiet! product through full flow."""
        from dataclasses import dataclass, field
        @dataclass
        class MockProduct:
            supplier_sku: str = "BQ001"
            sku: str = "DCL-BQ001"
            name: str = "Блок живлення be quiet! Dark Power 14 1000W"
            brand: str = ""
            category_path: str = "Блоки живлення"
            price: int = 1500000
            old_price: int = None
            in_stock: bool = True
            images: list = field(default_factory=list)
            attributes: list = field(default_factory=list)
            raw_attributes: list = field(default_factory=list)
            seo_title: str = ""
            seo_description: str = ""
            focus_keyphrase: str = ""
        
        product = MockProduct()
        
        # Step 1: Extract brand from name
        from app.imports.brand_extractor import find_brand_in_name
        extracted = find_brand_in_name(product.name)
        assert extracted == "be quiet!", f"Expected 'be quiet!', got '{extracted}'"
        
        # Step 2: Normalize (should handle alias)
        normalized = normalize_brand(extracted)
        assert normalized == "be quiet!", f"Expected 'be quiet!', got '{normalized}'"
        
        # Step 3: Resolve
        resolver = BrandResolver(auto_create_brands=False)
        resolved = resolver.resolve("be quiet!", BrandSource.EXTRACTED_FROM_NAME, BrandConfidence.HIGH)
        assert resolved is not None, "be quiet! should resolve to brand_id=61"
        assert resolved.id == 61, f"Expected brand_id=61, got {resolved.id}"

    def test_itlink_vendor_flow(self):
        """Test IT-Link vendor field through full flow."""
        # IT-Link uses vendor field directly
        vendor = "Samsung"
        
        # Step 1: Normalize
        normalized = normalize_brand(vendor)
        assert normalized == "Samsung"
        
        # Step 2: Resolve
        resolver = BrandResolver(auto_create_brands=False)
        resolved = resolver.resolve("Samsung", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert resolved is not None, "Samsung should resolve"
        assert resolved.name == "Samsung"

    def test_unknown_brand_no_creation(self):
        """Test that unknown brand does not auto-create."""
        resolver = BrandResolver(auto_create_brands=False)
        resolved = resolver.resolve("SomeUnknownBrand", BrandSource.VENDOR_FIELD, BrandConfidence.HIGH)
        assert resolved is None, "Unknown brand should not resolve"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
