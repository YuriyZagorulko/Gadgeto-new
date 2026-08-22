"""
IT-Link supplier importer.
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
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
from app.services.seo import generate_product_seo

LEGACY_CATALOG_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog"
ITLINK_XML_PATH = os.path.join(LEGACY_CATALOG_DIR, "IT-link", "itlink.yml")
CATEGORY_MAPPING_PATH = os.path.join(
    LEGACY_CATALOG_DIR, "final data mapping", "category_mapping.json"
)


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
    errors: List[dict] = field(default_factory=list)


class ITLinkImporter:
    SKU_PREFIX = "ITL-"
    SUPPLIER_CODE = "itlink"
    MARKUP = 1.3

    def __init__(self, xml_path: str = None, category_mapping_path: str = None):
        self.xml_path = xml_path or ITLINK_XML_PATH
        self.category_mapping_path = category_mapping_path or CATEGORY_MAPPING_PATH
        self.stats = ImportStats()
        with open(self.category_mapping_path, "r", encoding="utf-8") as f:
            self.category_map = json.load(f)

    def _safe_price(self, value: str) -> int:
        try:
            return round(float(value) * self.MARKUP)
        except (ValueError, TypeError):
            return 0

    def download_feed(self) -> ET.ElementTree:
        if not os.path.exists(self.xml_path):
            raise FileNotFoundError(f"IT-Link XML not found: {self.xml_path}")
        return ET.parse(self.xml_path)

    def parse_offers(self, tree: ET.ElementTree) -> List[NormalizedProduct]:
        root = tree.getroot()
        xml_categories = {cat.attrib["id"]: cat.text for cat in root.findall(".//category")}
        offers = root.findall(".//offer")
        self.stats.total_offers = len(offers)
        
        products = []
        seen_skus = set()
        
        for offer in offers:
            try:
                product = self._parse_offer(offer, xml_categories)
                if product is None:
                    continue
                if product.sku in seen_skus:
                    self.stats.duplicate_skus += 1
                    continue
                seen_skus.add(product.sku)
                products.append(product)
                self.stats.processed += 1
            except Exception as e:
                self.stats.failed += 1
                self.stats.errors.append({"offer_id": offer.get("id", "unknown"), "error": str(e)})
        
        return products

    def _parse_offer(self, offer: Any, xml_categories: dict) -> Optional[NormalizedProduct]:
        offer_id = offer.get("id", "")
        available = offer.get("available", "true")
        
        name = offer.findtext("name", "").strip()
        if not name:
            return None
        
        vendor = offer.findtext("vendor", "").strip()
        vendor_code = offer.findtext("vendorCode", "").strip()
        picture = offer.findtext("picture", "").strip()
        
        # SKU: use vendorCode cleaned, fall back to offer_id (matching legacy)
        sku_base = re.sub(r"[^a-zA-Z0-9_-]", "", vendor_code) if vendor_code else offer_id
        sku = f"{self.SKU_PREFIX}{sku_base}"
        
        # Price (USD * markup)
        price = self._safe_price(offer.findtext("price", "0"))
        rrp = offer.findtext("rrp", "0")
        old_price = self._safe_price(rrp) if rrp and rrp != "0" else None
        
        # Category
        category_id = offer.findtext("categoryId", "")
        category_name = xml_categories.get(category_id, "")
        try:
            category_path = resolve_category_path(category_name, self.category_map)
        except (ValueError, KeyError) as e:
            self.stats.unknown_categories.append(f"'{category_name}' (id={category_id}): {e}")
            self.stats.failed += 1
            self.stats.errors.append({"offer_id": offer_id, "error": f"Unknown category: {category_name}"})
            return None
        
        # Attributes
        description = ""
        raw_attributes = []
        for param in offer.findall("param"):
            pname = (param.attrib.get("name") or "").strip()
            pvalue = (param.text or "").strip()
            if pname == "Опис":
                description = pvalue
            elif pname and pvalue:
                raw_attributes.append((pname, pvalue))
        
        # Process through mapping pipeline
        processed_attrs = []
        unknown_names = []
        unknown_values = []
        for name, value in raw_attributes:
            result = process_attribute(name, value)
            if isinstance(result, tuple) and len(result) == 2:
                processed_attrs.append(result)
            elif result == ATTR_SKIP:
                pass
            elif result == ATTR_UNKNOWN_NAME:
                unknown_names.append((name, name, sku))
            elif result == ATTR_UNKNOWN_VALUE:
                unknown_values.append((name, value, sku))
            elif isinstance(result, tuple) and len(result) == 2 and result[0] == ATTR_UNKNOWN_VALUE:
                unknown_values.append((result[1], result[2], sku))
        
        merged_attrs = merge_attributes(processed_attrs)
        merged_list = list(merged_attrs.items())
        
        # SEO
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
        
        return product

    def run(self, import_type: str = "full") -> ImportStats:
        tree = self.download_feed()
        self.parse_offers(tree)
        return self.stats


if __name__ == "__main__":
    imp = ITLinkImporter()
    stats = imp.run()
    print(f"\nIT-Link Import Results:")
    print(f"  Total offers: {stats.total_offers}")
    print(f"  Processed: {stats.processed}")
    print(f"  Failed: {stats.failed}")
    print(f"  Duplicates: {stats.duplicate_skus}")
    print(f"  Unknown categories: {len(stats.unknown_categories)}")
    print(f"  Unknown attrs: {len(stats.unknown_attributes)}")
    print(f"  Unknown values: {len(stats.unknown_attribute_values)}")
