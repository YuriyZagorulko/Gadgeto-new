"""
Attribute processing pipeline.

Replaces the legacy `attributesManager/attribute_processor.py`.
This is the core mapping pipeline for both IT-Link and DC-Link suppliers.

Processing order:
  1. Load mapping files (JSON → in-memory)
  2. For each supplier attribute name+value:
     a. Check remove list (attribute_remove.json) → skip
     b. Map to internal name (attributes_final.json)
     c. Check value remove list (attribute_value_to_remove.json) → skip
     d. Check value mapping table (attribute_value_mapping_final.json)
        - If mapping exists for attribute: value must be in table → skip if not
        - If no mapping table: pass value as-is
     e. Return (internal_name, internal_value) or skip marker
  3. Merge duplicate internal names (combine values with " | ")
"""

import json
import os
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

# Paths to mapping files
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
_LEGACY_MAPPING_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog/final data mapping"

# Sentinels (same values as legacy DC-Link processor for exact compatibility)
ATTR_SKIP = "SKIP"
ATTR_UNKNOWN_NAME = "UNKNOWN_NAME"
ATTR_UNKNOWN_VALUE = "UNKNOWN_VALUE"


def _load_json(path: str) -> dict:
    """Load JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ── Lazy-loaded mapping data ─────────────────────────────────────────────

_attr_remove: Optional[Set[str]] = None
_attr_final_map: Optional[Dict[str, str]] = None
_attr_value_remove: Optional[Dict[str, Set[str]]] = None
_attr_value_map: Optional[Dict[str, Dict[str, str]]] = None


# ── DB-backed resolver hook (global + supplier-specific overrides) ─────────
_db_resolver = None  # instance of mapping_resolver.MappingResolver, or None


def set_db_resolver(resolver) -> None:
    """Install/replace the DB-backed resolver for the current importer run.
    Pass None to restore legacy JSON-file resolution."""
    global _db_resolver
    _db_resolver = resolver


def _load_attr_remove() -> Set[str]:
    global _attr_remove
    if _attr_remove is None:
        data = _load_json(os.path.join(_LEGACY_MAPPING_DIR, "attribute_remove.json"))
        _attr_remove = set(data.keys())
    return _attr_remove


def _load_attr_final_map() -> Dict[str, str]:
    global _attr_final_map
    if _attr_final_map is None:
        _attr_final_map = _load_json(os.path.join(_LEGACY_MAPPING_DIR, "attributes_final.json"))
    return _attr_final_map


def _load_attr_value_remove() -> Dict[str, Set[str]]:
    global _attr_value_remove
    if _attr_value_remove is None:
        data = _load_json(os.path.join(_LEGACY_MAPPING_DIR, "attribute_value_to_remove.json"))
        _attr_value_remove = {k: set(v) if isinstance(v, list) else set() for k, v in data.items()}
    return _attr_value_remove


def _load_attr_value_map() -> Dict[str, Dict[str, str]]:
    global _attr_value_map
    if _attr_value_map is None:
        _attr_value_map = _load_json(os.path.join(_LEGACY_MAPPING_DIR, "attribute_value_mapping_final.json"))
    return _attr_value_map


# ── Public API ────────────────────────────────────────────────────────────


def process_attribute(supplier_name: str, supplier_value: str) -> Union[Tuple, str]:
    """
    Process one supplier attribute through the full pipeline.
    
    Args:
        supplier_name: Raw attribute name from supplier feed
        supplier_value: Raw attribute value from supplier feed
    
    Returns:
        (internal_name, internal_value): Successful mapping
        ATTR_SKIP: Skip silently (removed attribute or value)
        ATTR_UNKNOWN_NAME: Name not mapped
        ATTR_UNKNOWN_VALUE: Value not in mapping table
    """
    supplier_name = supplier_name.strip()
    supplier_value = str(supplier_value).strip()

    if _db_resolver is not None:
        return _db_resolver.process_attribute(supplier_name, supplier_value)

    if not supplier_name or not supplier_value:
        return ATTR_SKIP

    # Step 1: Remove unwanted attributes
    if supplier_name in _load_attr_remove():
        return ATTR_SKIP

    # Step 2: Map attribute name
    mapped_name = _load_attr_final_map().get(supplier_name)
    if mapped_name is None:
        return ATTR_UNKNOWN_NAME

    # Step 3: Remove unwanted values
    value_remove_map = _load_attr_value_remove()
    if mapped_name in value_remove_map and supplier_value in value_remove_map[mapped_name]:
        return ATTR_SKIP

    # Step 4: Map attribute values
    attr_value_map = _load_attr_value_map().get(mapped_name)

    if attr_value_map is not None:
        if supplier_value in attr_value_map:
            final_value = attr_value_map[supplier_value]
        else:
            return ATTR_UNKNOWN_VALUE
    else:
        final_value = supplier_value

    return (mapped_name, final_value)


def supplier_name_to_woo_name(supplier_name: str) -> str:
    """Map supplier attribute name to WooCommerce name (or return empty)."""
    return _load_attr_final_map().get(supplier_name.strip(), "")


def is_global_woo_name(name: str) -> bool:
    """Check if a mapped name is actually a global WooCommerce attribute name."""
    # In the legacy system, this checked whether the name exists in
    # the WooCommerce attribute taxonomies. Since we have all final mappings
    # loaded, we consider any name that exists in the final map as valid.
    attr_final_reverse = {v: k for k, v in _load_attr_final_map().items()}
    return name in attr_final_reverse


def merge_attributes(attributes: List[Tuple[str, str]]) -> Dict[str, str]:
    """
    Merge duplicate attribute names by combining values with " | ".
    
    Args:
        attributes: List of (name, value) tuples
    
    Returns:
        Dict of {name: combined_value}
    """
    merged: Dict[str, list] = defaultdict(list)
    for name, value in attributes:
        if value and value.strip():
            merged[name].append(value.strip())

    return {
        name: " | ".join(dict.fromkeys(values))  # preserve order, remove adjacent dupes
        for name, values in merged.items()
    }


# ── Statistics helpers ────────────────────────────────────────────────────


def get_mapping_stats() -> dict:
    """Get current mapping data statistics."""
    attr_final = _load_attr_final_map()
    attr_value_map = _load_attr_value_map()
    
    internal_names = set(attr_final.values())
    
    return {
        "attr_remove_count": len(_load_attr_remove()),
        "attr_final_count": len(attr_final),
        "internal_names_count": len(internal_names),
        "value_mapped_attrs": len(attr_value_map),
        "value_mapping_entries": sum(len(v) for v in attr_value_map.values()),
        "value_remove_attrs": len(_load_attr_value_remove()),
    }


# ── Reload function (useful for testing) ──────────────────────────────────


def reload_mappings():
    """Force reload all mapping files (useful for testing after changes)."""
    global _attr_remove, _attr_final_map, _attr_value_remove, _attr_value_map
    _attr_remove = None
    _attr_final_map = None
    _attr_value_remove = None
    _attr_value_map = None
