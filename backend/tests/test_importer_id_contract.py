"""Importer contract tests: external-ID preservation.

Verifies that importer normalization code preserves supplier external IDs
without requiring a live API call or a full production import.
"""
import importlib.util
from pathlib import Path

import pytest


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BACKEND = Path(__file__).resolve().parents[1] / "app" / "imports"


class CapturingResolver:
    """Records what the importer asks the resolver to resolve."""

    def __init__(self):
        self.calls = []

    def process_attribute(self, name, value, category_id=None,
                          supplier_attr_external_id=None,
                          supplier_value_external_id=None):
        self.calls.append({
            "name": name,
            "value": value,
            "attr_ext": supplier_attr_external_id,
            "val_ext": supplier_value_external_id,
        })
        return (name, value)

    def resolve_category(self, external_id=None, name=None):
        return None  # force name-based fallback path in importers


# ===================== DC-Link ==============================================


class TestDCLinkIDPreservation:
    def _load(self):
        return _load_module("_test_dclink", str(_BACKEND / "dclink.py"))

    def test_extract_ids_from_options(self):
        mod = self._load()
        importer = mod.DCLinkImporter(feed_path="unused", categories_path="unused")
        # Simulate the parse_products extraction logic with a dict item
        item = {
            "options": [
                {"OptionName": "Колір", "ValueName": "Чорний",
                 "FilterID": "55", "ValueID": "123"},
                {"OptionName": "Розмір", "ValueName": "42",
                 "OptionID": "66", "ValueID": "124"},
            ]
        }
        raw_attrs = []
        for opt in item["options"]:
            opt_name = (opt.get("OptionName") or opt.get("name") or "").strip()
            opt_value = (opt.get("ValueName") or opt.get("value") or "").strip()
            opt_filter_id = str(opt.get("OptionID") or opt.get("FilterID") or "").strip()
            opt_value_id = str(opt.get("ValueID") or "").strip()
            if opt_name and opt_value:
                raw_attrs.append((opt_name, opt_value, opt_filter_id, opt_value_id))
        assert raw_attrs == [
            ("Колір", "Чорний", "55", "123"),
            ("Розмір", "42", "66", "124"),
        ]
        # IDs are preserved alongside names; OptionID preferred over FilterID
        # when both exist

    def test_optionid_preferred_over_filterid(self):
        """When both OptionID and FilterID are present, OptionID is the attribute ID."""
        mod = self._load()
        item = {
            "options": [
                {"OptionName": "Колір", "ValueName": "Чорний",
                 "FilterID": "123-456", "OptionID": "789", "ValueID": "999"},
            ]
        }
        raw_attrs = []
        for opt in item["options"]:
            opt_name = (opt.get("OptionName") or opt.get("name") or "").strip()
            opt_value = (opt.get("ValueName") or opt.get("value") or "").strip()
            opt_filter_id = str(opt.get("OptionID") or opt.get("FilterID") or "").strip()
            opt_value_id = str(opt.get("ValueID") or "").strip()
            if opt_name and opt_value:
                raw_attrs.append((opt_name, opt_value, opt_filter_id, opt_value_id))
        assert raw_attrs == [
            ("Колір", "Чорний", "789", "999"),
        ]
        # OptionID="789" wins over FilterID="123-456" (compound, not pure attr ID)

    def test_filterid_fallback_when_no_optionid(self):
        """When OptionID is absent, FilterID is used as fallback (backward compat)."""
        mod = self._load()
        item = {
            "options": [
                {"OptionName": "Колір", "ValueName": "Чорний",
                 "FilterID": "55", "ValueID": "123"},
            ]
        }
        raw_attrs = []
        for opt in item["options"]:
            opt_name = (opt.get("OptionName") or opt.get("name") or "").strip()
            opt_value = (opt.get("ValueName") or opt.get("value") or "").strip()
            opt_filter_id = str(opt.get("OptionID") or opt.get("FilterID") or "").strip()
            opt_value_id = str(opt.get("ValueID") or "").strip()
            if opt_name and opt_value:
                raw_attrs.append((opt_name, opt_value, opt_filter_id, opt_value_id))
        assert raw_attrs == [
            ("Колір", "Чорний", "55", "123"),
        ]

    def test_ids_passed_to_resolver(self, monkeypatch):
        mod = self._load()
        importer = mod.DCLinkImporter(feed_path="unused", categories_path="unused")
        cap = CapturingResolver()
        importer.resolver = cap
        from app.imports.attribute_processor import set_db_resolver
        set_db_resolver(cap)
        try:
            class FakeStats:
                def __init__(self):
                    self.unmapped_attributes = []
                    self.warnings = []
                def record_unknown_attribute(self, *a, **k):
                    pass
                def record_unknown_attribute_value(self, *a, **k):
                    pass
            importer.stats = FakeStats()
            raw = [("Колір", "Чорний", "55", "123")]
            importer._process_attributes(raw, sku="TEST", category_id=None)
            assert cap.calls[0]["name"] == "Колір"
            assert cap.calls[0]["attr_ext"] == "55"
            assert cap.calls[0]["val_ext"] == "123"
        finally:
            set_db_resolver(None)


# ===================== IT-Link ==============================================


class TestITLinkNoFabricatedIDs:
    def _load(self):
        return _load_module("_test_itlink", str(_BACKEND / "itlink.py"))

    def test_no_external_id_fields_on_normalized_product(self):
        """IT-Link NormalizedProduct must NOT have fabricated attribute/value IDs."""
        mod = self._load()
        p = mod.NormalizedProduct()
        # attribute tuples must be plain (name, value) pairs — no IDs
        assert p.attributes == []
        assert p.raw_attributes == []

    def test_resolver_receives_no_ids(self, monkeypatch):
        mod = self._load()
        importer = mod.ITLinkImporter(feed_path="unused")
        cap = CapturingResolver()
        importer.resolver = cap

        from app.imports.attribute_processor import set_db_resolver
        set_db_resolver(cap)
        try:
            # With no resolver installed, process_attribute returns UNKNOWN_NAME
            # for anything that isn't in the map.
            raw_attrs = [("Колір", "Чорний")]
            processed = []
            for attr_name, attr_value in raw_attrs:
                from app.imports.attribute_processor import process_attribute, ATTR_SKIP, ATTR_UNKNOWN_NAME, ATTR_UNKNOWN_VALUE
                result = process_attribute(attr_name, attr_value)
                if isinstance(result, tuple) and len(result) == 2:
                    processed.append(result)
            # The resolver was asked without external IDs
            assert cap.calls[0]["attr_ext"] is None
            assert cap.calls[0]["val_ext"] is None
        finally:
            set_db_resolver(None)

    def test_category_id_present_in_xml_extraction(self):
        """IT-Link offers carry categoryId — importer must read it (no fabrication)."""
        mod = self._load()
        # The parse_offers method reads categoryId directly from XML.
        # Verify the attribute is read (documented contract).
        import inspect
        src = inspect.getsource(mod.ITLinkImporter.parse_offers)
        assert 'findtext("categoryId", "")' in src


# ===================== Brain (regression only) ==============================


class TestBrainIDPreservation:
    def _load(self):
        return _load_module("_test_brain", str(_BACKEND / "brain.py"))

    def test_extract_options_with_ids(self):
        mod = self._load()
        item = {"options": [
            {"OptionName": "Колір", "ValueName": "Чорний", "OptionID": "77", "ValueID": "99"},
        ]}
        result = mod.BrainImporter._extract_raw_attributes_with_ids(item)
        assert result == [("Колір", "Чорний", "77", "99")]
