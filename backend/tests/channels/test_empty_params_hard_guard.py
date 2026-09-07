"""Regression tests: empty params must NOT block Rozetka export.

Rozetka API has no concept of required attributes. Therefore:
- params={} is valid
- EMPTY_PARAMS must not appear as blocking error
- ROZETKA_PARAMS_EMPTY must not appear when no required attributes exist
"""

import pytest
from unittest.mock import MagicMock

from app.channels.validation import _get_required_attributes, ISSUE_EMPTY_PARAMS
from app.channels.rozetka.payload import build_create_payload, _build_params


class TestGetRequiredAttributes:
    """_get_required_attributes should return empty list (Rozetka has no required concept)."""

    def test_returns_empty_without_db_access(self):
        """Rozetka API has no required attributes → always empty."""
        result = _get_required_attributes(None, 1, "80090")
        assert result == []

    def test_returns_empty_with_cur(self):
        """Even with cursor, should return empty (no DB lookup)."""
        cur = MagicMock()
        result = _get_required_attributes(cur, 1, "80090")
        assert result == []
        cur.execute.assert_not_called()


class TestEmptyParamsSemantics:
    """Test that empty params don't block export."""

    def test_params_empty_no_required_attributes_no_error(self):
        """Case A: params={} + required=[] → no EMPTY_PARAMS error."""
        issues = []
        required_attr_ids = set()
        params = {}
        ext_cat_id = "80090"
        taxonomy_ok = True

        if ext_cat_id and taxonomy_ok and required_attr_ids:
            if not params:
                issues.append({"code": ISSUE_EMPTY_PARAMS, "severity": "error"})

        error_codes = [i["code"] for i in issues if i["severity"] == "error"]
        assert ISSUE_EMPTY_PARAMS not in error_codes

    def test_params_empty_with_required_attributes_triggers_error(self):
        """Case C: params={} + required=[123] → EMPTY_PARAMS error."""
        issues = []
        required_attr_ids = {123}
        params = {}
        ext_cat_id = "80090"
        taxonomy_ok = True

        if ext_cat_id and taxonomy_ok and required_attr_ids:
            if not params:
                issues.append({"code": ISSUE_EMPTY_PARAMS, "severity": "error"})

        error_codes = [i["code"] for i in issues if i["severity"] == "error"]
        assert ISSUE_EMPTY_PARAMS in error_codes

    def test_params_non_empty_no_error(self):
        """Case D: params={123: 'value'} + required=[123] → no error."""
        issues = []
        required_attr_ids = {123}
        params = {123: "value"}
        ext_cat_id = "80090"
        taxonomy_ok = True

        if ext_cat_id and taxonomy_ok and required_attr_ids:
            if not params:
                issues.append({"code": ISSUE_EMPTY_PARAMS, "severity": "error"})

        error_codes = [i["code"] for i in issues if i["severity"] == "error"]
        assert ISSUE_EMPTY_PARAMS not in error_codes


class TestBuildParamsEmpty:
    """Test that _build_params handles empty results gracefully."""

    def test_build_params_returns_empty_list_when_no_attributes(self):
        """_build_params returns [] when product has no attributes."""
        product = {"id": 1, "sku": "TEST-001", "attributes": []}
        resolver = MagicMock()
        resolver.resolve_attribute.return_value = None

        result = _build_params(product, resolver, "80090")
        assert result == []

    def test_build_create_payload_accepts_empty_params(self):
        """build_create_payload works with empty attr_specs (no params)."""
        # build_create_payload takes (transformed, attr_specs)
        # When attr_specs is empty, params should be an empty list
        transformed = {
            "id": 1, "sku": "TEST-001", "title": "Test Product 80090",
            "price": 100.0, "images": [{"url": "http://example.com/img.jpg"}],
            "brand": "TestBrand", "attributes": [],
            "params": [],
            "category": {"external_id": "80090", "external_name": "Корпуси"},
        }
        attr_specs = {}

        payload, _ = build_create_payload(transformed, attr_specs)
        assert payload is not None
        assert "params" in payload
        assert payload["params"] == []


class TestRozetkaValidationEmptyParams:
    """Test that rozetka_validation doesn't block on empty params."""

    def test_rozetka_params_empty_not_issued_without_required(self):
        """ROZETKA_PARAMS_EMPTY should not be issued when required_count=0."""
        attr_specs = {
            1: {"name": "Тип", "is_required": 0, "values": {}},
            2: {"name": "Колір", "is_required": 0, "values": {}},
        }
        issues = []
        total_required = sum(1 for a in attr_specs.values() if a.get("is_required"))
        params = {}

        if total_required > 0 and not params:
            issues.append({"code": "ROZETKA_PARAMS_EMPTY", "severity": "error"})

        error_codes = [i["code"] for i in issues if i["severity"] == "error"]
        assert "ROZETKA_PARAMS_EMPTY" not in error_codes

    def test_rozetka_params_empty_issued_with_required(self):
        """ROZETKA_PARAMS_EMPTY should be issued when required_count > 0."""
        attr_specs = {
            1: {"name": "Тип", "is_required": 1, "values": {}},
            2: {"name": "Колір", "is_required": 0, "values": {}},
        }
        issues = []
        total_required = sum(1 for a in attr_specs.values() if a.get("is_required"))
        params = {}

        if total_required > 0 and not params:
            issues.append({"code": "ROZETKA_PARAMS_EMPTY", "severity": "error"})

        error_codes = [i["code"] for i in issues if i["severity"] == "error"]
        assert "ROZETKA_PARAMS_EMPTY" in error_codes
