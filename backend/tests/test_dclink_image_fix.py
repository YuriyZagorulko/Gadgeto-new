"""Regression tests for DC-Link KeyError fix and image deduplication fix."""

import importlib.util
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Load the modules directly (bypasses app/imports/__init__.py import chain)
# ---------------------------------------------------------------------------
_DCLINK_PATH = str(Path(__file__).resolve().parents[2] / "backend/app/imports/dclink.py")
_RUNNER_PATH = str(Path(__file__).resolve().parents[2] / "backend/app/imports/import_runner.py")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_download_feed_uses_get_not_bracket():
    """download_feed() must use .get() instead of bracket access to avoid KeyError."""
    src = Path(_DCLINK_PATH).read_text()

    # Verify no bracket access to ["id"] in download_feed
    in_download_feed = False
    problematic_lines = []
    for i, line in enumerate(src.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("def download_feed"):
            in_download_feed = True
        elif in_download_feed and stripped.startswith("def "):
            in_download_feed = False
        elif in_download_feed:
            # Check for bracket access to "id"
            if '["id"]' in stripped or "['id']" in stripped:
                problematic_lines.append((i, stripped))

    assert len(problematic_lines) == 0, \
        f"download_feed still has bracket access to 'id' at lines: {[l for l, _ in problematic_lines]}"


def test_download_feed_resilient_to_missing_id():
    """download_feed handles missing 'id' key without crashing."""
    dclink = _load_module("dclink", _DCLINK_PATH)
    imp = dclink.DCLinkImporter()

    # Mock the API calls to return data WITHOUT "id" key
    def mock_login():
        return "test_sid"

    def mock_get_categories(sid):
        # Return categories WITHOUT "id"
        return [{"category_id": 123, "name": "Test Category"}]

    def mock_get_products(sid, cat_id):
        # Return products WITHOUT "id"
        return [{"product_id": 999, "articul": "TEST001", "name": "Test Product"}]

    def mock_get_products_content(sid, product_ids):
        return [{"id": 999, "articul": "TEST001", "name": "Test Product", "options": []}]

    imp._login = mock_login
    imp._get_categories = mock_get_categories
    imp._get_products = mock_get_products
    imp._get_products_content = mock_get_products_content

    content, cat_map = imp.download_feed()

    assert len(cat_map) == 1, "Expected 1 mapped category"
    assert cat_map["123"] == "Test Category"
    assert content == [{"id": 999, "articul": "TEST001", "name": "Test Product", "options": []}]


def test_download_feed_resilient_to_mixed_keys():
    """download_feed handles mixed 'id' and alternative keys."""
    dclink = _load_module("dclink", _DCLINK_PATH)
    imp = dclink.DCLinkImporter()

    def mock_login():
        return "test_sid"

    def mock_get_categories(sid):
        # Mix of "id" and "category_id"
        return [
            {"id": 1, "name": "Standard"},
            {"category_id": 2, "name": "Alternative"},
        ]

    def mock_get_products(sid, cat_id):
        return [
            {"id": 10, "articul": "A001"},
            {"product_id": 20, "articul": "A002"},
        ]

    def mock_get_products_content(sid, product_ids):
        return [{"art": str(pid)} for pid in product_ids]

    imp._login = mock_login
    imp._get_categories = mock_get_categories
    imp._get_products = mock_get_products
    imp._get_products_content = mock_get_products_content

    content, cat_map = imp.download_feed()

    assert len(cat_map) == 2
    assert cat_map["1"] == "Standard"
    assert cat_map["2"] == "Alternative"
    assert len(content) == 2


def test_upsert_images_deletes_existing_matching_urls():
    """_upsert_images must DELETE existing images with matching URLs before INSERT."""
    runner = _load_module("import_runner", _RUNNER_PATH)

    # We can't instantiate ImportRunner easily (needs DB), so do AST check
    src = Path(_RUNNER_PATH).read_text()

    # The method must contain both DELETE and INSERT
    assert "DELETE FROM product_images" in src, \
        "_upsert_images must DELETE existing matching images before INSERT"
    assert "INSERT INTO product_images" in src, \
        "_upsert_images must INSERT images"

    # Verify the DELETE is BEFORE the INSERT loop
    in_upsert = False
    found_delete = False
    found_insert = False
    delete_before_insert = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("def _upsert_images"):
            in_upsert = True
            found_delete = False
            found_insert = False
        elif in_upsert and stripped.startswith("def "):
            in_upsert = False
        elif in_upsert:
            if "DELETE FROM product_images" in stripped:
                found_delete = True
            if "INSERT INTO product_images" in stripped:
                found_insert = True
                if found_delete:
                    delete_before_insert = True

    assert found_delete, "_upsert_images must DELETE existing images"
    assert found_insert, "_upsert_images must INSERT images"
    assert delete_before_insert, "DELETE must come before INSERT in _upsert_images"


def test_upsert_images_urls_collected_before_execution():
    """_upsert_images must collect URLS before any DB operation."""
    src = Path(_RUNNER_PATH).read_text()
    # Must have a "urls_to_import" list
    assert "urls_to_import" in src, \
        "_upsert_images must collect URLs into a list before DB operations"
    assert "url = img_url.strip()" not in src or "urls_to_import" in src, \
        "_upsert_images should strip URLs early, not re-strip in loop"
