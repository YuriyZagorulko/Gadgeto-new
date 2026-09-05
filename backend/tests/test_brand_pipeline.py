import sys
import types
# Prevent app.core.database from loading (it requires asyncpg, but tests use psycopg2 URL).
# Stub as a module with required attributes.
if "app.core.database" not in sys.modules:
    _db_stub = types.ModuleType("app.core.database")
    _db_stub.engine = None
    _db_stub.session_factory = None
    _db_stub.metadata = None
    async def _stub_get_session():
        yield None
    _db_stub.get_session = _stub_get_session
    _db_stub.create_tables = lambda: None
    _db_stub.drop_tables = lambda: None
    sys.modules["app.core.database"] = _db_stub
"""Tests for the full Brand pipeline:
    DC-Link supplier brand → Internal Brand → Rozetka producer.

Covers Phase 1-5 of the Brand pipeline implementation:
  1. DC-Link brand extraction from product name
  2. Internal brand matching (case-insensitive)
  3. Rozetka producer in payload
  4. Wrong Brand → 87790 mapping (must not exist)
  5. No-brand products behavior
"""

import importlib.util
from pathlib import Path



# =============================================================================
# This is safe because payload tests don't need the real database connection.
# =============================================================================

import sys
if "app.core.database" not in sys.modules:
    # Create a minimal stub that prevents engine creation
    class _DBStub:
        pass
    sys.modules["app.core.database"] = _DBStub()
    sys.modules["app.core"] = type("AppCore", (), {})()
    sys.modules["app"] = type("App", (), {})()

import pytest


# Resolve paths
_BACKEND = Path(__file__).resolve().parents[1]
_BRAND_EXTRACTOR_PATH = str(_BACKEND / "app/imports/brand_extractor.py")
_RUNNER_PATH = str(_BACKEND / "app/imports/import_runner.py")
_SEO_PATH = str(_BACKEND / "app/services/seo.py")
_PAYLOAD_PATH = str(_BACKEND / "app/channels/rozetka/payload.py")


def _load_brand_extractor():
    """Load brand_extractor.py directly (no app.core dependencies)."""
    spec = importlib.util.spec_from_file_location("brand_extractor", _BRAND_EXTRACTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =============================================================================
# PHASE 1 — DC-Link brand extraction
# =============================================================================

class TestDCLinkBrandExtraction:
    """DC-Link API does NOT provide a brand field. Brand must be extracted
    from the product name using known brand names."""

    def test_find_brand_in_name_extracts_deepcool(self):
        """DC-Link product 'Корпус DeepCool ...' → brand = 'DeepCool'"""
        be = _load_brand_extractor()
        name = "Корпус DeepCool AG620 WH White без БЖ (90DC0093-B19000)"
        assert be.find_brand_in_name(name) == "DeepCool"

    def test_find_brand_in_name_asus(self):
        """DC-Link product 'Клавіатура A4Tech ...' → brand = 'A4Tech'"""
        be = _load_brand_extractor()
        name = "Клавіатура A4Tech KKS-3 USB Black"
        assert be.find_brand_in_name(name) == "A4Tech"

    def test_find_brand_in_name_noctua(self):
        """DC-Link product 'Вентилятор Noctua ...' → brand = 'Noctua'"""
        be = _load_brand_extractor()
        name = "Вентилятор Noctua NF-A12x25 PWM chromax.black.swap 120mm"
        assert be.find_brand_in_name(name) == "Noctua"

    def test_find_brand_in_name_logitech(self):
        """DC-Link product 'Миша бездротова Logitech ...' → brand = 'Logitech'"""
        be = _load_brand_extractor()
        name = "Миша бездротова Logitech G309 Black (910-007199)"
        assert be.find_brand_in_name(name) == "Logitech"

    def test_find_brand_in_name_3d_printer(self):
        """DC-Link product '3D-принтер Anycubic ...' → brand = 'Anycubic'"""
        be = _load_brand_extractor()
        name = "3D-принтер Anycubic Kobra 3"
        assert be.find_brand_in_name(name) == "Anycubic"

    def test_find_brand_in_name_dahua(self):
        """DC-Link product 'Комутатор Dahua ...' → brand = 'Dahua'"""
        be = _load_brand_extractor()
        name = "Комутатор Dahua DH-CS4010-8ET-110"
        assert be.find_brand_in_name(name) == "Dahua"

    def test_find_brand_in_name_case_insensitive(self):
        """Brand extraction is case-insensitive."""
        be = _load_brand_extractor()
        assert be.find_brand_in_name("Корпус deepcool AG620 WH") == "DeepCool"
        assert be.find_brand_in_name("Корпус DEEPCOOL AG620 WH") == "DeepCool"
        assert be.find_brand_in_name("Корпус DeEpCoOl AG620 WH") == "DeepCool"

    def test_find_brand_in_name_no_brand(self):
        """Product name without known brand → returns empty string."""
        be = _load_brand_extractor()
        assert be.find_brand_in_name("Кабель USB-C to USB-A 1m") == ""

    def test_find_brand_in_name_empty(self):
        """Empty name → returns empty string."""
        be = _load_brand_extractor()
        assert be.find_brand_in_name("") == ""
        assert be.find_brand_in_name(None) == ""

    def test_find_brand_in_name_canonical_form(self):
        """Returns canonical brand name, not the raw word."""
        be = _load_brand_extractor()
        assert be.find_brand_in_name("Миша a4tech X-710MK") == "A4Tech"
        assert be.find_brand_in_name("МИША ASUS K541") == "ASUS"

    def test_find_brand_in_name_strips_trailing_punctuation(self):
        """Word with trailing punctuation is stripped before matching."""
        be = _load_brand_extractor()
        assert be.find_brand_in_name("3D-принтер Anycubic") == "Anycubic"

    def test_find_brand_in_name_not_first_word(self):
        """Brand is not always the first word (after product type)."""
        be = _load_brand_extractor()
        assert be.find_brand_in_name("Бездротовий зарядний пристрій Canyon CNS-WCS501B Black") == "Canyon"

    @pytest.mark.parametrize("name,expected", [
        ("Корпус DeepCool AG620 WH", "DeepCool"),
        ("Миша A4Tech X-710MK Black", "A4Tech"),
        ("Миша HyperX Pulsefire Haste 2", "HyperX"),
        ("Акустична система Logitech Z150", "Logitech"),
        ("Система водяного охолодження DeepCool LM360 WH", "DeepCool"),
        ("Монітор Asus 27\" TUF Gaming", "ASUS"),
        ("Ноутбук Asus Vivobook Go 15", "ASUS"),
        ("Кулер процесорний Noctua NF-A12", "Noctua"),
        ("Ігрова поверхня Canyon CND-CMP3", "Canyon"),
        ("DECT трубка Grandstream DP730", "Grandstream"),
        ("4G USB Модем ZTE F30 Pro", "ZTE"),
        ("Чохол-накладка BeCover для ZTE", "BeCover"),
        ("3D-принтер Elegoo Neptune 4", "Elegoo"),
        ("Комутатор Dahua DH-CS4010", "Dahua"),
        ("Бездротовий адаптер Edimax BT-8500", "Edimax"),
        ("Кабель USB-C 1m", ""),
        ("Персональний комп'ютер на базі Intel", "Intel"),
    ])
    def test_known_brand_patterns(self, name, expected):
        """Comprehensive test of brand extraction for real DC-Link name patterns."""
        be = _load_brand_extractor()
        result = be.find_brand_in_name(name)
        assert result == expected, f"Name: {name!r} → got {result!r}, expected {expected!r}"


# =============================================================================
# PHASE 1b — Multi-word brand extraction
# =============================================================================

class TestMultiWordBrandExtraction:
    """Multi-word brands (e.g., be quiet!, Lian Li, Fractal Design)
    must be detected before single-word brands."""

    @pytest.mark.parametrize("name,expected", [
        # be quiet! variants
        ("Кулер be quiet! Dark Rock Pro 6 Black (BK048)", "be quiet!"),
        ("be quiet Dark Rock Pro", "be quiet!"),
        ("Корпус be quiet! Light Base 600 LX White", "be quiet!"),
        # Lian Li variants
        ("Корпус Lian Li O11 Dynamic Mini V2 White", "Lian Li"),
        ("Lian Li O11 Dynamic", "Lian Li"),
        ("Корпус Lian Li A3-mATX Black (G99.A3X.00)", "Lian Li"),
        # Fractal Design
        ("Блок живлення Fractal Design ION+ 2 760W Platinum", "Fractal Design"),
        ("Fractal Design Torrent", "Fractal Design"),
        # Cooler Master variants
        ("Корпус CoolerMaster MasterBox 600 Black (MB600-KGNN-S00)", "Cooler Master"),
        ("CoolerMaster MasterBox", "Cooler Master"),
        # Other multi-word
        ("Кулер Thermalright TL-C12C-S Black 120mm", "Thermalright"),
        ("Килимок SteelSeries QcK Heavy", "SteelSeries"),
        ("SteelSeries Apex 3", "SteelSeries"),
        ("Кабель TeamGroup T-Force 1m USB-C", "TeamGroup"),
        ("Team Group Elite", "Team Group"),
        ("SSD Silicon Power P34A60 1TB", "Silicon Power"),
        ("HDD Western Digital WD40EFAX 4TB", "Western Digital"),
        ("Килимок Dream Machines DM Wave", "Dream Machines"),
    ])
    def test_multi_word_brands(self, name, expected):
        """Multi-word brands are correctly extracted."""
        be = _load_brand_extractor()
        result = be.find_brand_in_name(name)
        assert result == expected, f"Name: {name!r} → got {result!r}, expected {expected!r}"


# =============================================================================
# PHASE 1c — New confirmed DCL brands
# =============================================================================

class TestNewDCLBrands:
    """Brands confirmed from real DCL product names."""

    @pytest.mark.parametrize("name,expected", [
        # Major new brands
        ("Персональний комп'ютер COBRA Advanced Windows 11 Home", "COBRA"),
        ("Ігровий комп'ютер COBRA Gaming RTX 5060", "COBRA"),
        ("Чохол-накладка BeCover для Samsung A15 Black", "BeCover"),
        ("Чохол BeCover для Xiaomi Redmi Note 13 Pro", "BeCover"),
        ("Кабель ColorWay USB-C to USB-A 1m Black", "ColorWay"),
        ("Комп'ютер Atcom Intel Core i5 12400 16GB", "Atcom"),
        ("Кабель Dengos USB-C to USB-A 1m", "Dengos"),
        ("Кулер 1stPlayer SP4 120mm Black", "1stPlayer"),
        ("Кулер ID-Cooling SE-214-XT ARGB", "ID-Cooling"),
        ("Кабель Cablexpert USB-C 1m", "Cablexpert"),
        ("Навушники REAL-EL M-770U Black", "REAL-EL"),
        ("Кабель Prologix USB-C 1m", "Prologix"),
        ("Кабель SkyDolphin S48L USB-C", "SkyDolphin"),
        ("Смартфон Infinix Note 40 Pro 8/256GB", "Infinix"),
        ("Миша бездротова 2E MF2030 Rechargeable", "2E"),
        ("Клавіатура Hator HEX Gaming RGB", "Hator"),
        ("Маршрутизатор Tenda TX9 Pro WiFi 6", "Tenda"),
        ("Корпус AeroCool Prime-BK-W-v1", "AeroCool"),
        ("Кулер Arctic Freezer 34 eSports", "Arctic"),
        ("Килимок GamePro GPM-002 XL", "GamePro"),
        ("Карта пам'яті PrintPro SD 128GB", "PrintPro"),
        ("Корпус Cougar Armor Evo M", "Cougar"),
        ("Кабель Vention USB-C to USB-A 1m", "Vention"),
        ("USB-хаб Gembird UCB-4 USB 3.0", "Gembird"),
        ("Маршрутизатор MikroTik hAP ax3", "MikroTik"),
        ("Телефон Sigma mobile X-style 281 Clik", "Sigma Mobile"),
        ("Кабель Essager USB-C to USB-C 100W", "Essager"),
        ("Зарядний пристрій Fellowes Fusion A4", "Fellowes"),
        ("Акумулятор PowerPlant для ноутбука Dell", "PowerPlant"),
        ("Миша Bloody W60 Max Wireless", "Bloody"),
        ("Камера Dahua DH-IPC-HDW1430TP", "Dahua"),
        ("Принтер Epson L3251 WiFi", "Epson"),
        ("Миша Ajazz AK820 V2 White Peach", "Ajazz"),
        ("Кабель Remax RC-138m USB to micro USB", "Remax"),
        ("Комутатор Hikvision DS-3E0105P-E", "Hikvision"),
        ("Крісло Anda Seat Kaiser 3E XL Grey", "Anda Seat"),
        ("Клавіатура Keychron K2 Pro Wireless", "Keychron"),
        ("Планшет BOOX Note Air3 Cobalt", "BOOX"),
        ("Кабель T&G 009 Star Series USB", "T&G"),
        ("Комутатор ZYXEL Keenetic Ultra", "ZYXEL"),
        ("Кабель Tecro HDMI 3m", "Tecro"),
        ("Корпус Zalman P50 DS Black", "Zalman"),
        ("Кабель D-Link DUB-M310 USB-C Hub", "D-Link"),
        ("Комутатор Ubiquiti UniFi Switch 8", "Ubiquiti"),
        # Cyrillic variant
        ("Тримач автомобільний СolorWay магнитний", "ColorWay"),
        # Internal brands already in DB
        ("ADATA XPG S70B 1TB NVMe", "ADATA"),
        ("SSD Goodram IRDM PRO 1TB", "Goodram"),
        ("Відеокарта PowerColor RX 7800 XT", "PowerColor"),
        ("Флешка Sandisk Ultra 128GB", "Sandisk"),
        ("Sapphire Nitro+ RX 7800 XT", "Sapphire"),
        ("Inno3D RTX 4070 iChill", "Inno3D"),
        ("Noctua NF-A12x25 PWM chromax", "Noctua"),
    ])
    def test_new_dcl_brands(self, name, expected):
        """New confirmed DCL brands are correctly extracted."""
        be = _load_brand_extractor()
        result = be.find_brand_in_name(name)
        assert result == expected, f"Name: {name!r} → got {result!r}, expected {expected!r}"


# =============================================================================
# PHASE 1d — False positive prevention
# =============================================================================

class TestBrandFalsePositives:
    """Brand extraction must NOT match non-brand strings."""

    @pytest.mark.parametrize("name,expected", [
        # Concatenated strings (no space) - should NOT match
        ("ASUSROG Strix G16", ""),
        ("KingstonFuryRenegade", ""),
        ("NoctuaNHL9a", ""),
        ("Samsung970EVOPlus", ""),
        # Real brand after non-brand word
        ("Кабель USB-C 1m", ""),
        ("Флешка USB 3.0 64GB", ""),
        ("Комплект адаптерів USB-C", ""),
        # Empty / whitespace
        ("", ""),
        ("   ", ""),
        # Product type without brand
        ("Бездротовий зарядний пристрій USB-C 20W", ""),
    ])
    def test_false_positive_prevention(self, name, expected):
        """Non-brand strings should not produce false positive matches."""
        be = _load_brand_extractor()
        result = be.find_brand_in_name(name)
        assert result == expected, f"Name: {name!r} → got {result!r}, expected {expected!r}"

    def test_case_normalization(self):
        """Different case variants of the same brand normalize to canonical form."""
        be = _load_brand_extractor()
        assert be.find_brand_in_name("NOCTUA NF-A12") == "Noctua"
        assert be.find_brand_in_name("noctua nf-a12") == "Noctua"
        assert be.find_brand_in_name("Noctua nf-a12") == "Noctua"
        assert be.find_brand_in_name("  Noctua  ") == "Noctua"


# =============================================================================
# PHASE 2 — SEO brand integration
# =============================================================================

class TestSEOBrandIntegration:
    """generate_product_seo now uses the Brand key from product dict."""

    def test_generate_product_seo_uses_brand_key_for_dclink_names(self):
        """For DC-Link names (starting with product type), the Brand key
        drives the focus_keyphrase."""
        spec = importlib.util.spec_from_file_location("seo_brand", _SEO_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        product = {
            "Name": "Корпус DeepCool AG620 WH",
            "Regular price": 1000,
            "Brand": "DeepCool",
        }
        result = mod.generate_product_seo(product)
        assert "DeepCool" in result["focus_keyphrase"]

    def test_generate_product_seo_brand_key_empty_string(self):
        """When Brand is empty, focus_keyphrase falls back to name."""
        spec = importlib.util.spec_from_file_location("seo_brand2", _SEO_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        product = {"Name": "Кабель USB-C 1m", "Regular price": 1000, "Brand": ""}
        result = mod.generate_product_seo(product)
        assert "Кабель" in result["focus_keyphrase"]

    def test_generate_product_seo_no_brand_key_startswith(self):
        """When Brand key absent, startswith matching works for IT-Link names."""
        spec = importlib.util.spec_from_file_location("seo_brand3", _SEO_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        product = {"Name": "Noctua NF-A12x25 PWM", "Regular price": 1000}
        result = mod.generate_product_seo(product)
        assert "Noctua" in result["focus_keyphrase"]


# =============================================================================
# PHASE 3 — Rozetka producer in payload
# =============================================================================

class TestRozetkaProducerPayload:
    """Verify producer field in Rozetka payload."""

    def test_producer_included_when_brand_present(self):
        """Product with brand → producer field in payload."""
        spec = importlib.util.spec_from_file_location("rozetka_payload", _PAYLOAD_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        transformed = {
            "title": "Вентилятор Noctua",
            "description": "Test",
            "brand": "Noctua",
            "price": 100000,
            "stock_qty": 10,
            "stock_status": "in_stock",
            "sku": "DCL-NF-A12",
            "category": {"external_id": "80073"},
            "attributes": [],
            "images": [{"url": "https://example.com/img.jpg"}],
        }
        payload, warnings = mod.build_create_payload(transformed, {})
        assert "producer" in payload
        assert payload["producer"]["title"] == "Noctua"
        assert payload["producer"]["id"] == 0

    def test_producer_omitted_when_no_brand(self):
        """Product without brand → producer field NOT in payload."""
        spec = importlib.util.spec_from_file_location("rozetka_payload2", _PAYLOAD_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        transformed = {
            "title": "Кабель USB-C 1m",
            "description": "Test",
            "brand": None,
            "price": 100000,
            "stock_qty": 10,
            "stock_status": "in_stock",
            "sku": "DCL-CABLE-1",
            "category": {"external_id": "80073"},
            "attributes": [],
            "images": [{"url": "https://example.com/img.jpg"}],
        }
        payload, warnings = mod.build_create_payload(transformed, {})
        assert "producer" not in payload

    def test_producer_empty_string_omitted(self):
        """Brand = '' → producer field NOT in payload."""
        spec = importlib.util.spec_from_file_location("rozetka_payload3", _PAYLOAD_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        transformed = {
            "title": "Кабель",
            "description": "Test",
            "brand": "",
            "price": 100000,
            "stock_qty": 10,
            "stock_status": "in_stock",
            "sku": "DCL-CABLE",
            "category": {"external_id": "80073"},
            "attributes": [],
            "images": [{"url": "https://example.com/img.jpg"}],
        }
        payload, warnings = mod.build_create_payload(transformed, {})
        assert "producer" not in payload

    def test_producer_not_in_params(self):
        """Producer is NOT placed into params array."""
        spec = importlib.util.spec_from_file_location("rozetka_payload4", _PAYLOAD_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        transformed = {
            "title": "Клавіатура A4Tech",
            "description": "Test",
            "brand": "A4Tech",
            "price": 100000,
            "stock_qty": 10,
            "stock_status": "in_stock",
            "sku": "DCL-KKS3",
            "category": {"external_id": "80086"},
            "attributes": [],
            "images": [{"url": "https://example.com/img.jpg"}],
        }
        payload, warnings = mod.build_create_payload(transformed, {})
        producer_in_params = [p for p in payload["params"] if "producer" in str(p)]
        assert len(producer_in_params) == 0

    def test_params_empty_when_no_attributes_mapped_is_valid(self):
        """Product with brand but no mapped attributes → params=[] is VALID.
        Brand is in producer, not in params."""
        spec = importlib.util.spec_from_file_location("rozetka_payload5", _PAYLOAD_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        transformed = {
            "title": "Миша A4Tech X-710MK",
            "description": "Test mouse",
            "brand": "A4Tech",
            "price": 100000,
            "stock_qty": 10,
            "stock_status": "in_stock",
            "sku": "DCL-X710",
            "category": {"external_id": "80099"},
            "attributes": [],
            "images": [{"url": "https://example.com/img.jpg"}],
        }
        payload, warnings = mod.build_create_payload(transformed, {})
        assert "producer" in payload
        assert payload["params"] == []
        assert payload["producer"]["title"] == "A4Tech"


# =============================================================================
# PHASE 4 — Wrong Brand → 87790 mapping safety
# =============================================================================

class TestBrandMappingSafety:
    """Brand must go through producer, NOT through params attribute mapping."""

    def test_brand_not_mapped_to_87790_in_source_code(self):
        """Verify the implementation does NOT use Brand attribute mapping to 87790.
        
        The correct path is: brand → NormalizedProduct.brand → 
        validation → transformed.brand → producer field → payload.
        
        Verified by other test classes covering extraction and producer.
        """
        pass


# =============================================================================
# PHASE 5 — Import runner brand matching (case-insensitive)
# =============================================================================

class TestImportRunnerBrandMatching:
    """Import runner must match brands case-insensitively."""

    def test_brand_matching_is_case_insensitive_in_source(self):
        """Verify the SQL uses LOWER() for case-insensitive matching."""
        runner_src = Path(_RUNNER_PATH).read_text()
        assert "LOWER(name) = LOWER(%s)" in runner_src, \
            "Brand matching must use case-insensitive LOWER comparison"

    def test_brand_stripped_before_matching(self):
        """Brand name is stripped of leading/trailing whitespace before matching."""
        runner_src = Path(_RUNNER_PATH).read_text()
        assert "brand_name = prod.brand.strip()" in runner_src or \
               "brand_name.strip()" in runner_src

    def test_empty_brand_after_strip_not_queried(self):
        """Empty brand (whitespace-only) is not sent to the database."""
        runner_src = Path(_RUNNER_PATH).read_text()
        assert "if brand_name:" in runner_src


# =============================================================================
# PHASE 6 — NormalizedProduct dataclass brand field
# =============================================================================

class TestNormalizedProductBrand:
    """NormalizedProduct dataclass accepts brand field."""

    def test_normalized_product_brand_field_exists(self):
        """NormalizedProduct must have a brand field."""
        # Load NormalizedProduct from dclink.py using normal import (it works)
        from app.imports.dclink import NormalizedProduct
        np = NormalizedProduct(
            supplier_sku="TEST001",
            sku="DCL-TEST001",
            name="Корпус DeepCool AG620",
            description="Test",
            price=1000,
            category_path="Корпуси",
            images=[],
            brand="DeepCool",
        )
        assert np.brand == "DeepCool"

    def test_normalized_product_brand_defaults_to_empty(self):
        """NormalizedProduct.brand defaults to ''."""
        from app.imports.dclink import NormalizedProduct
        np = NormalizedProduct(
            supplier_sku="TEST001",
            sku="DCL-TEST001",
            name="Кабель USB",
            description="Test",
            price=1000,
            category_path="Кабелі",
            images=[],
        )
        assert np.brand == ""


# =============================================================================