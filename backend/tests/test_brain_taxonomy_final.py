"""Targeted tests for the FINAL Brain taxonomy stage (supplier_id=3)."""
import importlib.util
from pathlib import Path

import pytest

_BRAIN_TAX = str(
    Path(__file__).resolve().parents[1] / "app" / "imports" / "brain_taxonomy.py"
)


def _load(name="brain_tax_mod"):
    spec = importlib.util.spec_from_file_location(name, _BRAIN_TAX)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def bt():
    return _load()


def test_numeric_ordering_not_lexical(bt):
    assert bt.sort_numeric(["99", "1045", "100"]) == ["99", "100", "1045"]


def test_duplicate_names_stay_distinct(bt):
    cats = [
        {"categoryID": 1209, "parentID": 1181, "realcat": 0, "name": "X"},
        {"categoryID": 1487, "parentID": 1378, "realcat": 0, "name": "X"},
    ]
    ordered = bt.order_for_insert(cats)
    assert sorted(c["categoryID"] for c in ordered) == [1209, 1487]
    assert bt.build_realcat_map(cats) == {}


def test_fallback_min_is_numeric(bt):
    assert bt.pick_fallback_min(["1045", "99", "1097"]) == "99"


def test_parent_before_child(bt):
    cats = [
        {"categoryID": 12, "parentID": 10, "realcat": 0, "name": "Child"},
        {"categoryID": 10, "parentID": 1, "realcat": 0, "name": "Parent"},
        {"categoryID": 1, "parentID": None, "realcat": 0, "name": "Root"},
    ]
    ordered = bt.order_for_insert(cats)
    pos = {c["categoryID"]: i for i, c in enumerate(ordered)}
    assert pos[1] < pos[10] < pos[12]


def test_virtual_realcat_chain(bt):
    cats = [
        {"categoryID": 10, "parentID": 1, "realcat": 0, "name": "Real"},
        {"categoryID": 20, "parentID": 10, "realcat": 10, "name": "V1"},
        {"categoryID": 30, "parentID": 20, "realcat": 20, "name": "V2"},
    ]
    m = bt.build_realcat_map(cats)
    assert bt.resolve_real_external_id("30", m) == "10"
    assert bt.resolve_real_external_id(20, m) == "10"
    assert bt.resolve_real_external_id("10", m) == "10"


def test_realcat_cycle_safe(bt):
    m = {"1": "2", "2": "1"}
    assert bt.resolve_real_external_id("1", m) in ("1", "2")


def test_routing_depth_and_fallback(bt):
    cats = [
        {"categoryID": 1181, "parentID": 1, "realcat": 0, "name": "P"},
        {"categoryID": 1191, "parentID": 1181, "realcat": 0, "name": "C"},
    ]
    depths = bt.compute_depths(cats)
    assert depths["1191"] > depths["1181"]
    assert bt.pick_product_category([1181, 1191], {}, depths) == "1191"
    assert bt.pick_product_category([1045, 1097], {}, {"1045": 3, "1097": 3}) == "1045"
    assert bt.pick_product_category([30], {"30": "10"}, {"10": 1, "30": 2}) == "10"


def test_optionid_is_identity_filterid_ignored(bt):
    out = bt.extract_brain_attribute_ids(
        {"OptionName": "K", "ValueName": "V",
         "OptionID": "789", "FilterID": "123-456", "ValueID": "999"}
    )
    assert out == ("K", "V", "789", "999")


def test_import_routing_final4(bt):
    """Simulated DB resolver: mapped import, EXCLUDE skip, virtual resolve."""
    mapping = {"1366": "Фотопапір", "1402": "Кабель-менеджмент",
               "1209": "Носії інформації", "1487": "Носії інформації"}

    def resolve(ext_id, realmap):
        real = bt.resolve_real_external_id(ext_id, realmap)
        return mapping.get(real)  # None = EXCLUDE/unmapped -> skip, never import

    assert resolve("1366", {}) == "Фотопапір"
    assert resolve("1402", {}) == "Кабель-менеджмент"
    assert resolve("1209", {}) == resolve("1487", {}) == "Носії інформації"
    assert resolve("9999", {"9999": "1366"}) == "Фотопапір"  # virtual via realcat
    assert resolve("7777", {}) is None  # unmapped -> skip
    assert resolve("5555", {}) is None  # EXCLUDE -> skip, never silently import
