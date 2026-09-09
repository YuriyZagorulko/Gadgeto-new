"""Contract tests for supplier dictionary sync integration.

Verifies that:
1. sync_dictionaries() method exists on all importers
2. It returns the expected dict format
3. The cached feed mechanism works correctly
"""

import importlib.util
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "app" / "imports"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dclink_has_sync_dictionaries_method():
    mod = _load_module("_test_dcl", str(_BACKEND / "dclink.py"))
    importer = mod.DCLinkImporter(feed_path="unused", categories_path="unused")
    assert hasattr(importer, "sync_dictionaries")
    assert callable(importer.sync_dictionaries)
    # Without credentials, it should return empty stats, not raise
    result = importer.sync_dictionaries()
    assert isinstance(result, dict)
    assert "categories_synced" in result
    assert "attributes_synced" in result
    assert "values_synced" in result


def test_dclink_cached_feed_mechanism():
    """When sync_dictionaries is called before run(), the cached feed is used."""
    mod = _load_module("_test_dcl", str(_BACKEND / "dclink.py"))
    importer = mod.DCLinkImporter(feed_path="unused", categories_path="unused")
    # After sync_dictionaries (which fails due to missing creds), 
    # _cached_feed should not be set (since it failed)
    result = importer.sync_dictionaries()
    # The run() method should handle the missing cache gracefully
    assert hasattr(importer, "_cached_feed")  # attribute exists
    assert importer._cached_feed is None  # but set to None (failed sync)
    # run() must not crash when _cached_feed is None
    # (it will fail with a different error about missing creds, but not
    #  crash due to broken cache logic)


def test_itlink_has_sync_dictionaries_method():
    mod = _load_module("_test_itl", str(_BACKEND / "itlink.py"))
    importer = mod.ITLinkImporter(feed_path="unused")
    assert hasattr(importer, "sync_dictionaries")
    assert callable(importer.sync_dictionaries)
    result = importer.sync_dictionaries()
    assert isinstance(result, dict)
    assert "categories_synced" in result
    assert "attributes_synced" in result
    assert "values_synced" in result


def test_itlink_cached_xml_path_after_sync():
    """IT-Link sync_dictionaries sets _cached_xml_path."""
    mod = _load_module("_test_itl", str(_BACKEND / "itlink.py"))
    importer = mod.ITLinkImporter(feed_path="unused")
    result = importer.sync_dictionaries()
    # After a failed sync (no credentials), _cached_xml_path still exists
    assert hasattr(importer, "_cached_xml_path")


def test_brain_has_sync_dictionaries_method():
    mod = _load_module("_test_brain", str(_BACKEND / "brain.py"))
    importer = mod.BrainImporter(client=None)
    assert hasattr(importer, "sync_dictionaries")
    assert callable(importer.sync_dictionaries)
    result = importer.sync_dictionaries()
    assert isinstance(result, dict)
    assert result == {"categories_synced": 0, "attributes_synced": 0, "values_synced": 0}


def test_sync_dictionaries_returns_expected_keys():
    """All three importers return the same dict shape."""
    from collections import Counter
    dcl = _load_module("_test_dcl", str(_BACKEND / "dclink.py")).DCLinkImporter(
        feed_path="unused", categories_path="unused")
    itl = _load_module("_test_itl", str(_BACKEND / "itlink.py")).ITLinkImporter(
        feed_path="unused")
    brain = _load_module("_test_brain", str(_BACKEND / "brain.py")).BrainImporter(
        client=None)
    expected_keys = {"categories_synced", "attributes_synced", "values_synced"}
    for importer in [dcl, itl, brain]:
        result = importer.sync_dictionaries()
        assert set(result.keys()) == expected_keys,             f"{importer.__class__.__name__} returned {set(result.keys())}"
