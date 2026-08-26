"""Channel product validation service.

Determines whether a product is exportable to a given external channel
(e.g. Rozetka).  Returns a structured result with:
  - ready: True/False
  - issues: list of {code, severity, message, details}
"""

import hashlib
import json
from typing import Any

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB
from app.channels.mapping_resolver import ChannelMappingResolver

ISSUE_MISSING_CATEGORY_MAPPING = "MISSING_CATEGORY_MAPPING"
ISSUE_MISSING_ATTRIBUTE_MAPPING = "MISSING_ATTRIBUTE_MAPPING"
ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING = "MISSING_ATTRIBUTE_VALUE_MAPPING"
ISSUE_MISSING_REQUIRED_ATTRIBUTE = "MISSING_REQUIRED_ATTRIBUTE"
ISSUE_INVALID_ATTRIBUTE_VALUE = "INVALID_ATTRIBUTE_VALUE"
ISSUE_MISSING_TITLE = "MISSING_TITLE"
ISSUE_MISSING_DESCRIPTION = "MISSING_DESCRIPTION"
ISSUE_MISSING_PRICE = "MISSING_PRICE"
ISSUE_INVALID_PRICE = "INVALID_PRICE"
ISSUE_MISSING_IMAGE = "MISSING_IMAGE"
ISSUE_INVALID_IMAGE_URL = "INVALID_IMAGE_URL"
ISSUE_HTTP_IMAGE_URL = "HTTP_IMAGE_URL"
ISSUE_PRODUCT_NOT_PUBLISHED = "PRODUCT_NOT_PUBLISHED"
ISSUE_MISSING_BRAND = "MISSING_BRAND"
ISSUE_MISSING_STOCK = "MISSING_STOCK"
ISSUE_NO_TAXONOMY = "NO_TAXONOMY"
ISSUE_MISSING_REQUIRED_ATTR_MAPPING = "MISSING_REQUIRED_ATTR_MAPPING"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"



def _load_product_data(cur, product_id: int) -> dict | None:
    """Load a product and its relations from the catalog."""
    cur.execute(
        """SELECT id, name, description, short_description, slug, price, currency,
                  stock_qty, stock_status, is_active, is_visible, status,
                  brand_id, sku, supplier_sku
           FROM products WHERE id = %s""",
        (product_id,),
    )
    product = cur.fetchone()
    if not product:
        return None
    product = dict(product)
    cur.execute(
        """SELECT pc.category_id, c.name AS category_name
           FROM product_categories pc JOIN categories c ON c.id = pc.category_id
           WHERE pc.product_id = %s""",
        (product_id,),
    )
    product["categories"] = cur.fetchall()
    cur.execute(
        """SELECT pa.attribute_id, a.name AS attr_name, a.slug AS attr_slug,
                  pa.attribute_value_id, pa.value_text,
                  av.value AS attr_value_name
           FROM product_attributes pa
           JOIN attributes a ON a.id = pa.attribute_id
           LEFT JOIN attribute_values av ON av.id = pa.attribute_value_id
           WHERE pa.product_id = %s""",
        (product_id,),
    )
    product["attributes"] = cur.fetchall()
    cur.execute(
        """SELECT id, url, path, alt, sort_order, is_primary, is_suppressed
           FROM product_images WHERE product_id = %s ORDER BY sort_order ASC""",
        (product_id,),
    )
    product["images"] = cur.fetchall()
    if product["brand_id"]:
        cur.execute("SELECT id, name, slug FROM brands WHERE id = %s", (product["brand_id"],))
        product["brand"] = cur.fetchone()
    else:
        product["brand"] = None
    return product


def _get_channel_id(cur, channel_code: str) -> int | None:
    cur.execute("SELECT id FROM channels WHERE code = %s", (channel_code,))
    row = cur.fetchone()
    return row["id"] if row else None


def _get_external_category_id(resolver: ChannelMappingResolver, product: dict) -> str | None:
    for cat in product.get("categories", []):
        mapping = resolver.resolve_category(cat["category_id"])
        if mapping and mapping.get("external_category_id"):
            return mapping["external_category_id"]
    return None


def _get_required_attributes(cur, channel_id: int, external_category_id: str) -> list[dict]:
    cur.execute(
        """SELECT external_id, name, param_type, is_required, unit
           FROM channel_external_attributes
           WHERE channel_id = %s AND category_external_id = %s AND is_required = 1""",
        (channel_id, external_category_id),
    )
    return cur.fetchall()


def validate_product(product_id: int, channel_code: str = "rozetka",
                     public_base_url: str | None = None) -> dict:
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        return _validate(cur, product_id, channel_code, public_base_url)
    finally:
        conn.close()


def _validate(cur, product_id: int, channel_code: str = "rozetka",
              public_base_url: str | None = None) -> dict:
    issues: list[dict] = []
    product = _load_product_data(cur, product_id)
    if product is None:
        return {"ready": False, "issues": [{
            "code": "PRODUCT_NOT_FOUND", "severity": SEVERITY_ERROR,
            "message": f"Товар з ID {product_id} не знайдено",
            "details": {},
        }]}
    channel_id = _get_channel_id(cur, channel_code)
    if channel_id is None:
        return {"ready": False, "issues": [{
            "code": "CHANNEL_NOT_FOUND", "severity": SEVERITY_ERROR,
            "message": f"Канал {channel_code} не знайдено",
            "details": {},
        }]}
    resolver = ChannelMappingResolver(channel_id=channel_id, channel_code=channel_code)
    ready = True
    if product["status"] != "PUBLISHED":
        issues.append({"code": ISSUE_PRODUCT_NOT_PUBLISHED, "severity": SEVERITY_ERROR,
                        "message": "Товар не опубліковано у внутрішньому каталозі",
                        "details": {"status": product["status"]}})
        ready = False
    title = (product.get("name") or "").strip()
    if not title:
        issues.append({"code": ISSUE_MISSING_TITLE, "severity": SEVERITY_ERROR,
                        "message": "Відсутня назва товару", "details": {}})
        ready = False
    desc = (product.get("description") or "").strip()
    if not desc:
        issues.append({"code": ISSUE_MISSING_DESCRIPTION, "severity": SEVERITY_WARNING,
                        "message": "Відсутній опис товару", "details": {}})
    price = product.get("price") or 0
    if price <= 0:
        issues.append({"code": ISSUE_MISSING_PRICE, "severity": SEVERITY_ERROR,
                        "message": "Відсутня або нульова ціна",
                        "details": {"price": price}})
        ready = False
    stock_qty = product.get("stock_qty") or 0
    stock_status = product.get("stock_status") or ""
    if stock_qty <= 0 and stock_status not in ("in_stock", "on_backorder"):
        issues.append({"code": ISSUE_MISSING_STOCK, "severity": SEVERITY_WARNING,
                        "message": "Товар відсутній на складі",
                        "details": {"stock_qty": stock_qty, "stock_status": stock_status}})
    if not product.get("brand"):
        issues.append({"code": ISSUE_MISSING_BRAND, "severity": SEVERITY_WARNING,
                        "message": "Відсутній бренд", "details": {}})
    images = product.get("images") or []
    active_images = [img for img in images if not img["is_suppressed"]]
    if not active_images:
        issues.append({"code": ISSUE_MISSING_IMAGE, "severity": SEVERITY_ERROR,
                        "message": "Відсутні зображення товару", "details": {}})
        ready = False
    else:
        for img in active_images:
            url = img["url"] or ""
            if url.startswith("/media/") and not public_base_url:
                issues.append({"code": ISSUE_INVALID_IMAGE_URL, "severity": SEVERITY_WARNING,
                                "message": "Налаштуйте публічний BASE_URL",
                                "details": {"url": url}})
                break
            if url.startswith("http://"):
                issues.append({"code": ISSUE_HTTP_IMAGE_URL, "severity": SEVERITY_WARNING,
                                "message": "Зображення використовує HTTP замість HTTPS",
                                "details": {"url": url}})
    ext_cat_id = _get_external_category_id(resolver, product)
    if ext_cat_id is None:
        issues.append({"code": ISSUE_MISSING_CATEGORY_MAPPING, "severity": SEVERITY_ERROR,
                        "message": "Не знайдено відповідності категорії для каналу",
                        "details": {"internal_categories": [
                            {"id": c["category_id"], "name": c["category_name"]}
                            for c in product.get("categories", [])]}})
        ready = False
    for pa in product.get("attributes") or []:
        attr_id = pa["attribute_id"]
        attr_name = pa["attr_name"]
        attr_mapping = resolver.resolve_attribute(attr_id, ext_cat_id)
        if attr_mapping is None:
            issues.append({"code": ISSUE_MISSING_ATTRIBUTE_MAPPING, "severity": SEVERITY_ERROR,
                            "message": f"Не знайдено відповідності атрибута {attr_name}",
                            "details": {"attribute_id": attr_id, "attribute_name": attr_name}})
            ready = False
            continue
        if pa["attribute_value_id"]:
            val_mapping = resolver.resolve_value(pa["attribute_value_id"], ext_cat_id)
            if val_mapping is None:
                val_name = pa.get("attr_value_name") or f"id={pa['attribute_value_id']}"
                issues.append({"code": ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING,
                                "severity": SEVERITY_ERROR,
                                "message": f"Не знайдено відповідності значення {attr_name}: {val_name}",
                                "details": {"attribute_id": attr_id, "attribute_name": attr_name,
                                            "attribute_value_id": pa["attribute_value_id"],
                                            "value_name": val_name}})
                ready = False
    if ext_cat_id:
        required_attrs = _get_required_attributes(cur, channel_id, ext_cat_id)
        if required_attrs:
            for req in required_attrs:
                mapped_found = False
                for pa in product.get("attributes") or []:
                    attr_map = resolver.resolve_attribute(pa["attribute_id"], ext_cat_id)
                    if attr_map and attr_map.get("external_attribute_id") == req["external_id"]:
                        mapped_found = True
                        break
                if not mapped_found:
                    issues.append({"code": ISSUE_MISSING_REQUIRED_ATTR_MAPPING,
                                    "severity": SEVERITY_ERROR,
                                    "message": f"Відсутній обов’язковий атрибут {req['name']}",
                                    "details": {"external_attribute_id": req["external_id"],
                                                "external_attribute_name": req["name"],
                                                "external_category_id": ext_cat_id}})
                    ready = False
    return {"ready": ready, "issues": issues}


def compute_content_hash(product: dict, resolver: ChannelMappingResolver,
                          ext_cat_id: str | None,
                          public_base_url: str | None = None) -> str:
    payload = _build_transform_payload(product, resolver, ext_cat_id, public_base_url)
    content = {
        "title": payload.get("title"),
        "description": payload.get("description"),
        "brand": payload.get("brand"),
        "category": payload.get("category"),
        "attributes": payload.get("attributes", []),
        "images": [img["url"] for img in payload.get("images", [])],
    }
    raw = json.dumps(content, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_commercial_hash(product: dict) -> str:
    commercial = {
        "price": product.get("price"),
        "stock_qty": product.get("stock_qty"),
        "stock_status": product.get("stock_status"),
        "currency": product.get("currency"),
    }
    raw = json.dumps(commercial, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_transform_payload(product: dict, resolver: ChannelMappingResolver,
                              ext_cat_id: str | None,
                              public_base_url: str | None = None) -> dict:
    title = (product.get("name") or "").strip()
    description = (product.get("description") or "").strip()
    brand_name = product["brand"]["name"] if product.get("brand") else None
    category = None
    if ext_cat_id:
        for cat in product.get("categories") or []:
            cm = resolver.resolve_category(cat["category_id"])
            if cm:
                category = {"external_id": cm.get("external_category_id"),
                            "name": cm.get("external_category_name")}
                break
    transformed_attrs = []
    for pa in product.get("attributes") or []:
        attr_mapping = resolver.resolve_attribute(pa["attribute_id"], ext_cat_id)
        if attr_mapping is None:
            continue
        entry = {"external_attribute_id": attr_mapping.get("external_attribute_id"),
                 "external_attribute_name": attr_mapping.get("external_attribute_name")}
        if pa["attribute_value_id"]:
            val_mapping = resolver.resolve_value(pa["attribute_value_id"], ext_cat_id)
            if val_mapping:
                entry["external_value_id"] = val_mapping.get("external_value_id")
                entry["value"] = val_mapping.get("external_value_name")
            else:
                entry["value"] = pa.get("attr_value_name") or ""
        elif pa["value_text"]:
            # Try to resolve via the value_text bridge (attribute_values -> mappings)
            val_mapping = resolver.resolve_value_by_text(
                pa["attribute_id"], pa["value_text"], ext_cat_id,
            )
            if val_mapping:
                entry["external_value_id"] = val_mapping.get("external_value_id")
                entry["value"] = val_mapping.get("external_value_name")
            else:
                entry["value"] = pa["value_text"]
        transformed_attrs.append(entry)
    transformed_images = []
    for img in product.get("images") or []:
        if img.get("is_suppressed"):
            continue
        url = img["url"] or ""
        if url.startswith("/media/") and public_base_url:
            url = public_base_url.rstrip("/") + url
        transformed_images.append({
            "url": url, "alt": img.get("alt") or "",
            "sort_order": img.get("sort_order") or 0,
            "is_primary": bool(img.get("is_primary")),
        })
    return {
        "product_id": product["id"],
        "sku": product.get("sku") or product.get("supplier_sku") or "",
        "title": title, "description": description, "brand": brand_name,
        "category": category, "attributes": transformed_attrs,
        "images": transformed_images,
        "price": product.get("price") or 0,
        "currency": product.get("currency") or "UAH",
        "stock_qty": product.get("stock_qty") or 0,
        "stock_status": product.get("stock_status") or "out_of_stock",
    }
