"""
DC-Link supplier importer.

Reads the locally cached JSON feed (dclink_products.json), applies the full
mapping pipeline, and returns normalized products.
"""

import json
import os
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

# Legacy catalog paths
LEGACY_CATALOG_DIR = "/home/yuri/Desktop/my/projects/gedgeto/catalog"
DCLINK_PRODUCTS_PATH = os.path.join(LEGACY_CATALOG_DIR, "DC-Link", "dclink_products.json")
DCLINK_CATEGORIES_PATH = os.path.join(LEGACY_CATALOG_DIR, "DC-Link", "dclink_categories.json")
CATEGORY_MAPPING_PATH = os.path.join(
    LEGACY_CATALOG_DIR, "final data mapping", "category_mapping.json"
)


@dataclass
class NormalizedProduct:
    """Normalized product from supplier feed (same structure as IT-Link)."""
    supplier: str = "dclink"
    supplier_sku: str = ""
    sku: str = ""
    name: str = ""
    description: str = ""
    short_description: str = ""
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
    """Import statistics."""
    total_items: int = 0
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    unknown_attributes: List[Tuple[str, str, str]] = field(default_factory=list)
    unknown_attribute_values: List[Tuple[str, str, str]] = field(default_factory=list)
    unknown_categories: List[str] = field(default_factory=list)
    duplicate_skus: int = 0
    empty_skus: int = 0
    errors: List[dict] = field(default_factory=list)


class DCLinkImporter:
    """DC-Link supplier importer."""
    
    SKU_PREFIX = "DCL-"
    SUPPLIER_CODE = "dclink"
    
    # Tiered markup: (price_threshold_uah, multiplier)
    MARKUP_RULES = [
        (200, 1.50),
        (500, 1.45),
        (1000, 1.40),
        (3000, 1.35),
        (7000, 1.30),
        (15000, 1.25),
        (float("inf"), 1.20),
    ]
    
    def __init__(self, products_path: str = None, categories_path: str = None,
                 category_mapping_path: str = None, category_map: dict = None):
        self.products_path = products_path or DCLINK_PRODUCTS_PATH
        self.categories_path = categories_path or DCLINK_CATEGORIES_PATH
        self.category_mapping_path = category_mapping_path or CATEGORY_MAPPING_PATH
        self.stats = ImportStats()

        # DB-derived map (global + supplier overrides) takes priority;
        # legacy JSON file is the fallback when the DB has no rules.
        if category_map:
            self.category_map = dict(category_map)
        else:
            with open(self.category_mapping_path, "r", encoding="utf-8") as f:
                self.category_map = json.load(f)
        
        with open(self.categories_path, "r", encoding="utf-8") as f:
            self.dc_categories = json.load(f)
        
        # Build DC-Link category ID → name map
        self.dc_cat_map = {}
        for c in self.dc_categories:
            cid = str(c.get("categoryID", ""))
            cname = c.get("name", "")
            if cid:
                self.dc_cat_map[cid] = cname
    
    def _apply_markup(self, price_uah: float) -> int:
        """Apply tiered markup rules (same as legacy)."""
        for threshold, multiplier in self.MARKUP_RULES:
            if price_uah <= threshold:
                return round(price_uah * multiplier)
        return round(price_uah * self.MARKUP_RULES[-1][1])
    
    def download_feed(self) -> List[dict]:
        """Load JSON feed from cache."""
        if not os.path.exists(self.products_path):
            raise FileNotFoundError(f"DC-Link products not found: {self.products_path}")
        with open(self.products_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def parse_products(self, feed: List[dict]) -> List[NormalizedProduct]:
        """Parse all products from JSON feed."""
        self.stats.total_items = len(feed)
        products = []
        seen_skus = set()
        
        for item in feed:
            try:
                product = self._parse_product(item)
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
                self.stats.errors.append({
                    "sku": str(item.get("articul", "unknown")),
                    "error": str(e),
                })
        
        return products
    
    def _parse_product(self, item: dict) -> Optional[NormalizedProduct]:
        """Parse a single product from JSON."""
        articul = str(item.get("articul", "")).strip()
        if not articul:
            self.stats.empty_skus += 1
            return None
        
        sku = f"{self.SKU_PREFIX}{articul}"
        name = item.get("name", "").strip()
        if not name:
            return None
        
        description = item.get("description", "").strip() or item.get("brief_description", "").strip()
        brief = item.get("brief_description", "").strip()
        
        # Price
        price_uah = item.get("price_uah", 0)
        if isinstance(price_uah, str):
            try:
                price_uah = float(price_uah)
            except ValueError:
                price_uah = 0
        
        price = self._apply_markup(price_uah)
        
        # Category
        category_id = str(item.get("categoryID", "")).strip()
        dc_cat_name = self.dc_cat_map.get(category_id, "")
        
        try:
            category_path = resolve_category_path(dc_cat_name, self.category_map)
        except (ValueError, KeyError) as e:
            self.stats.unknown_categories.append(f"'{dc_cat_name}' (dc_id={category_id}): {e}")
            self.stats.failed += 1
            return None
        
        # Images
        images = []
        for img_key in ["full_image", "large_image", "medium_image", "small_image"]:
            img_url = item.get(img_key, "")
            if img_url:
                images.append(img_url)
        # Also check 'images' key for additional images
        extra_images = item.get("images", [])
        if isinstance(extra_images, list):
            for img in extra_images:
                if isinstance(img, dict):
                    url = img.get("url", "") or img.get("image", "") or img.get("full_image", "")
                    if url and url not in images:
                        images.append(url)
                elif isinstance(img, str) and img not in images:
                    images.append(img)
        
        # Stock
        stocks = item.get("stocks", [])
        in_stock = bool(stocks) and any(s is not None for s in stocks)
        
        # Attributes
        raw_options = item.get("options") or []
        raw_attributes = []
        for opt in raw_options:
            opt_name = (opt.get("OptionName") or "").strip()
            opt_value = (opt.get("ValueName") or "").strip()
            if opt_name and opt_value:
                raw_attributes.append((opt_name, opt_value))
        
        # Process through mapping pipeline
        processed_attrs, unknown_names, unknown_values = self._process_attributes(raw_attributes)
        merged_attrs = merge_attributes(processed_attrs)
        merged_attrs_list = list(merged_attrs.items())
        
        # Build product dict for SEO
        product_dict = {
            "Name": name,
            "Regular price": price,
            "Brand": "",
        }
        seo = generate_product_seo(product_dict)
        
        product = NormalizedProduct(
            supplier_sku=articul,
            sku=sku,
            name=name,
            description=description,
            short_description=brief,
            price=price,
            category_path=category_path,
            images=images,
            in_stock=in_stock,
            attributes=merged_attrs_list,
            raw_attributes=raw_attributes,
            seo_title=seo.get("seo_title", ""),
            seo_description=seo.get("meta_description", ""),
            focus_keyphrase=seo.get("focus_keyphrase", ""),
        )
        
        self.stats.unknown_attributes.extend(unknown_names)
        self.stats.unknown_attribute_values.extend(unknown_values)
        
        return product
    
    def _process_attributes(
        self, raw_attrs: List[Tuple[str, str]]
    ) -> Tuple[List[Tuple[str, str]], List[Tuple], List[Tuple]]:
        """Process raw attributes through mapping pipeline."""
        processed = []
        unknown_names = []
        unknown_values = []
        
        for name, value in raw_attrs:
            result = process_attribute(name, value)
            
            if isinstance(result, tuple) and len(result) == 2:
                processed.append(result)
            elif result == ATTR_SKIP:
                pass
            elif result == ATTR_UNKNOWN_NAME:
                unknown_names.append((name, name, ""))
            elif result == ATTR_UNKNOWN_VALUE:
                unknown_values.append((name, value, ""))
        
        return processed, unknown_names, unknown_values
    
    def run(self, import_type: str = "full") -> ImportStats:
        """Run the full import pipeline."""
        feed = self.download_feed()
        products = self.parse_products(feed)
        return self.stats


# CLI entry point for testing
if __name__ == "__main__":
    importer = DCLinkImporter()
    stats = importer.run()
    print(f"\nDC-Link Import Results:")
    print(f"  Total items: {stats.total_items}")
    print(f"  Processed: {stats.processed}")
    print(f"  Failed: {stats.failed}")
    print(f"  Empty SKUs: {stats.empty_skus}")
    print(f"  Duplicate SKUs: {stats.duplicate_skus}")
    print(f"  Unknown categories: {len(stats.unknown_categories)}")
    print(f"  Unknown attributes: {len(stats.unknown_attributes)}")
    print(f"  Unknown attribute values: {len(stats.unknown_attribute_values)}")
    
    for pc in stats.unknown_categories[:10]:
        print(f"  Unknown category: {pc}")
