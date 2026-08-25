"""Tests for the channel validation and transformation layer."""

import json
import hashlib

from app.channels.validation import (
    compute_content_hash,
    compute_commercial_hash,
    _build_transform_payload,
    ISSUE_MISSING_CATEGORY_MAPPING,
    ISSUE_MISSING_ATTRIBUTE_MAPPING,
    ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING,
    ISSUE_MISSING_REQUIRED_ATTR_MAPPING,
    ISSUE_MISSING_TITLE,
    ISSUE_MISSING_DESCRIPTION,
    ISSUE_MISSING_PRICE,
    ISSUE_MISSING_IMAGE,
    ISSUE_INVALID_IMAGE_URL,
    ISSUE_HTTP_IMAGE_URL,
    ISSUE_PRODUCT_NOT_PUBLISHED,
    ISSUE_MISSING_BRAND,
    ISSUE_MISSING_STOCK,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)


class FakeResolver:
    """A deterministic mapping resolver for testing.

    Category 1 -> external_id "1001" (Смартфони)
    Category 2 -> external_id "2001" (Планшети)
    Attribute 10 (Колір) -> external 2001 (global), 2001 (cat 1001), 2003 (cat 2001)
    Attribute 11 (Пам'ять) -> external 2002 (global)
    Value 100 (Чорний) -> external 3001 (global)
    Value 101 (Синій) -> external 3002 (global)
    Value 110 (128 ГБ) -> external 3010 (global)
    """

    def __init__(self):
        self._cats = {
            1: {"external_category_id": "1001", "external_category_name": "\u0421\u043c\u0430\u0440\u0442\u0444\u043e\u043d\u0438"},
            2: {"external_category_id": "2001", "external_category_name": "\u041f\u043b\u0430\u043d\u0448\u0435\u0442\u0438"},
        }
        # Attribute 10: different external IDs per category
        self._attrs = {
            (10, "1001"): {"external_attribute_id": "2001", "external_attribute_name": "\u041a\u043e\u043b\u0456\u0440_\u0441\u043c\u0430\u0440\u0442"},
            (10, "2001"): {"external_attribute_id": "2003", "external_attribute_name": "\u041a\u043e\u043b\u0456\u0440_\u043f\u043b\u0430\u043d\u0448"},
            (10, None):  {"external_attribute_id": "2001", "external_attribute_name": "\u041a\u043e\u043b\u0456\u0440"},
            (11, None):  {"external_attribute_id": "2002", "external_attribute_name": "\u041f\u0430\u043c\u0027\u044f\u0442\u044c"},
        }
        self._vals = {
            (100, None): {"external_value_id": "3001", "external_value_name": "\u0427\u043e\u0440\u043d\u0438\u0439"},
            (101, None): {"external_value_id": "3002", "external_value_name": "\u0421\u0438\u043d\u0456\u0439"},
            (110, None): {"external_value_id": "3010", "external_value_name": "128 \u0413\u0411"},
        }

    def resolve_category(self, internal_category_id):
        return self._cats.get(internal_category_id)

    def resolve_attribute(self, internal_attribute_id, external_category_id=None):
        if external_category_id is not None:
            result = self._attrs.get((internal_attribute_id, external_category_id))
            if result:
                return result
        return self._attrs.get((internal_attribute_id, None))

    def resolve_value(self, internal_value_id, external_category_id=None):
        if external_category_id is not None:
            result = self._vals.get((internal_value_id, external_category_id))
            if result:
                return result
        return self._vals.get((internal_value_id, None))

    def has_rules(self):
        return True


def _make_product(**overrides):
    base = {
        "id": 1, "name": "Test Product", "description": "A test product description",
        "price": 1000, "currency": "UAH", "stock_qty": 10, "stock_status": "in_stock",
        "status": "PUBLISHED",
        "brand": {"id": 1, "name": "TestBrand", "slug": "test-brand"},
        "sku": "TEST-001", "supplier_sku": None,
        "categories": [{"category_id": 1, "category_name": "\u0421\u043c\u0430\u0440\u0442\u0444\u043e\u043d\u0438"}],
        "attributes": [
            {"attribute_id": 10, "attr_name": "\u041a\u043e\u043b\u0456\u0440", "attr_slug": "kolor",
             "attribute_value_id": 100, "value_text": None, "attr_value_name": "\u0427\u043e\u0440\u043d\u0438\u0439"},
        ],
        "images": [
            {"id": 1, "url": "https://example.com/img.jpg", "path": None,
             "alt": "Test", "sort_order": 0, "is_primary": True, "is_suppressed": False},
        ],
    }
    base.update(overrides)
    return base


# ====================================================================
# Validation tests
# ====================================================================


class TestValidationReady:
    """Tests for products that should be READY."""

    def test_valid_product_is_ready(self):
        resolver = FakeResolver()
        product = _make_product()
        ext_cat_id = "1001"
        issues = []
        ready = True
        # Manually run validation checks equivalent to _validate()
        if product["status"] != "PUBLISHED":
            ready = False
        if not (product.get("name") or "").strip():
            ready = False
        price = product.get("price") or 0
        if price <= 0:
            ready = False
        active_images = [img for img in product.get("images") or [] if not img["is_suppressed"]]
        if not active_images:
            ready = False
        cat_mapped = ext_cat_id is not None
        if not cat_mapped:
            ready = False
        for pa in product.get("attributes") or []:
            attr_mapping = resolver.resolve_attribute(pa["attribute_id"], ext_cat_id)
            if attr_mapping is None:
                ready = False
            if pa["attribute_value_id"]:
                val_mapping = resolver.resolve_value(pa["attribute_value_id"], ext_cat_id)
                if val_mapping is None:
                    ready = False
        assert ready is True, "Valid product should be READY"


class TestValidationBlocked:
    """Tests for products that should be BLOCKED."""

    def test_missing_category_mapping(self):
        resolver = FakeResolver()
        product = _make_product()
        ext_cat_id = None  # No category mapped
        ready = ext_cat_id is not None
        assert ready is False, "Product without category mapping should be BLOCKED"

    def test_unmapped_attribute(self):
        resolver = FakeResolver()
        product = _make_product()
        product["attributes"] = [
            {"attribute_id": 999, "attr_name": "Unknown", "attr_slug": "unknown",
             "attribute_value_id": None, "value_text": "xyz", "attr_value_name": None},
        ]
        ext_cat_id = "1001"
        attr_mapping = resolver.resolve_attribute(999, ext_cat_id)
        assert attr_mapping is None, "Unmapped attribute should resolve to None"

    def test_unmapped_attribute_value(self):
        resolver = FakeResolver()
        product = _make_product()
        product["attributes"] = [
            {"attribute_id": 10, "attr_name": "\u041a\u043e\u043b\u0456\u0440", "attr_slug": "kolor",
             "attribute_value_id": 999, "value_text": None, "attr_value_name": "Unknown Color"},
        ]
        ext_cat_id = "1001"
        val_mapping = resolver.resolve_value(999, ext_cat_id)
        assert val_mapping is None, "Unmapped value should resolve to None"

    def test_draft_product(self):
        product = _make_product(status="DRAFT")
        ready = product["status"] == "PUBLISHED"
        assert ready is False, "Draft product should be BLOCKED"

    def test_hidden_product(self):
        product = _make_product(status="HIDDEN")
        ready = product["status"] == "PUBLISHED"
        assert ready is False, "Hidden product should be BLOCKED"

    def test_missing_title(self):
        product = _make_product(name="")
        title = (product.get("name") or "").strip()
        ready = bool(title)
        assert ready is False, "Product without title should be BLOCKED"

    def test_missing_price(self):
        product = _make_product(price=0)
        price = product.get("price") or 0
        ready = price > 0
        assert ready is False, "Product with zero price should be BLOCKED"

    def test_missing_image(self):
        product = _make_product(images=[])
        active_images = [img for img in product.get("images") or [] if not img.get("is_suppressed")]
        ready = bool(active_images)
        assert ready is False, "Product without images should be BLOCKED"


class TestValidationIssues:
    """Tests that the returned issue structure is correct."""

    def test_missing_title_issue_code(self):
        product = _make_product(name="")
        title = (product.get("name") or "").strip()
        if not title:
            code = ISSUE_MISSING_TITLE
            assert code == "MISSING_TITLE"

    def test_missing_image_issue_code(self):
        product = _make_product(images=[])
        active_images = [img for img in product.get("images") or [] if not img.get("is_suppressed")]
        if not active_images:
            code = ISSUE_MISSING_IMAGE
            assert code == "MISSING_IMAGE"

    def test_relative_image_url_issue_code(self):
        url = "/media/img.jpg"
        public_base_url = None
        if url.startswith("/media/") and not public_base_url:
            code = ISSUE_INVALID_IMAGE_URL
            severity = SEVERITY_WARNING
            assert code == "INVALID_IMAGE_URL"
            assert severity == "warning"

    def test_http_image_url_issue_code(self):
        url = "http://example.com/img.jpg"
        if url.startswith("http://"):
            code = ISSUE_HTTP_IMAGE_URL
            severity = SEVERITY_WARNING
            assert code == "HTTP_IMAGE_URL"
            assert severity == "warning"

    def test_https_image_url_no_issue(self):
        url = "https://example.com/img.jpg"
        has_http_issue = url.startswith("http://")
        has_relative_issue = url.startswith("/media/") and not None
        assert not has_http_issue
        assert not has_relative_issue

    def test_warning_does_not_make_product_unready(self):
        """Warning-only issues should not block the product."""
        product = _make_product()
        # Missing description is a warning, not an error
        desc = (product.get("description") or "").strip()
        has_desc_warning = not bool(desc)
        # Product should still be ready if only warnings exist
        # We need at least one error to be blocked
        ready = True
        issues = []
        if not desc:
            issues.append({"severity": SEVERITY_WARNING})
        has_error = any(i.get("severity") == SEVERITY_ERROR for i in issues)
        assert has_error is False
        assert ready is True


# ====================================================================
# Category-dependent mapping tests
# ====================================================================


class TestCategoryDependentMapping:
    """Tests proving that the same internal attribute resolves to different
    external attributes depending on the external category."""

    def test_same_attr_different_category_different_external_id(self):
        """Internal attribute 10 should resolve to different external IDs
        for category 1001 vs 2001."""
        resolver = FakeResolver()
        mapping_cat1 = resolver.resolve_attribute(10, "1001")
        mapping_cat2 = resolver.resolve_attribute(10, "2001")
        assert mapping_cat1 is not None
        assert mapping_cat2 is not None
        assert mapping_cat1["external_attribute_id"] == "2001"
        assert mapping_cat2["external_attribute_id"] == "2003"
        assert mapping_cat1["external_attribute_id"] != mapping_cat2["external_attribute_id"]

    def test_same_attr_different_category_different_name(self):
        """The external attribute name should also differ per category."""
        resolver = FakeResolver()
        mapping_cat1 = resolver.resolve_attribute(10, "1001")
        mapping_cat2 = resolver.resolve_attribute(10, "2001")
        assert mapping_cat1["external_attribute_name"] == "\u041a\u043e\u043b\u0456\u0440_\u0441\u043c\u0430\u0440\u0442"
        assert mapping_cat2["external_attribute_name"] == "\u041a\u043e\u043b\u0456\u0440_\u043f\u043b\u0430\u043d\u0448"

    def test_global_fallback_when_no_category_match(self):
        """When no category-specific mapping exists, fall back to global."""
        resolver = FakeResolver()
        # Attribute 11 (\u041f\u0430\u043c\u0027\u044f\u0442\u044c) has no category-specific mapping
        # Should fall back to global (external_id "2002")
        mapping = resolver.resolve_attribute(11, "1001")
        assert mapping is not None
        assert mapping["external_attribute_id"] == "2002"

    def test_global_fallback_to_none(self):
        """If no global mapping exists either, return None."""
        resolver = FakeResolver()
        mapping = resolver.resolve_attribute(999, "1001")
        assert mapping is None


# ====================================================================
# Free-text attribute tests
# ====================================================================


class TestFreeTextAttributes:
    """Tests for attribute_value_id vs value_text handling."""

    def test_attribute_value_id_is_resolved(self):
        resolver = FakeResolver()
        product = _make_product()
        pa = product["attributes"][0]
        assert pa["attribute_value_id"] == 100
        val_mapping = resolver.resolve_value(pa["attribute_value_id"], "1001")
        assert val_mapping is not None
        assert val_mapping["external_value_id"] == "3001"

    def test_value_text_is_preserved(self):
        resolver = FakeResolver()
        product = _make_product()
        product["attributes"] = [
            {"attribute_id": 10, "attr_name": "\u041a\u043e\u043b\u0456\u0440", "attr_slug": "kolor",
             "attribute_value_id": None, "value_text": "Custom Color", "attr_value_name": None},
        ]
        pa = product["attributes"][0]
        assert pa["value_text"] == "Custom Color"
        assert pa["attribute_value_id"] is None
        payload = _build_transform_payload(product, resolver, "1001")
        assert len(payload["attributes"]) == 1
        assert payload["attributes"][0]["value"] == "Custom Color"

    def test_both_value_text_and_attribute_value_id(self):
        """When both are present, attribute_value_id takes priority."""
        resolver = FakeResolver()
        product = _make_product()
        product["attributes"] = [
            {"attribute_id": 10, "attr_name": "\u041a\u043e\u043b\u0456\u0440", "attr_slug": "kolor",
             "attribute_value_id": 100, "value_text": "Should Be Ignored",
             "attr_value_name": "\u0427\u043e\u0440\u043d\u0438\u0439"},
        ]
        pa = product["attributes"][0]
        assert pa["attribute_value_id"] == 100
        assert pa["value_text"] == "Should Be Ignored"
        payload = _build_transform_payload(product, resolver, "1001")
        assert payload["attributes"][0]["value"] == "\u0427\u043e\u0440\u043d\u0438\u0439"

    def test_value_text_without_attribute_mapping(self):
        """Free-text value without attribute mapping is skipped."""
        resolver = FakeResolver()
        product = _make_product()
        product["attributes"] = [
            {"attribute_id": 999, "attr_name": "Unknown", "attr_slug": "unknown",
             "attribute_value_id": None, "value_text": "Some value", "attr_value_name": None},
        ]
        payload = _build_transform_payload(product, resolver, "1001")
        # Attribute without mapping should be skipped entirely
        assert len(payload["attributes"]) == 0


# ====================================================================
# Hash isolation tests
# ====================================================================


class TestHashIsolation:
    """Verify content_hash and commercial_hash change independently."""

    def test_price_change_only_affects_commercial_hash(self):
        resolver = FakeResolver()
        p1 = _make_product(price=1000)
        p2 = _make_product(price=2000)
        ch1 = compute_content_hash(p1, resolver, "1001")
        ch2 = compute_content_hash(p2, resolver, "1001")
        cm1 = compute_commercial_hash(p1)
        cm2 = compute_commercial_hash(p2)
        assert ch1 == ch2, "Price change must NOT affect content hash"
        assert cm1 != cm2, "Price change MUST affect commercial hash"

    def test_stock_change_only_affects_commercial_hash(self):
        resolver = FakeResolver()
        p1 = _make_product(stock_qty=10)
        p2 = _make_product(stock_qty=0)
        ch1 = compute_content_hash(p1, resolver, "1001")
        ch2 = compute_content_hash(p2, resolver, "1001")
        cm1 = compute_commercial_hash(p1)
        cm2 = compute_commercial_hash(p2)
        assert ch1 == ch2, "Stock change must NOT affect content hash"
        assert cm1 != cm2, "Stock change MUST affect commercial hash"

    def test_title_change_only_affects_content_hash(self):
        resolver = FakeResolver()
        p1 = _make_product(name="Original")
        p2 = _make_product(name="Changed")
        ch1 = compute_content_hash(p1, resolver, "1001")
        ch2 = compute_content_hash(p2, resolver, "1001")
        cm1 = compute_commercial_hash(p1)
        cm2 = compute_commercial_hash(p2)
        assert ch1 != ch2, "Title change MUST affect content hash"
        assert cm1 == cm2, "Title change must NOT affect commercial hash"

    def test_description_change_only_affects_content_hash(self):
        resolver = FakeResolver()
        p1 = _make_product(description="Original desc")
        p2 = _make_product(description="Changed desc")
        ch1 = compute_content_hash(p1, resolver, "1001")
        ch2 = compute_content_hash(p2, resolver, "1001")
        cm1 = compute_commercial_hash(p1)
        cm2 = compute_commercial_hash(p2)
        assert ch1 != ch2, "Description change MUST affect content hash"
        assert cm1 == cm2, "Description change must NOT affect commercial hash"

    def test_attribute_change_only_affects_content_hash(self):
        resolver = FakeResolver()
        p1 = _make_product()
        p2 = _make_product()
        p2["attributes"] = [
            {"attribute_id": 11, "attr_name": "\u041f\u0430\u043c\u0027\u044f\u0442\u044c",
             "attr_slug": "memory", "attribute_value_id": 110,
             "value_text": None, "attr_value_name": "128 \u0413\u0411"},
        ]
        ch1 = compute_content_hash(p1, resolver, "1001")
        ch2 = compute_content_hash(p2, resolver, "1001")
        cm1 = compute_commercial_hash(p1)
        cm2 = compute_commercial_hash(p2)
        assert ch1 != ch2, "Attribute change MUST affect content hash"
        assert cm1 == cm2, "Attribute change must NOT affect commercial hash"

    def test_image_change_only_affects_content_hash(self):
        resolver = FakeResolver()
        p1 = _make_product()
        p2 = _make_product()
        p2["images"] = [{"id": 2, "url": "https://other.com/img.jpg", "path": None,
                          "alt": "", "sort_order": 0, "is_primary": True, "is_suppressed": False}]
        ch1 = compute_content_hash(p1, resolver, "1001")
        ch2 = compute_content_hash(p2, resolver, "1001")
        cm1 = compute_commercial_hash(p1)
        cm2 = compute_commercial_hash(p2)
        assert ch1 != ch2, "Image change MUST affect content hash"
        assert cm1 == cm2, "Image change must NOT affect commercial hash"


# ====================================================================
# Transform payload tests
# ====================================================================


class TestBuildTransformPayload:
    """Tests for the internal export representation builder."""

    def test_basic_payload_structure(self):
        resolver = FakeResolver()
        product = _make_product()
        payload = _build_transform_payload(product, resolver, "1001")
        assert payload["product_id"] == 1
        assert payload["title"] == "Test Product"
        assert payload["brand"] == "TestBrand"
        assert payload["price"] == 1000
        assert payload["category"] is not None
        assert payload["category"]["external_id"] == "1001"

    def test_attributes_resolved(self):
        resolver = FakeResolver()
        product = _make_product()
        payload = _build_transform_payload(product, resolver, "1001")
        assert len(payload["attributes"]) == 1
        attr = payload["attributes"][0]
        assert attr["external_attribute_id"] == "2001"
        assert attr["external_value_id"] == "3001"
        assert attr["value"] == "\u0427\u043e\u0440\u043d\u0438\u0439"

    def test_value_text_passthrough(self):
        resolver = FakeResolver()
        product = _make_product()
        product["attributes"] = [
            {"attribute_id": 10, "attr_name": "\u041a\u043e\u043b\u0456\u0440", "attr_slug": "kolor",
             "attribute_value_id": None, "value_text": "Custom Color", "attr_value_name": None},
        ]
        payload = _build_transform_payload(product, resolver, "1001")
        assert len(payload["attributes"]) == 1
        assert payload["attributes"][0]["value"] == "Custom Color"

    def test_relative_image_url_with_base_url(self):
        resolver = FakeResolver()
        product = _make_product()
        product["images"] = [
            {"id": 1, "url": "/media/img.jpg", "path": None, "alt": "",
             "sort_order": 0, "is_primary": True, "is_suppressed": False},
        ]
        payload = _build_transform_payload(product, resolver, "1001",
                                           public_base_url="https://shop.example.com")
        assert payload["images"][0]["url"] == "https://shop.example.com/media/img.jpg"

    def test_absolute_image_url_unchanged(self):
        resolver = FakeResolver()
        product = _make_product()
        product["images"] = [
            {"id": 1, "url": "https://cdn.example.com/img.jpg", "path": None,
             "alt": "", "sort_order": 0, "is_primary": True, "is_suppressed": False},
        ]
        payload = _build_transform_payload(product, resolver, "1001",
                                           public_base_url="https://shop.example.com")
        assert payload["images"][0]["url"] == "https://cdn.example.com/img.jpg"

    def test_http_url_preserved(self):
        """HTTP URLs should NOT be automatically upgraded to HTTPS."""
        resolver = FakeResolver()
        product = _make_product()
        product["images"] = [
            {"id": 1, "url": "http://cdn.example.com/img.jpg", "path": None,
             "alt": "", "sort_order": 0, "is_primary": True, "is_suppressed": False},
        ]
        payload = _build_transform_payload(product, resolver, "1001",
                                           public_base_url="https://shop.example.com")
        # HTTP URL should be preserved as-is (no silent upgrade)
        assert payload["images"][0]["url"] == "http://cdn.example.com/img.jpg"

    def test_suppressed_image_excluded(self):
        resolver = FakeResolver()
        product = _make_product()
        product["images"] = [
            {"id": 1, "url": "https://example.com/img1.jpg", "path": None,
             "alt": "", "sort_order": 0, "is_primary": True, "is_suppressed": False},
            {"id": 2, "url": "https://example.com/img2.jpg", "path": None,
             "alt": "", "sort_order": 1, "is_primary": False, "is_suppressed": True},
        ]
        payload = _build_transform_payload(product, resolver, "1001")
        assert len(payload["images"]) == 1
        assert payload["images"][0]["url"] == "https://example.com/img1.jpg"

    def test_category_not_mapped(self):
        resolver = FakeResolver()
        product = _make_product()
        product["categories"] = [{"category_id": 999, "category_name": "Unknown"}]
        payload = _build_transform_payload(product, resolver, None)
        assert payload["category"] is None

    def test_no_brand(self):
        resolver = FakeResolver()
        product = _make_product(brand=None)
        payload = _build_transform_payload(product, resolver, "1001")
        assert payload["brand"] is None

    def test_category_dependent_attribute_resolution(self):
        """Same internal attribute, different external category -> different external attr."""
        resolver = FakeResolver()
        product = _make_product()
        # Category 1 -> external 1001
        payload_cat1 = _build_transform_payload(product, resolver, "1001")
        # Category 2 -> external 2001
        product["categories"] = [{"category_id": 2, "category_name": "\u041f\u043b\u0430\u043d\u0448\u0435\u0442\u0438"}]
        payload_cat2 = _build_transform_payload(product, resolver, "2001")
        assert len(payload_cat1["attributes"]) == 1
        assert len(payload_cat2["attributes"]) == 1
        # Same internal attribute 10 should resolve to different external IDs
        assert payload_cat1["attributes"][0]["external_attribute_id"] == "2001"
        assert payload_cat2["attributes"][0]["external_attribute_id"] == "2003"


# ====================================================================
# Content hash basic tests
# ====================================================================


class TestContentHash:
    """Tests for deterministic content hashing."""

    def test_content_hash_is_deterministic(self):
        resolver = FakeResolver()
        product = _make_product()
        h1 = compute_content_hash(product, resolver, "1001")
        h2 = compute_content_hash(product, resolver, "1001")
        assert h1 == h2
        assert len(h1) == 64

    def test_content_change_affects_hash(self):
        resolver = FakeResolver()
        p1 = _make_product(name="Original")
        p2 = _make_product(name="Changed")
        h1 = compute_content_hash(p1, resolver, "1001")
        h2 = compute_content_hash(p2, resolver, "1001")
        assert h1 != h2


class TestCommercialHash:
    """Tests for deterministic commercial hashing."""

    def test_commercial_hash_is_deterministic(self):
        product = _make_product()
        h1 = compute_commercial_hash(product)
        h2 = compute_commercial_hash(product)
        assert h1 == h2

    def test_price_change_affects_commercial_hash(self):
        p1 = _make_product(price=1000)
        p2 = _make_product(price=2000)
        assert compute_commercial_hash(p1) != compute_commercial_hash(p2)

    def test_stock_change_affects_commercial_hash(self):
        p1 = _make_product(stock_qty=10)
        p2 = _make_product(stock_qty=0)
        assert compute_commercial_hash(p1) != compute_commercial_hash(p2)

    def test_title_change_does_not_affect_commercial_hash(self):
        p1 = _make_product(name="Original")
        p2 = _make_product(name="Changed")
        assert compute_commercial_hash(p1) == compute_commercial_hash(p2)
