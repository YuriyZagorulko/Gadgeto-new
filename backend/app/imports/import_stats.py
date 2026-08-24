"""Shared structured import statistics for supplier importers.

Replaces the ad-hoc per-importer ImportStats dataclasses with a single
class that:

- Uses deduplicated counters (dictionaries) for unmapped categories,
  attributes, and attribute values -- avoiding thousands of duplicate
  string entries.
- Tracks occurrence counts and a bounded list of affected SKUs.
- Computes an import status (COMPLETED / COMPLETED_WITH_WARNINGS / FAILED)
  based on the presence of real errors vs. merely unmapped data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Maximum number of SKUs to retain per unmapped entry (for admin report brevity).
_MAX_SKUS = 100

# Import status constants
COMPLETED = "COMPLETED"
COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
FAILED = "FAILED"

# Backward-compatible alias for the old success status.
SUCCEEDED = "SUCCEEDED"


@dataclass
class _UnmappedInfo:
    """Lightweight container for deduplicated unmapped-item tracking."""

    count: int = 0
    supplier_item_id: Optional[str] = None
    skus: List[str] = field(default_factory=list)

    def add(self, sku: Optional[str] = None,
            supplier_item_id: Optional[str] = None):
        self.count += 1
        if supplier_item_id and not self.supplier_item_id:
            self.supplier_item_id = supplier_item_id
        if sku and len(self.skus) < _MAX_SKUS:
            self.skus.append(sku)


@dataclass
class ImportStats:
    """Structured import statistics shared by IT-Link and DC-Link importers.

    Fields:
        total: Total number of items/offers in the supplier feed.
        processed: Number of products that passed parsing and were normalised.
        created / updated: Set externally by ImportRunner after persistence.
        skipped: Products skipped because their supplier category had no
            active mapping (NOT counted as ``failed``).
        failed: Products / items that failed due to real parsing/runtime
            errors (NOT unmapped-category skips).
        duplicate_skus: Duplicate SKU occurrences.
        empty_skus: Items with empty / missing SKU.
        unmapped_categories: {supplier_cat_name: _UnmappedInfo}
        unmapped_attributes: {supplier_attr_name: _UnmappedInfo}
        unmapped_attribute_values: {attr_name: {supplier_value: _UnmappedInfo}}
        warnings: Free-text warnings (e.g. protected-field collisions).
        errors: Structured error dicts with item refs.
        products: Normalised products ready for persistence.
    """

    total: int = 0
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    duplicate_skus: int = 0
    empty_skus: int = 0

    unmapped_categories: Dict[str, _UnmappedInfo] = field(default_factory=dict)
    unmapped_attributes: Dict[str, _UnmappedInfo] = field(default_factory=dict)
    unmapped_attribute_values: Dict[str, Dict[str, _UnmappedInfo]] = field(
        default_factory=dict
    )

    warnings: List[str] = field(default_factory=list)
    errors: List[dict] = field(default_factory=list)
    products: list = field(default_factory=list)

    # ------------------------------------------------------------------ helpers

    @property
    def has_unmapped(self) -> bool:
        """True if any unmapped categories, attributes, or values were found."""
        return (
            bool(self.unmapped_categories)
            or bool(self.unmapped_attributes)
            or bool(self.unmapped_attribute_values)
        )

    @property
    def has_errors(self) -> bool:
        """True if any real (non-unmapped) errors were recorded."""
        return self.failed > 0 or len(self.errors) > 0

    @property
    def status(self) -> str:
        """Compute the import status from collected stats.

        - FAILED if any real errors occurred (parsing or persistence).
        - COMPLETED_WITH_WARNINGS if the import finished but unmapped data
          was found.
        - COMPLETED if everything finished cleanly.
        """
        if self.has_errors:
            return FAILED
        if self.has_unmapped:
            return COMPLETED_WITH_WARNINGS
        return COMPLETED

    # -------------------------------------------------------- recording methods

    def record_unmapped_category(
        self,
        name: str,
        supplier_category_id: Optional[str] = None,
        sku: Optional[str] = None,
    ):
        """Record a supplier category that had no active mapping."""
        info = self.unmapped_categories.get(name)
        if info is None:
            info = _UnmappedInfo(supplier_item_id=supplier_category_id)
            self.unmapped_categories[name] = info
        info.add(sku=sku, supplier_item_id=supplier_category_id)

    def record_unknown_attribute(self, name: str, sku: Optional[str] = None):
        """Record a supplier attribute name with no mapping."""
        info = self.unmapped_attributes.get(name)
        if info is None:
            info = _UnmappedInfo()
            self.unmapped_attributes[name] = info
        info.add(sku=sku)

    def record_unknown_attribute_value(
        self,
        attr_name: str,
        value: str,
        sku: Optional[str] = None,
    ):
        """Record a supplier attribute value with no active value mapping."""
        inner = self.unmapped_attribute_values.setdefault(attr_name, {})
        info = inner.get(value)
        if info is None:
            info = _UnmappedInfo()
            inner[value] = info
        info.add(sku=sku)

    # ----------------------------------------------------------- serialisation

    def to_summary_dict(self) -> dict:
        """Return a JSON-serialisable summary of the stats and unmapped data."""
        def _cat(d: Dict[str, _UnmappedInfo]) -> dict:
            return {
                k: {"count": v.count, "id": v.supplier_item_id, "skus": v.skus}
                for k, v in d.items()
            }

        def _val(d: Dict[str, Dict[str, _UnmappedInfo]]) -> dict:
            return {
                k: {vv: {"count": vi.count, "skus": vi.skus}
                    for vv, vi in inner.items()}
                for k, inner in d.items()
            }

        return {
            "total": self.total,
            "processed": self.processed,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "failed": self.failed,
            "duplicate_skus": self.duplicate_skus,
            "empty_skus": self.empty_skus,
            "unmapped_categories": _cat(self.unmapped_categories),
            "unmapped_attributes": _cat(self.unmapped_attributes),
            "unmapped_attribute_values": _val(self.unmapped_attribute_values),
            "warnings": self.warnings,
            "errors": self.errors,
            "has_unmapped": self.has_unmapped,
            "has_errors": self.has_errors,
            "status": self.status,
        }

    def merge_runner_stats(self, runner) -> dict:
        """Merge ImportRunner persistence stats into a final summary dict.

        Called by ``importer_service.run_full_import`` after the persistence
        loop completes.  The runner provides ``created``, ``updated``,
        ``skipped``, ``failed``, ``warnings``, and ``errors`` for the
        persistence phase.
        """
        summary = self.to_summary_dict()
        summary["created"] = getattr(runner, "created", 0)
        summary["updated"] = getattr(runner, "updated", 0)
        summary["skipped"] = self.skipped + getattr(runner, "skipped", 0)
        summary["failed"] = self.failed + getattr(runner, "failed", 0)
        summary["warnings"] = list(self.warnings) + list(
            getattr(runner, "warnings", [])
        )
        summary["errors"] = list(self.errors) + list(getattr(runner, "errors", []))
        # Recompute status after merging persistence errors.
        has_errors = summary["failed"] > 0 or len(summary["errors"]) > 0
        if has_errors:
            summary["status"] = FAILED
        elif summary["has_unmapped"]:
            summary["status"] = COMPLETED_WITH_WARNINGS
        else:
            summary["status"] = COMPLETED
        return summary
