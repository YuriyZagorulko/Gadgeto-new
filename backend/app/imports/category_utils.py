"""
Category resolution utilities.

Replicates the legacy `woocommerce_category_resolver.py` functionality.
"""

import json
import os
from typing import Dict, Optional

# Path to WC categories export
LEGACY_MAPPING_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping"
WC_CATEGORIES_PATH = os.path.join(
    LEGACY_MAPPING_DIR, "data_from_server", "woocommerce_categories.json"
)

# Cached category index
_wc_category_index = None  # Dict[str, dict]  keyed by name, slug, path


def _load_wc_categories() -> dict:
    """Load and index WC categories."""
    global _wc_category_index
    if _wc_category_index is not None:
        return _wc_category_index
    
    try:
        with open(WC_CATEGORIES_PATH, "r", encoding="utf-8") as f:
            categories = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _wc_category_index = {}
        return _wc_category_index
    
    index = {"by_name": {}, "by_slug": {}, "by_path": {}}
    
    if not isinstance(categories, list):
        categories = []
    
    for cat in categories:
        name = cat.get("name", "")
        slug = cat.get("slug", "")
        path = cat.get("path", "")
        
        if name:
            index["by_name"][name] = cat
        if slug:
            index["by_slug"][slug] = cat
        if path:
            index["by_path"][path] = cat
    
    _wc_category_index = index
    return index


def resolve_category_path(supplier_category_name: str, category_map: Dict[str, str], sku: str = "") -> str:
    """
    Resolve a supplier category name to its WooCommerce category path.
    
    This is the exact same resolution pipeline as the legacy system:
        supplier_category_name
            → category_mapping.json lookup
            → internal category name
            → get `path` from woocommerce_categories.json
            → return path
    
    Raises:
        ValueError: If any step fails.
    
    Returns:
        WooCommerce category path (e.g. "Комп'ютери > Комплектуючі > SSD-накопичувачі")
    """
    name = str(supplier_category_name or "").strip()
    if not name:
        raise ValueError(f"Empty supplier category name (SKU: {sku})")
    
    # Step 1: Look up in category_mapping.json
    if name not in category_map:
        raise ValueError(f"Supplier category '{name}' not found in category_mapping.json (SKU: {sku})")
    
    mapped_name = category_map[name]
    
    # Step 2: Look up the mapped WC category by name
    index = _load_wc_categories()
    cat = index["by_name"].get(mapped_name)
    
    if cat is None:
        raise ValueError(f"Mapped WC category '{mapped_name}' not found in WC categories (SKU: {sku})")
    
    path = cat.get("path", "")
    if not path:
        raise ValueError(f"Category '{mapped_name}' has no valid 'path' (SKU: {sku})")
    
    # Step 3: Verify path exists
    if path not in index["by_path"]:
        raise ValueError(f"Category '{mapped_name}' has path '{path}' which is not indexed (SKU: {sku})")
    
    return path


def reload_categories():
    """Force reload of category index (useful for testing)."""
    global _wc_category_index
    _wc_category_index = None


def get_wc_category_index_stats() -> dict:
    """Get statistics about the loaded WC categories."""
    index = _load_wc_categories()
    return {
        "total_by_name": len(index["by_name"]),
        "total_by_path": len(index["by_path"]),
        "total_by_slug": len(index["by_slug"]),
    }
