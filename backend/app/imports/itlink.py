"""IT-Link supplier importer.

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
from app.imports.import_stats import ImportStats as SharedImportStats
from app.imports.pricing_service import calculate_price, calculate_old_price, find_markup_multiplier
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
class ImportStats(SharedImportStats):
    """IT-Link import statistics. Alias of shared ImportStats (keeps backward
    compatibility for callers that import from itlink module)."""
    pass


class ITLinkImporter:
    SKU_PREFIX = "ITL-"
    SUPPLIER_CODE = "itlink"

    def __init__(self, feed_path: str = None, category_map: dict = None):
        self.feed_path = feed_path
        self.stats = ImportStats()
        self.category_map = dict(category_map) if category_map else {}

    def download_feed(self) -> str:
        """Download the current IT-Link price list via OAuth2."""
        from app.suppliers.itlink_downloader.auth import get_access_token
        from app.suppliers.itlink_downloader.client import download_price_list
        from app.suppliers.itlink_downloader.exceptions import (
            AuthenticationError, ConfigurationError, DownloadError,
        )
        try:
            access_token = get_access_token()
        except AuthenticationError as e:
            raise RuntimeError(f"Помилка аутентифікації IT-Link: {e}") from e
        except ConfigurationError as e:
            raise RuntimeError(f"Помилка конфігурації IT-Link: {e}") from e
        try:
            saved_path = download_price_list(access_token)
        except DownloadError as e:
            raise RuntimeError(f"Помилка завантаження каталогу IT-Link: {e}") from e
        return str(saved_path)

    def _safe_price(self, value: str) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def parse_feed(self, xml_path: str) -> ET.ElementTree:
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"Каталог IT-Link не знайдено: {xml_path}")
        return ET.parse(xml_path)

    def parse_offers(self, tree: ET.ElementTree):
        """Parse XML offers, yielding NormalizedProduct one at a time.

        Yields NormalizedProduct for each valid offer.  The caller must
        iterate the generator to consume products — no full product list
        is retained in memory.
        """
        root = tree.getroot()
        xml_categories = {cat.attrib["id"]: cat.text for cat in root.findall(".//category")}
        offers = root.findall(".//offer")
        self.stats.total = len(offers)

        seen_skus = set()

        for offer in offers:
            offer_id = offer.get("id", "")
            vendor_code = (offer.findtext("vendorCode") or "").strip()
            if not vendor_code:
                self.stats.empty_skus += 1
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

            # Resolve category BEFORE price calculation.
            # Unmapped categories are skipped (not failed).
            category_id = offer.findtext("categoryId", "")
            category_name = xml_categories.get(category_id, "")
            try:
                category_path = resolve_category_path(category_name, self.category_map)
                # Look up internal category_id for category-scoped attribute resolution
                import psycopg2
                from app.core.db_connect import DB
                _conn = psycopg2.connect(DB)
                _cur = _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                _cur.execute("SELECT id FROM categories WHERE name = %s", (category_path,))
                _cat_row = _cur.fetchone()
                _internal_cat_id = _cat_row["id"] if _cat_row else None
                _conn.close()
            except (ValueError, KeyError) as e:
                self.stats.record_unmapped_category(
                    name=category_name,
                    supplier_category_id=category_id,
                    sku=sku,
                )
                self.stats.skipped += 1
                continue

            price_uah = self._safe_price(offer.findtext("price", "0") or "0")
            rrp_uah_str = offer.findtext("rrp", "0") or "0"

            price = calculate_price(
                price_uah=price_uah,
                supplier_code=self.SUPPLIER_CODE,
                category_path=category_path,
            )
            if rrp_uah_str != "0":
                rrp_uah = self._safe_price(rrp_uah_str)
                multiplier = find_markup_multiplier(
                    base_price_uah=price_uah,
                    supplier_code=self.SUPPLIER_CODE,
                    category_path=category_path,
                )
                old_price = calculate_old_price(
                    source_old_price_uah=rrp_uah,
                    markup=multiplier,
                )
            else:
                old_price = None

            description = ""
            raw_attributes = []
            for param in offer.findall("param"):
                pname = (param.attrib.get("name") or "").strip()
                pvalue = (param.text or "").strip()
                if pname == "Опис":
                    description = pvalue
                elif pname and pvalue:
                    raw_attributes.append((pname, pvalue))

            raw_attributes = _validate_attributes(raw_attributes, self.stats, sku, "IT-Link")

            processed_attrs = []
            for attr_name, attr_value in raw_attributes:
                result = process_attribute(attr_name, attr_value,
                                          category_id=_internal_cat_id)
                if isinstance(result, tuple) and len(result) == 2:
                    processed_attrs.append(result)
                elif result == ATTR_SKIP:
                    pass
                elif result == ATTR_UNKNOWN_NAME:
                    self.stats.record_unknown_attribute(attr_name, sku=sku)
                elif result == ATTR_UNKNOWN_VALUE:
                    self.stats.record_unknown_attribute_value(attr_name, attr_value, sku=sku)

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
            yield product

    def run(self, import_type: str = "full") -> ImportStats:
        xml_path = self.feed_path or self.download_feed()
        tree = self.parse_feed(xml_path)
        # Store the generator — the caller (importer_service) will iterate it
        # product-by-product, so only one NormalizedProduct is in memory at a time.
        self.stats.products = self.parse_offers(tree)
        return self.stats
        return self.stats
