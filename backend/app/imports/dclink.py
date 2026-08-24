"""
DC-Link supplier importer.

Downloads the current catalog from DC-Link API (cerebro.dclink.ua),
parses it, and returns normalized products for persistence.
"""

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

import requests

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
            safe.append((attr_name, attr_value))
        else:
            safe.append((attr_name, attr_value))
    return safe


BASE_URL = "https://cerebro.dclink.ua"

# Category IDs for the full product catalog
CATEGORY_IDS = [1371, 1379]
PRODUCTS_LIMIT = 1000


@dataclass
class NormalizedProduct:
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
    warnings: List[str] = field(default_factory=list)
    errors: List[dict] = field(default_factory=list)
    products: list = field(default_factory=list)


class DCLinkImporter:
    SKU_PREFIX = "DCL-"
    SUPPLIER_CODE = "dclink"

    MARKUP_RULES = [
        (200, 1.50),
        (500, 1.45),
        (1000, 1.40),
        (3000, 1.35),
        (7000, 1.30),
        (15000, 1.25),
        (float("inf"), 1.20),
    ]

    def __init__(self, feed_path: str = None, categories_path: str = None,
                 category_map: dict = None):
        self.feed_path = feed_path
        self.categories_path = categories_path
        self.stats = ImportStats()
        self.category_map = dict(category_map) if category_map else {}

    def _login(self) -> str:
        """Authenticate with DC-Link API and return session ID."""
        login = settings.SUPPLIER_DCLINK_LOGIN or ""
        password = settings.SUPPLIER_DCLINK_PASSWORD or ""
        if not login or not password:
            raise RuntimeError(
                "\u041d\u0435 \u043d\u0430\u043b\u0430\u0448\u0442\u043e\u0432\u0430\u043d\u0456 \u043e\u0431\u043b\u0456\u043a\u043e\u0432\u0456 \u0434\u0430\u043d\u0456 DC-Link. "
                "\u0412\u0441\u0442\u0430\u043d\u043e\u0432\u0456\u0442\u044c SUPPLIER_DCLINK_LOGIN / SUPPLIER_DCLINK_PASSWORD."
            )
        password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
        response = requests.post(
            f"{BASE_URL}/auth",
            json={"login": login, "password": password_md5},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != 1:
            raise RuntimeError(f"\u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u0430\u0432\u0442\u0435\u043d\u0442\u0438\u0444\u0456\u043a\u0430\u0446\u0456\u0457 DC-Link: {data}")
        return data["result"]

    def _get_categories(self, sid: str) -> List[dict]:
        """Download supplier categories from DC-Link API."""
        response = requests.get(
            f"{BASE_URL}/categories/{sid}",
            params={"lang": "ua"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["result"]

    def _get_products(self, sid: str, category_id: int) -> list:
        """Download products for a category with pagination."""
        products = []
        offset = 0
        while True:
            response = requests.get(
                f"{BASE_URL}/products/{category_id}/{sid}",
                params={"lang": "ua", "limit": PRODUCTS_LIMIT, "offset": offset},
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()["result"]
            chunk = result["list"]
            if not chunk:
                break
            products.extend(chunk)
            if len(chunk) < PRODUCTS_LIMIT:
                break
            offset += PRODUCTS_LIMIT
            time.sleep(0.2)
        return products

    def _get_products_content(self, sid: str, product_ids: list) -> list:
        """Download full product details (attributes, images, descriptions)."""
        all_content = []
        batch_size = 500
        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i:i + batch_size]
            response = requests.post(
                f"{BASE_URL}/products/content/{sid}",
                json={"lang": "ua", "productIDs": ",".join(map(str, batch))},
                headers={"Content-Type": "application/json"},
                timeout=120,
            )
            if response.status_code != 200:
                continue
            data = response.json()
            if data.get("status") == 1:
                all_content.extend(data["result"])
            time.sleep(0.2)
        return all_content

    def download_feed(self) -> tuple:
        """Download the complete DC-Link catalog.
        Returns (products_list, categories_dict).
        """
        sid = self._login()

        categories = self._get_categories(sid)
        cat_dict = {str(c["categoryID"]): c["name"] for c in categories}

        all_products = {}
        for cid in CATEGORY_IDS:
            try:
                products = self._get_products(sid, cid)
                for p in products:
                    all_products[p["productID"]] = p
            except Exception as e:
                self.stats.errors.append({"category_id": cid, "error": str(e)})

        products_list = list(all_products.values())
        product_ids = [p["productID"] for p in products_list]

        content = self._get_products_content(sid, product_ids)
        content_map = {p["productID"]: p for p in content}

        for product in products_list:
            full = content_map.get(product["productID"])
            if full:
                product["description"] = full.get("description")
                product["options"] = full.get("options", [])
                product["images"] = full.get("images", [])

        return products_list, cat_dict

    def _apply_markup(self, price_uah: float) -> int:
        for threshold, multiplier in self.MARKUP_RULES:
            if price_uah <= threshold:
                return round(price_uah * multiplier)
        return round(price_uah * self.MARKUP_RULES[-1][1])

    def _pick_price(self, item: dict) -> int:
        try:
            price_uah = item.get("price_uah")
            if price_uah not in (None, "", 0):
                price = float(price_uah)
            else:
                usd = float(item.get("price", 0))
                if usd <= 0:
                    return 0
                price = usd * 44.3
            if price <= 0:
                return 0
            return self._apply_markup(price)
        except (ValueError, TypeError):
            return 0

    def parse_products(self, feed: list, dc_cat_map: dict) -> List[NormalizedProduct]:
        self.stats.total_items = len(feed)
        products = []
        seen_skus = set()

        for item in feed:
            articul = str(item.get("articul") or "").strip()
            if not articul:
                self.stats.empty_skus += 1
                continue
            sku = self.SKU_PREFIX + articul
            if sku in seen_skus:
                self.stats.duplicate_skus += 1
                continue
            seen_skus.add(sku)

            name = item.get("name") or ""
            description = item.get("description") or ""
            brief = item.get("brief_description") or ""
            price = self._pick_price(item)

            category_id = str(item.get("categoryID") or "").strip()
            category_name = dc_cat_map.get(category_id, "")
            try:
                category_path = resolve_category_path(category_name, self.category_map)
            except (ValueError, KeyError) as e:
                self.stats.unknown_categories.append(f"'{category_name}' (id={category_id}): {e}")
                self.stats.failed += 1
                self.stats.errors.append({"articul": articul, "error": f"\u041d\u0435\u0432\u0456\u0434\u043e\u043c\u0430 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u044f: {category_name}"})
                continue

            images = []
            full_image = item.get("full_image")
            if full_image:
                images.append(str(full_image))
            other_images = item.get("other_images") or item.get("images") or []
            for im in other_images:
                if isinstance(im, dict):
                    url = str(im.get("url") or im.get("path") or "")
                else:
                    url = str(im)
                if url and url not in images:
                    images.append(url)

            stocks = item.get("stocks", [])
            in_stock = bool(stocks) and any(s is not None for s in stocks)

            raw_options = item.get("options") or []
            raw_attributes = []
            for opt in raw_options:
                opt_name = (opt.get("OptionName") or "").strip()
                opt_value = (opt.get("ValueName") or "").strip()
                if opt_name and opt_value:
                    raw_attributes.append((opt_name, opt_value))

            # Core-field protection: prevent attribute names from overwriting core fields
            raw_attributes = _validate_attributes(raw_attributes, self.stats, sku, "DC-Link")

            processed, unknown_names, unknown_values = self._process_attributes(raw_attributes)
            merged_list = list(merge_attributes(processed).items())

            seo = generate_product_seo({"Name": name, "Regular price": price, "Brand": ""})

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

    def _process_attributes(self, raw_attrs):
        processed = []
        unknown_names = []
        unknown_values = []
        for attr_name, attr_value in raw_attrs:
            result = process_attribute(attr_name, attr_value)
            if isinstance(result, tuple) and len(result) == 2:
                processed.append(result)
            elif result == ATTR_SKIP:
                pass
            elif result == ATTR_UNKNOWN_NAME:
                unknown_names.append((attr_name, attr_name, ""))
            elif result == ATTR_UNKNOWN_VALUE:
                unknown_values.append((attr_name, attr_value, ""))
        return processed, unknown_names, unknown_values

    def run(self, import_type: str = "full") -> ImportStats:
        feed, dc_cat_map = self.download_feed()
        self.parse_products(feed, dc_cat_map)
        return self.stats
