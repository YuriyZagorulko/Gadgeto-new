"""Regression tests for the duplicate external parameter guard.

Two+ internal attributes resolving to the same external characteristic
produce duplicate ``id`` entries in the outgoing Rozetka ``params`` list,
which the Rozetka API rejects ("Дублікат параметрів").  ``_validate`` must
block such products with ``DUPLICATE_EXTERNAL_PARAM`` before the API
round-trip instead of failing at push time.

Also covers the ``_would_produce_empty_params`` parity rule: the EMPTY_PARAMS
check must mirror ``rozetka.payload._build_params`` exactly — characteristics
outside the category taxonomy (e.g. phantom global fallbacks) are skipped by
the builder, so they cannot rescue a product from EMPTY_PARAMS.
"""

import pytest

from app.channels import validation as validation_module
from app.channels.validation import (
    ISSUE_DUPLICATE_EXTERNAL_PARAM,
    ISSUE_EMPTY_PARAMS,
    SEVERITY_ERROR,
    _validate,
    _would_produce_empty_params,
)


class TestDuplicateExternalParam:
    """Two internal attrs -> one external characteristic must be blocked."""

    def test_duplicate_text_attrs_blocked(self, fake_resolver):
        # 171 and 272 both resolve to 20927 (TextInput — both would emit).
        fake_resolver["attr_map"] = {171: "20927", 272: "20927"}
        result = _run([_attr(171, value_text="iPhone 15"),
                       _attr(272, value_text="iPhone 15 Pro")],
                      [_TAX_TEXT_A, _TAX_TEXT_B])

        assert not result["ready"]
        assert ISSUE_DUPLICATE_EXTERNAL_PARAM in _error_codes(result)
        dup = _issue(result, ISSUE_DUPLICATE_EXTERNAL_PARAM)
        assert dup["details"]["external_attribute_id"] == "20927"
        assert dup["details"]["internal_attribute_ids"] == [171, 272]
        # EMPTY_PARAMS must NOT fire — the duplicated params are non-empty.
        assert ISSUE_EMPTY_PARAMS not in _error_codes(result)

    def test_same_internal_attribute_twice_blocked(self, fake_resolver):
        # The same internal attribute listed twice in the product (multi-value
        # data) also produces duplicate params and must be blocked.
        fake_resolver["attr_map"] = {168: "20927"}
        result = _run([_attr(168, value_id=900, name="Колір"),
                       _attr(168, value_id=901, name="Колір")],
                      [_TAX_TEXT_A])

        assert not result["ready"]
        assert ISSUE_DUPLICATE_EXTERNAL_PARAM in _error_codes(result)
        assert _issue(
            result, ISSUE_DUPLICATE_EXTERNAL_PARAM
        )["details"]["internal_attribute_ids"] == [168, 168]

    def test_distinct_external_attrs_not_flagged(self, fake_resolver):
        fake_resolver["attr_map"] = {171: "20927", 272: "23341"}
        result = _run([_attr(171, value_text="iPhone 15"),
                       _attr(272, value_text="Україна")],
                      [_TAX_TEXT_A, _TAX_TEXT_B])

        assert ISSUE_DUPLICATE_EXTERNAL_PARAM not in _error_codes(result)

    def test_single_attribute_not_flagged(self, fake_resolver):
        fake_resolver["attr_map"] = {171: "20927"}
        result = _run([_attr(171, value_text="iPhone 15")], [_TAX_TEXT_A])

        assert ISSUE_DUPLICATE_EXTERNAL_PARAM not in _error_codes(result)
        assert result["ready"] is True


class TestDuplicateNotConfusedWithSkipped:
    """Contributions the payload builder skips must not raise false positives."""

    def test_duplicate_target_not_in_taxonomy_no_duplicate(self, fake_resolver):
        # Both attrs map to 999999 which is NOT in the category taxonomy —
        # the builder skips both, so no duplicates are sent (EMPTY_PARAMS
        # fires instead).
        fake_resolver["attr_map"] = {171: "999999", 272: "999999"}
        result = _run([_attr(171, value_text="a"), _attr(272, value_text="b")],
                      [_TAX_TEXT_A])

        assert ISSUE_DUPLICATE_EXTERNAL_PARAM not in _error_codes(result)
        assert ISSUE_EMPTY_PARAMS in _error_codes(result)

    def test_duplicate_select_without_values_no_duplicate(self, fake_resolver):
        # Both attrs map to the ComboBox 21590 but have no value mappings —
        # the builder omits both, so no duplicates are sent (EMPTY_PARAMS
        # fires instead).
        fake_resolver["attr_map"] = {171: "21590", 272: "21590"}
        result = _run([_attr(171, value_id=900), _attr(272, value_id=901)],
                      [_TAX_COMBO])

        assert ISSUE_DUPLICATE_EXTERNAL_PARAM not in _error_codes(result)
        assert ISSUE_EMPTY_PARAMS in _error_codes(result)

    def test_duplicate_select_with_values_blocked(self, fake_resolver):
        # Both attrs map to the ComboBox 21590 and both value mappings
        # resolve — real duplicates, must be blocked.
        fake_resolver["attr_map"] = {171: "21590", 272: "21590"}
        fake_resolver["value_map"] = {
            900: {"external_value_id": "3001"},
            901: {"external_value_id": "3002"},
        }
        result = _run([_attr(171, value_id=900), _attr(272, value_id=901)],
                      [_TAX_COMBO])

        assert ISSUE_DUPLICATE_EXTERNAL_PARAM in _error_codes(result)


class TestEmptyParamsParity:
    """EMPTY_PARAMS must mirror _build_params (taxonomy-skips included)."""

    def test_phantom_mapping_produces_empty_params(self, fake_resolver):
        # Regression: a mapped attribute whose external characteristic is NOT
        # in the taxonomy is skipped by the payload builder.  The old
        # EMPTY_PARAMS check treated it as contributing and let the product
        # through to an API rejection; now it must be blocked up front.
        fake_resolver["attr_map"] = {171: "999999"}
        result = _run([_attr(171, value_text="7 кг")], [_TAX_TEXT_A])

        assert not result["ready"]
        assert ISSUE_EMPTY_PARAMS in _error_codes(result)
        empty = _issue(result, ISSUE_EMPTY_PARAMS)
        skipped = empty["details"]["skipped_attributes"]
        assert skipped == [{"external_attribute_id": "999999",
                            "internal_attribute_ids": [171],
                            "mapping_scope": "global",
                            "reason": "not_in_category_taxonomy"}]

    def test_phantom_mapping_would_produce_empty_params(self, fake_resolver):
        fake_resolver["attr_map"] = {171: "999999"}
        product = {"attributes": [_attr(171, value_text="7 кг")]}
        assert _would_produce_empty_params(
            FakeCursor(product["attributes"], [_TAX_TEXT_A]),
            1, "80073", FakeResolver(), product) is True

    def test_text_attr_in_taxonomy_produces_params(self, fake_resolver):
        fake_resolver["attr_map"] = {171: "20927"}
        result = _run([_attr(171, value_text="7 кг")], [_TAX_TEXT_A])

        assert ISSUE_EMPTY_PARAMS not in _error_codes(result)
        assert result["ready"] is True


class FakeCursor:
    """Answers the exact SQL sequence ``_validate`` issues (RealDictCursor)."""

    def __init__(self, product_attrs, all_attr_rows):
        self._product_attrs = product_attrs
        self._all_attr_rows = all_attr_rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def fetchone(self):
        sql, _params = self.executed[-1]
        if "FROM products WHERE" in sql:
            return {"id": 1, "name": "Тестовий товар",
                    "supplier_sku": "T-1", "status": "PUBLISHED",
                    "description": "Опис", "price": 100.0,
                    "stock_qty": 5, "stock_status": "in_stock",
                    "brand_id": 1}
        if "FROM brands" in sql:
            return {"id": 1, "name": "TestBrand", "slug": "testbrand"}
        if "FROM channels WHERE" in sql:
            return {"id": 1}
        if "parent_external_id=%s" in sql:
            return {"children": 0}
        if "channel_external_categories" in sql and "external_id=%s" in sql:
            return {"name": "Аксесуари"}
        if "count(*) AS attrs" in sql:
            return {"attrs": len(self._all_attr_rows)}
        raise AssertionError(f"Unexpected fetchone: {sql}")

    def fetchall(self):
        sql, _params = self.executed[-1]
        if "FROM product_categories" in sql:
            return [{"category_id": 1, "category_name": "Тестова категорія"}]
        if "FROM product_attributes pa" in sql:
            return list(self._product_attrs)
        if "FROM product_images" in sql:
            return [{"id": 1, "url": "https://example.com/img.jpg",
                     "is_suppressed": False}]
        if "FROM channel_external_attributes" in sql:
            return list(self._all_attr_rows)
        raise AssertionError(f"Unexpected fetchall: {sql}")


class FakeResolver:
    """Stands in for ChannelMappingResolver inside _validate."""

    cfg: dict = {}

    def __init__(self, channel_id=None, channel_code=None):
        self.channel_id = channel_id
        self.channel_code = channel_code

    def resolve_category(self, category_id):
        if category_id == 1:
            return {"external_category_id": "80073",
                    "external_category_name": "Аксесуари"}
        return None

    def resolve_attribute(self, attribute_id, ext_cat_id):
        ext = self.cfg.get("attr_map", {}).get(attribute_id)
        if ext is None:
            return None
        return {"external_attribute_id": ext,
                "external_attribute_name": self.cfg.get(
                    "ext_names", {}).get(ext, "Тестова характеристика")}

    def resolve_value(self, attribute_value_id, ext_cat_id):
        return self.cfg.get("value_map", {}).get(attribute_value_id)

    def resolve_value_by_text(self, attribute_id, value_text, ext_cat_id):
        return self.cfg.get("value_by_text", {}).get((attribute_id, value_text))


@pytest.fixture
def fake_resolver(monkeypatch):
    FakeResolver.cfg = {}
    monkeypatch.setattr(validation_module, "ChannelMappingResolver", FakeResolver)
    monkeypatch.setattr(
        validation_module, "_get_required_attributes",
        lambda cur_, channel_id, ext_cat_id: [])
    return FakeResolver.cfg


def _attr(attribute_id, value_id=None, value_text=None, name="Тестовий атрибут"):
    return {"attribute_id": attribute_id, "attr_name": name,
            "attribute_value_id": value_id, "value_text": value_text}


def _run(product_attrs, all_attr_rows):
    cur = FakeCursor(product_attrs, all_attr_rows)
    return _validate(cur, 1, "rozetka")


def _error_codes(result):
    return {i["code"] for i in result["issues"] if i["severity"] == SEVERITY_ERROR}


def _issue(result, code):
    return next(i for i in result["issues"] if i["code"] == code)


# Taxonomy rows ---------------------------------------------------------------
_TAX_TEXT_A = {"external_id": "20927", "name": "Сумісна модель",
               "param_type": "TextInput"}
_TAX_TEXT_B = {"external_id": "23341", "name": "Країна виробництва",
               "param_type": "TextInput"}
_TAX_COMBO = {"external_id": "21590", "name": "Тип сумісності",
              "param_type": "ComboBox"}
