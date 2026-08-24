"""
Category resolution utilities.

Resolves a supplier category name to an internal category name via the
DB-derived category_map dict. No legacy JSON files are read at runtime.
"""

from typing import Dict


def resolve_category_path(supplier_category_name: str, category_map: Dict[str, str], sku: str = "") -> str:
    """
    Resolve a supplier category name to its internal category name.

    The category_map is a dict of {raw_category_name: internal_category_name}
    built from the DB MappingResolver at import time.

    Raises:
        ValueError: If the supplier category has no mapping.

    Returns:
        Internal category name (e.g. "SSD-\u043d\u0430\u043a\u043e\u043f\u0438\u0447\u0443\u0432\u0430\u0447\u0456").
    """
    name = str(supplier_category_name or "").strip()
    if not name:
        raise ValueError(f"Empty supplier category name (SKU: {sku})")

    if name not in category_map:
        raise ValueError(f"Supplier category '{name}' not found in category mapping (SKU: {sku})")

    return category_map[name]
