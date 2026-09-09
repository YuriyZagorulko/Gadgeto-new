"""Controlled smoke test: supplier feed -> dict sync -> run() reuse.

Uses a mocked DC-Link feed / IT-Link XML (no API call) to exercise
sync_dictionaries() pipeline with a recording SupplierDictSync stub.

Does NOT touch the production database.
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "app" / "imports"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RecordingDictSync:
    """Stand-in for SupplierDictSync that records sync calls."""

    def __init__(self, supplier_code):
        self.supplier_code = supplier_code
        self.categories = []
        self.attributes = []
        self.values = []
        self.next_id = 1000

    def sync_category(self, external_id, name):
        self.categories.append((external_id, name))
        self.next_id += 1
        return self.next_id

    def sync_attribute(self, external_id, name):
        self.attributes.append((external_id, name))
        self.next_id += 1
        return self.next_id

    def sync_value(self, supplier_attribute_id, external_id, value):
        self.values.append((supplier_attribute_id, external_id, value))
        self.next_id += 1
        return self.next_id


@pytest.fixture
def stub_dict_sync(monkeypatch):
    """Install a recording SupplierDictSync into sys.modules."""
    recorder = {"instance": None}
    fake = types.ModuleType("fake_supplier_dict_sync")
    def _factory(code):
        inst = RecordingDictSync(code)
        recorder["instance"] = inst
        return inst
    fake.SupplierDictSync = _factory
    monkeypatch.setitem(sys.modules, "app.imports.supplier_dict_sync", fake)
    monkeypatch.setitem(sys.modules, "supplier_dict_sync", fake)
    return recorder


@pytest.fixture
def dclink_module():
    return _load_module("_smoke_dcl", str(_BACKEND / "dclink.py"))


@pytest.fixture
def itlink_module():
    return _load_module("_smoke_itl", str(_BACKEND / "itlink.py"))


def test_dclink_sync_pipeline(dclink_module, monkeypatch, stub_dict_sync):
    """DC-Link: feed -> sync_dictionaries() records categories/attrs/values."""
    importer = dclink_module.DCLinkImporter(feed_path="unused", categories_path="unused")

    feed = [{"name": "Товар", "options": [
        {"OptionName": "Колір", "ValueName": "Чорний", "FilterID": "55", "ValueID": "777"},
        {"OptionName": "Розмір", "ValueName": "42", "OptionID": "66", "ValueID": "888"},
    ]}]
    dc_cat_map = {"123": "Ноутбуки", "456": "Телефони"}
    monkeypatch.setattr(importer, "download_feed", lambda: (feed, dc_cat_map))

    stats = importer.sync_dictionaries()
    rec = stub_dict_sync["instance"]

    assert stats["categories_synced"] == 2
    assert stats["attributes_synced"] == 2
    assert stats["values_synced"] == 2
    assert ("123", "Ноутбуки") in rec.categories
    assert ("456", "Телефони") in rec.categories
    assert "Колір" in [a[1] for a in rec.attributes]
    assert "Розмір" in [a[1] for a in rec.attributes]
    assert "777" in [v[1] for v in rec.values]
    assert importer._cached_feed is not None


def test_dclink_run_consumes_cached_feed(dclink_module, monkeypatch):
    importer = dclink_module.DCLinkImporter(feed_path="unused", categories_path="unused")
    importer._cached_feed = ([{"name": "x"}], {"1": "A"})
    download_calls = []
    def fake_download():
        download_calls.append(1)
        return ([], {})
    monkeypatch.setattr(importer, "download_feed", fake_download)
    monkeypatch.setattr(importer, "parse_products", lambda feed, cmap: [])
    importer.run("full")
    assert download_calls == []
    assert importer._cached_feed is None


def test_itlink_sync_only_categories(itlink_module, monkeypatch, stub_dict_sync):
    importer = itlink_module.ITLinkImporter(feed_path=None)
    xml = """<?xml version="1.0"?>
    <yml_catalog><shop><categories>
      <category id="1001">Ноутбуки</category>
      <category id="1002">Телефони</category>
    </categories></shop></yml_catalog>"""
    p = Path("/tmp/fake_itlink_smoke.xml")
    p.write_text(xml, encoding="utf-8")
    importer.feed_path = str(p)

    stats = importer.sync_dictionaries()
    rec = stub_dict_sync["instance"]

    assert stats["categories_synced"] == 2
    assert stats["attributes_synced"] == 0
    assert stats["values_synced"] == 0
    assert ("1001", "Ноутбуки") in rec.categories
    assert ("1002", "Телефони") in rec.categories
    assert importer._cached_xml_path is not None
    p.unlink(missing_ok=True)
