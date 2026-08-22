"""
Base importer class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime


class BaseImporter(ABC):
    """Base class for all suppliers importers."""

    supplier_code: str
    supplier_name: str

    def __init__(self):
        self.stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

    @abstractmethod
    def download_feed(self) -> Any:
        """Download supplier feed (XML, JSON, etc.)."""
        pass

    @abstractmethod
    def parse_feed(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Parse raw feed data into normalized product list."""
        pass

    @abstractmethod
    def normalize_product(self, raw_product: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single product to internal schema."""
        pass

    @abstractmethod
    def map_category(self, supplier_category: str) -> Optional[str]:
        """Map supplier category to internal category path."""
        pass

    @abstractmethod
    def map_attribute(self, supplier_attr_name: str, supplier_value: str) -> Optional[tuple]:
        """
        Map supplier attribute and value to internal attribute and value.
        Returns (internal_attr_name, internal_value) or None to skip.
        """
        pass

    def validate_category(self, category_path: str) -> bool:
        """Validate that category exists in the database."""
        # Will be implemented in concrete classes with database access
        return True

    def run(self, import_type: str = "full") -> Dict[str, Any]:
        """
        Run full import pipeline.

        Args:
            import_type: 'full' or 'delta'

        Returns:
            Statistics dict
        """
        try:
            raw_data = self.download_feed()
            products = self.parse_feed(raw_data)

            for product in products:
                try:
                    normalized = self.normalize_product(product)

                    # Map category
                    category_path = self.map_category(normalized.get("category", ""))
                    if not category_path:
                        self.stats["skipped"] += 1
                        continue

                    # Map attributes
                    normalized_attrs = []
                    for attr_name, attr_value in normalized.get("attributes", {}).items():
                        mapped = self.map_attribute(attr_name, attr_value)
                        if mapped:
                            normalized_attrs.append(mapped)
                    normalized["attributes"] = normalized_attrs

                    # TODO: Upsert product to database
                    # self.upsert_product(normalized, category_path)

                    self.stats["created"] += 1

                except Exception as e:
                    self.stats["failed"] += 1
                    self.stats["errors"].append({
                        "sku": normalized.get("supplier_sku", "unknown"),
                        "error": str(e),
                    })

            return self.stats

        except Exception as e:
            self.stats["errors"].append({"global_error": str(e)})
            return self.stats
