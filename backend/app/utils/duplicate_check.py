"""Helpers for duplicate-prevention validation.

Provides normalization + lookup functions used by both admin API endpoints
and the import runner, ensuring consistent duplicate checking across all
code paths.
"""

import re
from typing import Optional


def normalize_name(name: str) -> str:
    """Normalize a category/attribute/value name for uniqueness comparison.

    Trims leading/trailing whitespace and lower-cases.
    """
    return name.strip().lower()


def find_duplicate_category(cur, name: str, parent_id: Optional[int],
                            exclude_id: Optional[int] = None) -> Optional[int]:
    """Return the ID of an existing category with the same normalized name
    under the same parent, excluding *exclude_id* if given.

    Returns None when no duplicate exists.
    """
    norm = normalize_name(name)
    if parent_id is None:
        sql = "SELECT id FROM categories WHERE LOWER(TRIM(name)) = %s AND parent_id IS NULL"
        params = [norm]
    else:
        sql = "SELECT id FROM categories WHERE LOWER(TRIM(name)) = %s AND parent_id = %s"
        params = [norm, parent_id]
    if exclude_id is not None:
        sql += " AND id != %s"
        params.append(exclude_id)
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def find_duplicate_attribute(cur, name: str,
                             exclude_id: Optional[int] = None) -> Optional[int]:
    """Return the ID of an existing attribute with the same normalized name,
    excluding *exclude_id* if given.

    Attributes are globally unique by normalized name.
    """
    norm = normalize_name(name)
    sql = "SELECT id FROM attributes WHERE LOWER(TRIM(name)) = %s"
    params = [norm]
    if exclude_id is not None:
        sql += " AND id != %s"
        params.append(exclude_id)
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def find_duplicate_attribute_value(cur, attribute_id: int, value: str,
                                   exclude_id: Optional[int] = None) -> Optional[int]:
    """Return the ID of an existing attribute value with the same normalized
    value for the same attribute, excluding *exclude_id* if given.

    Returns None when no duplicate exists.
    """
    norm = normalize_name(value)
    sql = "SELECT id FROM attribute_values WHERE attribute_id = %s AND LOWER(TRIM(value)) = %s"
    params = [attribute_id, norm]
    if exclude_id is not None:
        sql += " AND id != %s"
        params.append(exclude_id)
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None
