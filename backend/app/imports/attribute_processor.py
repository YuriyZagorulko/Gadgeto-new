"""
Attribute processing pipeline.

Replaces the legacy `attributesManager/attribute_processor.py`.
This is the core mapping pipeline for both IT-Link and DC-Link suppliers.

Processing order (DB-backed):
  1. Check DB-backed resolver (MappingResolver) — supplier-specific then global
  2. If no resolver installed, only return UNKNOWN_NAME (no legacy JSON fallback)
  3. Merge duplicate internal names (combine values with " | ")
"""

# ── DB-backed resolver hook (global + supplier-specific overrides) ─────────
_db_resolver = None  # instance of mapping_resolver.MappingResolver, or None


def set_db_resolver(resolver) -> None:
    """Install/replace the DB-backed resolver for the current importer run.
    Pass None to clear the resolver (no runtime fallback to JSON)."""
    global _db_resolver
    _db_resolver = resolver


# Sentinels (same values as legacy DC-Link processor for exact compatibility)
ATTR_SKIP = "SKIP"
ATTR_UNKNOWN_NAME = "UNKNOWN_NAME"
ATTR_UNKNOWN_VALUE = "UNKNOWN_VALUE"


# ── Public API ────────────────────────────────────────────────────────────


def process_attribute(supplier_name: str, supplier_value: str):
    """
    Process a supplier attribute through the mapping pipeline.

    Returns:
        (mapped_name, mapped_value)  — successful mapping
        ATTR_SKIP                     — attribute/value should be skipped
        ATTR_UNKNOWN_NAME             — attribute name not in any mapping
        ATTR_UNKNOWN_VALUE            — attribute known but value not mapped
    """
    supplier_name = supplier_name.strip()
    supplier_value = str(supplier_value).strip()

    if _db_resolver is not None:
        return _db_resolver.process_attribute(supplier_name, supplier_value)

    if not supplier_name or not supplier_value:
        return ATTR_SKIP
    return ATTR_UNKNOWN_NAME


def merge_attributes(attributes: list) -> dict:
    """
    Merge duplicate attribute names by combining values with " | ".

    Args:
        attributes: List of (name, value) tuples

    Returns:
        Dict of {name: combined_value}
    """
    from collections import defaultdict
    merged: dict = defaultdict(list)
    for name, value in attributes:
        if value and value.strip():
            merged[name].append(value.strip())

    return {
        name: " | ".join(dict.fromkeys(values))
        for name, values in merged.items()
    }
