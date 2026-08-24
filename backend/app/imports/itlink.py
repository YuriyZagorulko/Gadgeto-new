"""
IT-Link supplier importer.

Downloads the current XML price list via the IT-Link OAuth2 API,
parses it, and returns normalized products for persistence.
"""

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from app.imports.attribute_processor import (
    process_attribute,
    merge_attributes,
    ATTR_SKIP,
    ATTR_UNKNOWN_NAME,
    ATTR_UNKNOWN_VALUE,
)
from app.imports.category_utils import resolve_category_path
from app.core.config import settings
from app.services.seo import generate_product_seo

# Core product fields that must NEVER be overwritten by supplier attributes
PROTECTED_CORE_FIELDS = frozenset({
    "name", "sku", "supplier_sku", "slug", "brand", "brand_id",
    "price", "old_price", "sale_price", "cost", "purchase_cost",
    "stock_qty", "stock_quantity", "stock_status",
    "barcode", "ean", "supplier_id", "category", "category_id",
    "category_path", "images", "description", "short_description",
    "seo_title", "seo_description", "focus_keyphrase",
    "manufacturer", "vendor", "model", "articul", "article",
    "available", "in_stock", "currency", "weight", "dimensions",
})


def _validate_attributes(raw_attributes, stats, sku, logger_prefix=""):
    """Check that no attribute name collides with protected core fields.
    Logs a warning and returns only safe attributes (non-core-field names)."""
    safe = []
    for attr_name, attr_value in raw_attributes:
        key = attr_name.strip().lower().replace(" ", "_").replace("-", "_")
        if key in PROTECTED_CORE_FIELDS:
            msg = f"Supplier attribute '{attr_name}' collides with protected core field — skipping"
            if stats is not None:
                stats.warnings.append(f"{logger_prefix} SKU {sku}: {msg}")
            else:
                import logging
                logging.getLogger(__name__).warning(f"{logger_prefix} SKU {sku}: {msg}")
            # Still pass through the normal attribute processor; it may map it
            # to an internal attribute. If not, it will be UNKNOWN_NAME.
            safe.append((attr_name, attr_value))
        else:
            safe.append((attr_name, attr_value))
    return safe


@dataclass
class NormalizedProduct:
    supplier: str = "itlink"
    supplier_sku: str = ""
    sku: str = ""
    name: str = ""
    description: str = ""
    price: int = 0
    old_price: Optional[int] = None
    category_path: str = ""
    images: List[str] = field(default_factory=list)
    brand: str = ""
    in_stock: bool = True
    attributes: List[Tuple[str, str]] = field(default_factory=list)
    raw_attributes: List[Tuple[str, str]] = field(default_factory=list)
    seo_title: str = ""
    seo_description: str = ""
    focus_keyphrase: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImportStats:
    total_offers: int = 0
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    unknown_attributes: List[Tuple] = field(default_factory=list)
    unknown_attribute_values: List[Tuple] = field(default_factory=list)
    unknown_categories: List[str] = field(default_factory=list)
    duplicate_skus: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[dict] = field(default_factory=list)
    products: list = field(default_factory=list)


class ITLinkImporter:
    SKU_PREFIX = "ITL-"
    SUPPLIER_CODE = "itlink"
    MARKUP = 1.3

    def __init__(self, feed_path: str = None, category_map: dict = None):
        self.feed_path = feed_path
        self.stats = ImportStats()
        self.category_map = dict(category_map) if category_map else {}

    def download_feed(self) -> str:
        """
        Download the current IT-Link price list via OAuth2.
        Returns the path to the downloaded XML file.
        """
        from app.suppliers.itlink_downloader.auth import get_access_token
        from app.suppliers.itlink_downloader.client import download_price_list
        from app.suppliers.itlink_downloader.exceptions import (
            AuthenticationError, ConfigurationError, DownloadError,
        )

        try:
            access_token = get_access_token()
        except AuthenticationError as e:
            raise RuntimeError(f"\u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u0430\u0432\u0442\u0435\u043d\u0442\u0438\u0444\u0456\u043a\u0430\u0446\u0456\u0457 IT-Link: {e}") from e
        except ConfigurationError as e:
            raise RuntimeError(f"\u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u043a\u043e\u043d\u0444\u0456\u0433\u0443\u0440\u0430\u0446\u0456\u0457 IT-Link: {e}") from e

        try:
            saved_path = download_price_list(access_token)
        except DownloadError as e:
            raise RuntimeError(f"\u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0435\u043d\u043d\u044f \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0443 IT-Link: {e}") from e

        return str(saved_path)

    def _safe_price(self, value: str) -> int:
        try:
            return round(float(value) * self.MARKUP)
        except (ValueError, TypeError):
            return 0

    def parse_feed(self, xml_path: str) -> ET.ElementTree:
        if not os.path.exists(xml_path):
            raise FileNotFoundError(
                f"\u041a\u0430\u0442\u0430\u043b\u043e\u0433 IT-Link \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e: {xml_path}"
            )
        return ET.parse(xml_path)

    def parse_offers(self, tree: ET.ElementTree) -> List[NormalizedProduct]:
        root = tree.getroot()
        xml_categories = {cat.attrib["id"]: cat.text for cat in root.findall(".//category")}
        offers = root.findall(".//offer")
        self.stats.total_offers = len(offers)

        products = []
        seen_skus = set()

        for offer in offers:
            offer_id = offer.get("id", "")
            vendor_code = (offer.findtext("vendorCode") or "").strip()
            if not vendor_code:
                continue
            sku = self.SKU_PREFIX + vendor_code

            if sku in seen_skus:
                self.stats.duplicate_skus += 1
                continue
            seen_skus.add(sku)

            name = offer.findtext("name", "") or ""
            vendor = offer.findtext("vendor", "") or ""
            picture = offer.findtext("picture", "") or ""
            available = (offer.findtext("available", "") or "").strip()

            price = self._safe_price(offer.findtext("price", "0") or "0")
            rrp = offer.findtext("rrp", "0") or "0"
            old_price = self._safe_price(rrp) if rrp != "0" else None

            category_id = offer.findtext("categoryId", "")
            category_name = xml_categories.get(category_id, "")
            try:
                category_path = resolve_category_path(category_name, self.category_map)
            except (ValueError, KeyError) as e:
                self.stats.unknown_categories.append(f"'{category_name}' (id={category_id}): {e}")
                self.stats.failed += 1
                self.stats.errors.append({"offer_id": offer_id, "error": f"\u041d\u0435\u0432\u0456\u0434\u043e\u043c\u0430 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u044f: {category_name}"})
                continue

            description = ""
            raw_attributes = []
            for param in offer.findall("param"):
                pname = (param.attrib.get("name") or "").strip()
                pvalue = (param.text or "").strip()
                if pname == "Опис":
                    description = pvalue
                elif pname and pvalue:
                    raw_attributes.append((pname, pvalue))

            # Core-field protection: prevent attribute names from overwriting core fields
            raw_attributes = _validate_attributes(raw_attributes, self.stats, sku, "IT-Link")

            processed_attrs = []
            unknown_names = []
            unknown_values = []
            for attr_name, attr_value in raw_attributes:
                result = process_attribute(attr_name, attr_value)
                if isinstance(result, tuple) and len(result) == 2:
                    processed_attrs.append(result)
                elif result == ATTR_SKIP:
                    pass
                elif result == ATTR_UNKNOWN_NAME:
                    unknown_names.append((attr_name, attr_name, sku))
                elif result == ATTR_UNKNOWN_VALUE:
                    unknown_values.append((attr_name, attr_value, sku))

            merged_attrs = merge_attributes(processed_attrs)
            merged_list = list(merged_attrs.items())

            seo = generate_product_seo({"Name": name, "Regular price": price, "Brand": vendor})

            product = NormalizedProduct(
                supplier_sku=vendor_code,
                sku=sku,
                name=name,
                description=description,
                price=price,
                old_price=old_price,
                category_path=category_path,
                images=[picture] if picture else [],
                brand=vendor,
                in_stock=(available == "true"),
                attributes=merged_list,
                raw_attributes=raw_attributes,
                seo_title=seo.get("seo_title", ""),
                seo_description=seo.get("meta_description", ""),
                focus_keyphrase=seo.get("focus_keyphrase", ""),
            )

            self.stats.unknown_attributes.extend(unknown_names)
            self.stats.unknown_attribute_values.extend(unknown_values)
            products.append(product)

        self.stats.processed = len(products)
        self.stats.products = products
        return products

    def run(self, import_type: str = "full") -> ImportStats:
        xml_path = self.feed_path or self.download_feed()
        tree = self.parse_feed(xml_path)
        self.parse_offers(tree)
        return self.stats
