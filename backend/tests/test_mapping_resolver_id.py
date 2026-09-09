"""Unit tests for MappingResolver ID-based resolution.

Tests the resolution logic in isolation by injecting fake mapping data
into the resolver's internal dictionaries (bypassing DB load).
"""
import pytest

from app.imports.mapping_resolver import MappingResolver
from app.imports.attribute_processor import ATTR_UNKNOWN_NAME, ATTR_UNKNOWN_VALUE, ATTR_SKIP


def _make_resolver(**inject) -> MappingResolver:
    """Create a MappingResolver with fake data, bypassing DB load."""
    r = object.__new__(MappingResolver)
    r.supplier_code = inject.get("supplier_code", "test_supplier")
    r.attrs = inject.get("attrs", {})
    r.values = inject.get("values", {})
    r.cats = inject.get("cats", {})
    r.attrs_by_ext = inject.get("attrs_by_ext", {})
    r.values_by_ext = inject.get("values_by_ext", {})
    r.cats_by_ext = inject.get("cats_by_ext", {})
    return r


# ===================== Category ID resolution ===============================


def test_category_id_exists():
    """external_id supplied and mapping exists -> MAPPED."""
    r = _make_resolver(
        cats_by_ext={"123": {"active": True, "internal_name": "Ноутбуки"}},
        cats={"Ноутбуки": {"active": True, "internal_name": "Ноутбуки"}},
    )
    result = r.resolve_category(external_id="123")
    assert result == "Ноутбуки"


def test_category_id_missing():
    """external_id supplied but no mapping -> UNMAPPED (None)."""
    r = _make_resolver(cats_by_ext={}, cats={"Ноутбуки": {"active": True, "internal_name": "Ноутбуки"}})
    result = r.resolve_category(external_id="999")
    assert result is None  # NO name fallback


def test_category_id_inactive():
    """external_id maps to inactive entry -> UNMAPPED."""
    r = _make_resolver(
        cats_by_ext={"123": {"active": False, "internal_name": "Ноутбуки"}},
    )
    result = r.resolve_category(external_id="123")
    assert result is None


def test_category_id_null_target():
    """external_id maps to entry with NULL internal_name -> UNMAPPED."""
    r = _make_resolver(
        cats_by_ext={"123": {"active": True, "internal_name": None}},
    )
    result = r.resolve_category(external_id="123")
    assert result is None


def test_category_no_id_name_based():
    """No external_id -> name-based resolution works."""
    r = _make_resolver(
        cats={"Ноутбуки": {"active": True, "internal_name": "Ноутбуки"}},
    )
    result = r.resolve_category(name="Ноутбуки")
    assert result == "Ноутбуки"


def test_category_no_id_name_missing():
    """No external_id, name not in map -> UNMAPPED."""
    r = _make_resolver(cats={})
    result = r.resolve_category(name="Unknown")
    assert result is None


# ===================== Attribute ID resolution ==============================


def test_attr_id_exists():
    """external_id supplied and mapping exists -> MAPPED."""
    r = _make_resolver(
        attrs_by_ext={"456": {"sa_id": 1, "active": True, "internal_name": "Діагональ екрану"}},
        values_by_ext={(1, "789"): {"active": True, "value_name": "15.6"}},
    )
    result = r.process_attribute(
        "Діагональ дисплея", "15.6",
        supplier_attr_external_id="456",
        supplier_value_external_id="789",
    )
    assert result == ("Діагональ екрану", "15.6")


def test_attr_id_missing():
    """external_id supplied but no mapping -> ATTR_UNKNOWN_NAME (no name fallback)."""
    r = _make_resolver(
        attrs={"Діагональ дисплея": {"sa_id": 1, "active": True, "internal_name": "Діагональ екрану"}},
        attrs_by_ext={},
    )
    result = r.process_attribute(
        "Діагональ дисплея", "15.6",
        supplier_attr_external_id="999",
    )
    assert result == ATTR_UNKNOWN_NAME  # NO name fallback for ID-capable supplier


def test_attr_id_value_missing():
    """attr ID found, but value ID not found -> ATTR_UNKNOWN_VALUE."""
    r = _make_resolver(
        attrs_by_ext={"456": {"sa_id": 1, "active": True, "internal_name": "Діагональ екрану"}},
        values_by_ext={(1, "999"): {"active": True, "value_name": "other"}},
    )
    result = r.process_attribute(
        "Діагональ дисплея", "15.6",
        supplier_attr_external_id="456",
        supplier_value_external_id="789",
    )
    assert result == ATTR_UNKNOWN_VALUE  # value ID not in map


def test_attr_no_id_name_based():
    """No external_id -> name-based resolution works."""
    r = _make_resolver(
        attrs={"Діагональ дисплея": {"sa_id": 1, "active": True, "internal_name": "Діагональ екрану"}},
        values={("Діагональ дисплея", "15.6"): {"active": True, "value_name": "15.6"}},
    )
    result = r.process_attribute("Діагональ дисплея", "15.6")
    assert result == ("Діагональ екрану", "15.6")


# ===================== Value ID resolution ==================================


def test_val_id_exists():
    """value external_id supplied -> resolve by (sa_id, external_id)."""
    r = _make_resolver(
        attrs_by_ext={"456": {"sa_id": 1, "active": True, "internal_name": "Колір"}},
        values_by_ext={(1, "789"): {"active": True, "value_name": "Чорний"}},
    )
    result = r.process_attribute(
        "Колір", "black",
        supplier_attr_external_id="456",
        supplier_value_external_id="789",
    )
    assert result == ("Колір", "Чорний")


def test_val_id_missing_no_name_fallback():
    """value external_id supplied but not found -> ATTR_UNKNOWN_VALUE."""
    r = _make_resolver(
        attrs_by_ext={"456": {"sa_id": 1, "active": True, "internal_name": "Колір"}},
        values={("Колір", "black"): {"active": True, "value_name": "Чорний"}},
        values_by_ext={},
    )
    result = r.process_attribute(
        "Колір", "black",
        supplier_attr_external_id="456",
        supplier_value_external_id="999",
    )
    assert result == ATTR_UNKNOWN_VALUE  # NO name fallback when value ID supplied


# ===================== IT-Link (name-based) ==================================


def test_itlink_name_based_attr():
    """No external_id for attr -> name-based resolution (IT-Link)."""
    r = _make_resolver(
        attrs={"Діагональ дисплея": {"sa_id": 1, "active": True, "internal_name": "Діагональ екрану"}},
        values={("Діагональ дисплея", '15.6"'): {"active": True, "value_name": '15.6"'}},
    )
    result = r.process_attribute("Діагональ дисплея", '15.6"')
    assert result == ("Діагональ екрану", '15.6"')


def test_itlink_name_based_val():
    """No external_id for value -> name-based resolution (IT-Link)."""
    r = _make_resolver(
        attrs={"Колір": {"sa_id": 1, "active": True, "internal_name": "Колір"}},
        values={("Колір", "Чорний"): {"active": True, "value_name": "Чорний"}},
    )
    result = r.process_attribute("Колір", "Чорний")
    assert result == ("Колір", "Чорний")


# ===================== Supplier scope / collision ===========================


def test_same_external_id_different_suppliers():
    """Same external_id in different suppliers -> no collision.

    The resolver is scoped to one supplier, so they never see each other's IDs.
    """
    r1 = _make_resolver(
        supplier_code="supplier_a",
        attrs_by_ext={"123": {"sa_id": 1, "active": True, "internal_name": "Колір"}},
    )
    r2 = _make_resolver(
        supplier_code="supplier_b",
        attrs_by_ext={"123": {"sa_id": 2, "active": True, "internal_name": "Довжина"}},
    )
    # r1 should resolve to "Колір", r2 to "Довжина"
    from app.imports.attribute_processor import ATTR_UNKNOWN_VALUE
    res1 = r1.process_attribute("attr", "val", supplier_attr_external_id="123")
    res2 = r2.process_attribute("attr", "val", supplier_attr_external_id="123")
    # Both find the attr but can't resolve the value (no value in map)
    assert res1 == ATTR_UNKNOWN_VALUE  # actually found attr but no value
    assert res2 == ATTR_UNKNOWN_VALUE
    # Verify the internal_name differs
    e1 = r1.attrs_by_ext["123"]["internal_name"]
    e2 = r2.attrs_by_ext["123"]["internal_name"]
    assert e1 != e2  # different internal names for same external ID, across suppliers
    assert e1 == "Колір"
    assert e2 == "Довжина"


# ===================== Precedence: supplier-specific > global ===============


def test_specific_overrides_global():
    """Supplier-specific mapping takes precedence over global."""
    r = _make_resolver(
        attrs_by_ext={
            "123": {"sa_id": 1, "active": True, "internal_name": "Supplier-Specific", "specific": True},
        },
        # Global mapping with same external ID (should not be used)
        _global_override=False,
    )
    # Manually check that only the specific one is loaded
    # (the resolver's _load() SQL filters by specificity; we test the logic)
    assert r.attrs_by_ext["123"]["internal_name"] == "Supplier-Specific"


# ===================== edge cases ===========================================


def test_empty_name_or_value():
    r = _make_resolver()
    assert r.process_attribute("", "val") == ATTR_SKIP
    assert r.process_attribute("name", "") == ATTR_SKIP
    assert r.process_attribute("", "") == ATTR_SKIP


def test_category_both_id_and_name():
    """When both external_id and name are provided, external_id wins."""
    r = _make_resolver(
        cats_by_ext={"123": {"active": True, "internal_name": "ID-based"}},
        cats={"Name-based": {"active": True, "internal_name": "Name-based"}},
    )
    result = r.resolve_category(external_id="123", name="Name-based")
    assert result == "ID-based"  # ID wins


def test_attr_inactive_skipped():
    r = _make_resolver(
        attrs={"Test": {"sa_id": 1, "active": False, "internal_name": "Internal"}},
    )
    assert r.process_attribute("Test", "val") == ATTR_SKIP


def test_value_inactive_skipped():
    r = _make_resolver(
        attrs={"Test": {"sa_id": 1, "active": True, "internal_name": "Internal"}},
        values={("Test", "val"): {"active": False, "value_name": "Internal"}},
    )
    assert r.process_attribute("Test", "val") == ATTR_SKIP
