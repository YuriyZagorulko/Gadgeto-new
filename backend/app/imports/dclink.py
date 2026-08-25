"""DC-Link supplier importer.

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
from app.imports.pricing_service import (
    calculate_price, calculate_old_price, find_markup_multiplier, get_usd_rate,
)
from app.imports.category_utils import resolve_category_path
from app.imports.import_stats import ImportStats as SharedImportStats
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
class ImportStats(SharedImportStats):
    """DC-Link import statistics. Alias of shared ImportStats (keeps backward
    compatibility for callers that import from dclink module)."""
    pass


class DCLinkImporter:
    SKU_PREFIX = "DCL-"
    SUPPLIER_CODE = "dclink"

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
                "Не налаштовані облікові дані DC-Link. "
                "Встановіть SUPPLIER_DCLINK_LOGIN / SUPPLIER_DCLINK_PASSWORD."
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
            raise RuntimeError(f"Помилка аутентифікації DC-Link: {data}")
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
        """Download full product details (attributes, images, descriptions).

        Uses the proven endpoint from the historical DC-Link integration:
        POST /products/content/{sid}  with comma-separated productIDs.

        Batches up to 500 products per request.
        """
        all_content = []
        batch_size = 500
        total = len(product_ids)

        for i in range(0, total, batch_size):
            batch = product_ids[i:i + batch_size]
            ids_str = ",".join(map(str, batch))

            try:
                response = requests.post(
                    f"{BASE_URL}/products/content/{sid}",
                    json={"lang": "ua", "productIDs": ids_str},
                    headers={"Content-Type": "application/json"},
                    timeout=120,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == 1:
                        fetched = data.get("result")
                        if isinstance(fetched, list):
                            all_content.extend(fetched)
                        else:
                            self.stats.warnings.append(
                                f"Неочікуваний формат відповіді для {len(batch)} продуктів"
                            )
                    else:
                        self.stats.warnings.append(
                            f"Помилка отримання деталей для {len(batch)} продуктів: статус {data.get('status')}"
                        )
                elif response.status_code == 429:
                    # Rate limited — wait and retry once
                    time.sleep(5)
                    try:
                        response = requests.post(
                            f"{BASE_URL}/products/content/{sid}",
                            json={"lang": "ua", "productIDs": ids_str},
                            headers={"Content-Type": "application/json"},
                            timeout=120,
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("status") == 1:
                                fetched = data.get("result")
                                if isinstance(fetched, list):
                                    all_content.extend(fetched)
                    except requests.RequestException:
                        pass
                else:
                    self.stats.warnings.append(
                        f"Не вдалося отримати деталі товарів: HTTP {response.status_code} для {len(batch)} продуктів"
                    )
            except requests.RequestException as e:
                self.stats.warnings.append(
                    f"Не вдалося отримати деталі товарів: {e} для {len(batch)} продуктів"
                )

            time.sleep(0.2)

        return all_content

    def download_feed(self) -> Tuple[list, dict]:
        """Download full catalog via DC-Link API.

        Merges data from two endpoints:
        1. List endpoint: /products/{category_id}/{sid} — provides base product
           data (prices, stocks, names, full_image, etc.)
        2. Content endpoint: /products/content/{sid} — provides enriched data
           (options/attributes, description, additional images, name_ua/name_ru)

        Returns:
            (merged_products_list, dc_cat_map) where each product dict has
            fields from both the list and content endpoints.
        """
        sid = self._login()
        dc_categories = self._get_categories(sid)
        dc_cat_map = {}
        for c in dc_categories:
            cid = c.get("categoryID") or c.get("id")
            cname = c.get("name") or ""
            if cid:
                dc_cat_map[str(cid)] = cname

        # Step 1: Collect all products from the list endpoint (has prices, stock)
        all_product_ids = []
        base_products = {}  # productID -> product dict from list endpoint
        for cat_id in CATEGORY_IDS:
            chunk = self._get_products(sid, cat_id)
            for item in chunk:
                item_id = item.get("productID") or item.get("id")
                if item_id:
                    all_product_ids.append(item_id)
                    base_products[str(item_id)] = item

        # Record how many products the feed listed
        self.stats.feed_count = len(all_product_ids)

        # Step 2: Fetch enriched content from content endpoint (has options, description, images)
        content_list = self._get_products_content(sid, all_product_ids)

        # Step 3: Merge content into base products
        for enriched in content_list:
            pid = enriched.get("productID")
            if pid is None:
                continue
            base = base_products.get(str(pid))
            if base is None:
                # Enriched product not in base list — use as-is
                base_products[str(pid)] = enriched
                continue

            # Merge enriched fields into base product
            # Description from content endpoint
            if enriched.get("description"):
                base["description"] = enriched["description"]
            # Options/attributes from content endpoint
            if enriched.get("options"):
                base["options"] = enriched["options"]
            # Additional images from content endpoint (structured format)
            if enriched.get("images"):
                base["content_images"] = enriched["images"]
            # Name fallback: use name_ua if name is empty
            if not base.get("name") or base.get("name") is None:
                base["name"] = enriched.get("name_ua") or enriched.get("name_ru") or ""
            # Brief description fallback
            if not base.get("brief_description") and enriched.get("brief_description"):
                base["brief_description"] = enriched["brief_description"]

        return list(base_products.values()), dc_cat_map

    def _pick_price(self, item: dict, category_path: str = None) -> int:
        """Pick and calculate the final price in kopecks.

        Priority: price_uah -> price_usd -> 0.
        """
        price_uah = None
        uah_val = item.get("price_uah") or item.get("PriceUAH")
        if uah_val:
            try:
                price_uah = float(uah_val)
            except (ValueError, TypeError):
                pass

        price_usd = None
        if price_uah is None:
            usd_val = item.get("price") or item.get("Price")
            if usd_val:
                try:
                    price_usd = float(usd_val)
                except (ValueError, TypeError):
                    pass

        return calculate_price(
            price_uah=price_uah,
            price_usd=price_usd,
            supplier_code=self.SUPPLIER_CODE,
            category_path=category_path,
        )

    def parse_products(self, feed: list, dc_cat_map: dict):
        """Parse downloaded products, yielding NormalizedProduct one at a time.

        Yields a NormalizedProduct for each valid product.  No full product
        list is retained in memory — the caller must iterate the generator
        to consume products.
        """
        self.stats.total = len(feed)
        seen_skus = set()

        for item in feed:
            articul = str(item.get("articul") or item.get("artikul") or item.get("article") or item.get("sku") or "").strip()
            if not articul:
                self.stats.empty_skus += 1
                continue
            sku = self.SKU_PREFIX + articul

            if sku in seen_skus:
                self.stats.duplicate_skus += 1
                continue
            seen_skus.add(sku)

            name = item.get("name") or item.get("Name") or ""
            category_id = str(item.get("category_id") or item.get("categoryID") or item.get("CategoryId") or "")
            category_name = dc_cat_map.get(category_id, "")

            # Resolve category BEFORE price calculation.
            # Unmapped categories are skipped (not failed).
            try:
                category_path = resolve_category_path(category_name, self.category_map, sku=sku)
            except (ValueError, KeyError) as e:
                self.stats.record_unmapped_category(
                    name=category_name,
                    supplier_category_id=category_id,
                    sku=sku,
                )
                self.stats.skipped += 1
                continue

            price = self._pick_price(item, category_path=category_path)
            images = []
            full_image = item.get("full_image")
            if full_image:
                images.append(str(full_image))
            # Also check for additional images from the content endpoint
            # (structured array of {full_image, small_image, ...} dicts)
            content_images = item.get("content_images") or []
            for im in content_images:
                url = str(im.get("full_image") or im.get("url") or "")
                if url and url not in images:
                    images.append(url)
            other_images = item.get("other_images") or item.get("images") or []
            for im in other_images:
                if isinstance(im, dict):
                    url = str(im.get("url") or im.get("path") or im.get("full_image") or "")
                else:
                    url = str(im)
                if url and url not in images:
                    images.append(url)

            stocks = item.get("stocks", [])
            in_stock = bool(stocks) and any(s is not None for s in stocks)

            raw_options = item.get("options") or []
            raw_attributes = []
            for opt in raw_options:
                opt_name = (opt.get("OptionName") or opt.get("name") or "").strip()
                opt_value = (opt.get("ValueName") or opt.get("value") or "").strip()
                if opt_name and opt_value:
                    raw_attributes.append((opt_name, opt_value))

            raw_attributes = _validate_attributes(raw_attributes, self.stats, sku, "DC-Link")

            processed, unknown_names, unknown_values = self._process_attributes(raw_attributes, sku=sku)

            merged_list = list(merge_attributes(processed).items())

            brief = item.get("brief") or item.get("brief_description") or item.get("short_description") or item.get("ShortDescription") or ""
            description = item.get("description") or item.get("Description") or brief or ""

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
            yield product

    def _process_attributes(self, raw_attrs, sku: str = ""):
        processed = []
        for attr_name, attr_value in raw_attrs:
            result = process_attribute(attr_name, attr_value)
            if isinstance(result, tuple) and len(result) == 2:
                processed.append(result)
            elif result == ATTR_SKIP:
                pass
            elif result == ATTR_UNKNOWN_NAME:
                self.stats.record_unknown_attribute(attr_name, sku=sku)
            elif result == ATTR_UNKNOWN_VALUE:
                self.stats.record_unknown_attribute_value(attr_name, attr_value, sku=sku)
        return processed, [], []

    def run(self, import_type: str = "full") -> ImportStats:
        feed, dc_cat_map = self.download_feed()
        # Store the generator — the caller (importer_service) will iterate it
        # product-by-product, so only one NormalizedProduct is in memory at a time.
        self.stats.products = self.parse_products(feed, dc_cat_map)
        return self.stats
