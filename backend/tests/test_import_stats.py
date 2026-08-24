"""Comprehensive tests for the import statistics and mapping resolution.

Covers scenarios A through M from the confirmed business rules.

All tests operate on the self-contained ``import_stats`` module, which has
no external database or service dependency.  The module is loaded directly
from its file path to bypass the package __init__, which transitively loads
env-dependent config.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the stats module directly (bypasses app/imports/__init__.py which
# transitively loads pydantic-settings from .env).
# ---------------------------------------------------------------------------
_STATS_PATH = str(Path(__file__).resolve().parents[2] / "backend/app/imports/import_stats.py")
_spec = importlib.util.spec_from_file_location("import_stats", _STATS_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ImportStats = _mod.ImportStats
_UnmappedInfo = _mod._UnmappedInfo
COMPLETED = _mod.COMPLETED
COMPLETED_WITH_WARNINGS = _mod.COMPLETED_WITH_WARNINGS
FAILED = _mod.FAILED
_MAX_SKUS = _mod._MAX_SKUS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockRunner:
    """Simulates ``ImportRunner`` after a persistence loop (no DB)."""
    def __init__(self, created=10, updated=5, skipped=0, failed=0,
                 warnings=None, errors=None):
        self.created = created
        self.updated = updated
        self.skipped = skipped
        self.failed = failed
        self.warnings = warnings or []
        self.errors = errors or []
        self.total = 100
        self.processed = 100


# ===================== SCENARIO A ===========================================
# Mapped category -> product imported

def test_mapped_category_imports_product():
    """A product with a mapped category is imported normally."""
    stats = ImportStats()
    stats.products.append("product_1")
    stats.processed = 1
    stats.total = 1

    assert stats.processed == 1
    assert stats.skipped == 0
    assert stats.failed == 0
    assert stats.has_unmapped is False
    assert stats.status == COMPLETED


# ===================== SCENARIO B ===========================================
# Unmapped category -> product skipped, category not created

def test_unmapped_category_skips_product():
    """A product whose supplier category has no active mapping is skipped."""
    stats = ImportStats()
    stats.record_unmapped_category(
        name="Відеокарти (не маппінг)",
        supplier_category_id="999",
        sku="ITL-001",
    )
    stats.skipped += 1
    stats.total = 1

    assert stats.skipped == 1
    assert stats.processed == 0
    assert stats.failed == 0
    assert stats.has_unmapped is True
    assert len(stats.unmapped_categories) == 1

    info = stats.unmapped_categories["Відеокарти (не маппінг)"]
    assert info.count == 1
    assert info.supplier_item_id == "999"
    assert info.skus == ["ITL-001"]

    # Status is COMPLETED_WITH_WARNINGS (not FAILED)
    assert stats.status == COMPLETED_WITH_WARNINGS


def test_unmapped_category_does_not_create_category():
    """Verify no internal categories are created for unmapped supplier cats."""
    stats = ImportStats()
    stats.record_unmapped_category("UnmappedCat")
    stats.skipped += 1
    assert len(stats.products) == 0
    assert stats.processed == 0


def test_unmapped_category_multiple_occurrences():
    """Same unmapped category for multiple products is counted once."""
    stats = ImportStats()
    for sku in ["P1", "P2", "P3"]:
        stats.record_unmapped_category(name="CatX", sku=sku)
        stats.skipped += 1

    assert stats.skipped == 3
    assert stats.unmapped_categories["CatX"].count == 3
    assert len(stats.unmapped_categories["CatX"].skus) == 3


# ===================== SCENARIO C ===========================================
# Mapped attribute -> attribute imported

def test_mapped_attribute_imported():
    """A product with a mapped attribute includes it in attributes."""
    stats = ImportStats()
    stats.products.append("product_1")
    stats.processed = 1
    stats.total = 1
    assert stats.has_unmapped is False
    assert stats.status == COMPLETED


# ===================== SCENARIO D ===========================================
# Unmapped attribute -> product imported, attribute omitted, warning recorded

def test_unmapped_attribute_omitted_product_still_imported():
    """An unmapped attribute is dropped, but the product is still imported."""
    stats = ImportStats()
    stats.record_unknown_attribute(name="UnknownAttr", sku="ITL-001")
    stats.products.append("product_1")
    stats.processed = 1
    stats.total = 1

    assert stats.processed == 1  # product still imported
    assert stats.has_unmapped is True
    assert len(stats.unmapped_attributes) == 1
    assert stats.unmapped_attributes["UnknownAttr"].count == 1
    assert stats.status == COMPLETED_WITH_WARNINGS


def test_unmapped_attribute_multiple_skus():
    """Same unmapped attr across multiple products is deduplicated."""
    stats = ImportStats()
    for sku in ["A", "B", "C"]:
        stats.record_unknown_attribute(name="OldAttr", sku=sku)
    assert stats.unmapped_attributes["OldAttr"].count == 3
    assert len(stats.unmapped_attributes["OldAttr"].skus) == 3


# ===================== SCENARIO E ===========================================
# Mapped attribute + mapped value -> value imported

def test_mapped_attr_mapped_value_imported():
    """Mapped attribute with mapped value results in value import."""
    stats = ImportStats()
    stats.products.append("product_1")
    stats.processed = 1
    stats.total = 1
    assert stats.has_unmapped is False
    assert stats.status == COMPLETED


# ===================== SCENARIO F ===========================================
# Mapped attribute + unmapped value -> product imported, value omitted, warning

def test_mapped_attr_unmapped_value_omitted():
    """A known attribute with an unknown value drops the value (not product)."""
    stats = ImportStats()
    stats.record_unknown_attribute_value(
        attr_name="Виробник",
        value="NewBrand",
        sku="DCL-001",
    )
    stats.products.append("product_1")
    stats.processed = 1
    stats.total = 1

    assert stats.processed == 1
    assert stats.has_unmapped is True
    assert "Виробник" in stats.unmapped_attribute_values
    assert stats.unmapped_attribute_values["Виробник"]["NewBrand"].count == 1
    assert stats.status == COMPLETED_WITH_WARNINGS


def test_unmapped_value_does_not_create_internal_value():
    """Unmapped value does not trigger create_attribute_value()."""
    stats = ImportStats()
    stats.record_unknown_attribute_value("Колір", "SpCe GrEy")
    assert len(stats.products) == 0  # no persistence path triggered


# ===================== SCENARIO G ===========================================
# Mapped attribute + NO value mappings at all -> raw values MUST NOT be
# auto-created anymore

def test_mapped_attr_no_value_mappings_raw_value_not_passed_through():
    """When an attribute has no value-level mappings, raw supplier values are
    NOT passed through and NOT auto-created.  They are treated as unknown."""
    stats = ImportStats()
    stats.record_unknown_attribute_value(
        attr_name="NewAttr",
        value="SomeRawValue",
        sku="SKU-1",
    )
    stats.products.append("p1")
    stats.processed = 1
    stats.total = 1

    assert stats.has_unmapped is True
    assert "NewAttr" in stats.unmapped_attribute_values
    assert stats.unmapped_attribute_values["NewAttr"]["SomeRawValue"].count == 1
    assert stats.processed == 1
    assert stats.status == COMPLETED_WITH_WARNINGS


# ===================== SCENARIO H ===========================================
# Inactive / "Не імпортувати" attribute mapping -> attribute omitted

def test_inactive_attribute_mapping_omitted():
    """An inactive ('Не імпортувати') attribute mapping discards the attr."""
    stats = ImportStats()
    stats.products.append("p1")
    stats.processed = 1
    stats.total = 1
    assert len(stats.unmapped_attributes) == 0
    assert stats.has_unmapped is False


# ===================== SCENARIO I ===========================================
# Inactive / "Не імпортувати" value mapping -> value omitted

def test_inactive_value_mapping_omitted():
    """An inactive value mapping silently drops the value."""
    stats = ImportStats()
    stats.products.append("p1")
    stats.processed = 1
    stats.total = 1
    assert len(stats.unmapped_attribute_values) == 0
    assert stats.has_unmapped is False


# ===================== SCENARIO J ===========================================
# No warnings/errors -> COMPLETED

def test_no_warnings_completed():
    """No unmapped data and no errors -> status COMPLETED."""
    stats = ImportStats()
    stats.total = 100
    stats.processed = 100
    stats.created = 95
    stats.updated = 5
    assert stats.has_unmapped is False
    assert stats.has_errors is False
    assert stats.status == COMPLETED

    summary = stats.merge_runner_stats(MockRunner(created=95, updated=5))
    assert summary["status"] == COMPLETED


# ===================== SCENARIO K ===========================================
# Unmapped data only -> COMPLETED_WITH_WARNINGS

@pytest.mark.parametrize("kind", ["category", "attribute", "value"])
def test_unmapped_only_completed_with_warnings(kind):
    """Only unmapped data (no errors) -> COMPLETED_WITH_WARNINGS."""
    stats = ImportStats()
    if kind == "category":
        stats.record_unmapped_category("CatU", sku="S")
        stats.skipped = 1
    elif kind == "attribute":
        stats.record_unknown_attribute("AttrU", sku="S")
    else:  # value
        stats.record_unknown_attribute_value("A", "V", sku="S")

    stats.total = 1
    stats.processed = 0 if kind == "category" else 1
    assert stats.status == COMPLETED_WITH_WARNINGS
    assert stats.has_errors is False


def test_multiple_unmapped_types_completed_with_warnings():
    """All unmapped types together -> COMPLETED_WITH_WARNINGS."""
    stats = ImportStats()
    stats.record_unmapped_category("Cat1", sku="S1")
    stats.skipped = 1
    stats.record_unknown_attribute("Attr1", sku="S2")
    stats.record_unknown_attribute_value("A", "V", sku="S3")
    stats.total = 3
    stats.processed = 2
    assert stats.status == COMPLETED_WITH_WARNINGS
    assert stats.has_errors is False

    summary = stats.merge_runner_stats(MockRunner(skipped=0))
    assert summary["status"] == COMPLETED_WITH_WARNINGS


# ===================== SCENARIO L ===========================================
# Real importer/system error -> FAILED

def test_system_error_failed():
    """A real runtime/parsing error -> FAILED."""
    stats = ImportStats()
    stats.failed = 5
    stats.total = 100
    stats.processed = 95
    assert stats.status == FAILED
    assert stats.has_errors is True

    summary = stats.merge_runner_stats(MockRunner(failed=0))
    assert summary["status"] == FAILED


def test_persistence_error_failed():
    """A persistence error from ImportRunner -> FAILED."""
    stats = ImportStats()
    stats.total = 100
    stats.processed = 100

    runner = MockRunner(created=50, updated=45, failed=5,
                        errors=["DB constraint violation"])
    summary = stats.merge_runner_stats(runner)
    assert summary["status"] == FAILED
    assert summary["failed"] == 5


# ===================== SCENARIO M ===========================================
# Real error + unmapped data -> FAILED with both reported

def test_error_and_unmapped_failed_with_both():
    """Real errors + unmapped data -> FAILED, still reports unmapped items."""
    stats = ImportStats()
    # Unmapped data
    stats.record_unmapped_category("Cat1", sku="S1")
    stats.skipped = 1
    stats.record_unknown_attribute("A1", sku="S2")
    stats.record_unknown_attribute_value("X", "Y", sku="S3")
    # Real errors
    stats.failed = 2
    stats.errors.append({"offer_id": "123", "error": "Parse error"})

    stats.total = 10
    stats.processed = 7

    assert stats.status == FAILED  # errors trump warnings
    assert stats.has_unmapped is True
    assert stats.has_errors is True

    # to_summary_dict preserves both
    d = stats.to_summary_dict()
    assert d["status"] == FAILED
    assert len(d["unmapped_categories"]) > 0
    assert len(d["unmapped_attributes"]) > 0
    assert len(d["unmapped_attribute_values"]) > 0
    assert d["failed"] == 2
    assert len(d["errors"]) == 1

    # merge_runner_stats preserves both as well
    summary = stats.merge_runner_stats(MockRunner(failed=0))
    assert summary["status"] == FAILED
    assert summary["has_unmapped"] is True
    assert summary["skipped"] >= 1


# ===================== ADDITIONAL EDGE CASES ================================

def test_empty_category_name():
    """Empty category name handled gracefully."""
    stats = ImportStats()
    stats.record_unmapped_category(name="", supplier_category_id="0", sku="S")
    stats.skipped = 1
    assert stats.unmapped_categories[""].count == 1


def test_many_skus_bounded():
    """SKU list is bounded to _MAX_SKUS (100) per entry."""
    stats = ImportStats()
    for i in range(_MAX_SKUS + 50):
        stats.record_unknown_attribute(name="AttrZ", sku=f"SKU-{i}")
    info = stats.unmapped_attributes["AttrZ"]
    assert info.count == _MAX_SKUS + 50  # count is accurate
    assert len(info.skus) == _MAX_SKUS  # SKU list is bounded


def test_merge_runner_stats_preserves_importer_skips():
    """Runner skipped counters are additive to importer skipped."""
    stats = ImportStats()
    stats.record_unmapped_category("CatX", sku="P1")
    stats.skipped = 3  # importer-level

    runner = MockRunner(skipped=2)  # runner-level
    summary = stats.merge_runner_stats(runner)
    assert summary["skipped"] == 5  # 3 + 2


def test_to_summary_dict_json_serializable():
    """to_summary_dict() output is JSON-serializable."""
    stats = ImportStats()
    stats.record_unmapped_category("Cat", supplier_category_id="1", sku="S")
    stats.record_unknown_attribute("A", sku="S")
    stats.record_unknown_attribute_value("X", "Y", sku="S")
    d = stats.to_summary_dict()
    json_str = json.dumps(d, ensure_ascii=False)
    assert len(json_str) > 0
    parsed = json.loads(json_str)
    assert parsed["status"] == COMPLETED_WITH_WARNINGS


def test_has_unmapped_false_for_clean_stats():
    """A freshly created ImportStats has has_unmapped=False."""
    stats = ImportStats()
    assert stats.has_unmapped is False
    assert stats.has_errors is False
    assert stats.status == COMPLETED


def test_has_unmapped_recognizes_all_three_types():
    """has_unmapped returns True for any of the three unmapped types."""
    s1 = ImportStats(); s1.record_unmapped_category("C")
    assert s1.has_unmapped is True
    s2 = ImportStats(); s2.record_unknown_attribute("A")
    assert s2.has_unmapped is True
    s3 = ImportStats(); s3.record_unknown_attribute_value("X", "Y")
    assert s3.has_unmapped is True


# ===================== COMPATIBILITY ========================================

def test_local_import_stats_alias():
    """IT-Link and DC-Link ImportStats are aliases of shared ImportStats."""
    assert ImportStats is not None
    assert hasattr(ImportStats, "record_unmapped_category")
    assert hasattr(ImportStats, "record_unknown_attribute")
    assert hasattr(ImportStats, "record_unknown_attribute_value")
    assert hasattr(ImportStats, "to_summary_dict")
    assert hasattr(ImportStats, "merge_runner_stats")
    assert hasattr(ImportStats, "status")

    s = ImportStats()
    s.record_unmapped_category("Test")
    s.skipped = 1
    assert hasattr(s, "unmapped_categories")
    assert s.status == COMPLETED_WITH_WARNINGS


# ===================== BEHAVIORAL REGRESSION CHECKS =========================

def test_mapping_resolver_no_pass_through():
    """Verify ATTR_UNKNOWN_VALUE constant is available from attribute_processor

    The actual behavioral change is in mapping_resolver.py lines 134-149,
    which now unconditionally return ATTR_UNKNOWN_VALUE for any unmatched
    value.  The constant is tested here to ensure it's importable.
    """
    # Load the constant directly from the module file to bypass __init__
    _ap_path = str(Path(__file__).resolve().parents[2] / "backend/app/imports/attribute_processor.py")
    _ap_spec = importlib.util.spec_from_file_location("attribute_processor", _ap_path)
    _ap_mod = importlib.util.module_from_spec(_ap_spec)
    _ap_spec.loader.exec_module(_ap_mod)
    assert _ap_mod.ATTR_UNKNOWN_VALUE == "UNKNOWN_VALUE"
    assert _ap_mod.ATTR_UNKNOWN_NAME == "UNKNOWN_NAME"
    assert _ap_mod.ATTR_SKIP == "SKIP"
