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
ISSUE_EMPTY_PARAMS = "EMPTY_PARAMS"
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
# Phase 6.5: strict leaf category validation for Rozetka export
# Non-leaf / parent Rozetka categories can NEVER be used for export.
ROZETKA_CATEGORY_NOT_LEAF = "ROZETKA_CATEGORY_NOT_LEAF"
# Phase 6.3: export-settings driven exclusion (stock rules).  Only reported
# when an ExportSettings dict is passed; keeps validate_product() backwards
# compatible.
ISSUE_EXCLUDED_BY_STOCK_RULE = "EXCLUDED_BY_STOCK_RULE"

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
    """Return the characteristics that genuinely block export for a category.

    The Rozetka API exposes NO "required" field for category characteristics
    (verified across all cached taxonomy responses).  The historical
    ``is_required=1`` rows came from a sync bug that treated
    ``filter_type="main"`` — a UI filter-grouping flag — as obligatoriness.
    The sync no longer sets the flag and the cached value is informational
    only, so this provider deliberately returns [] WITHOUT querying the
    database: optional characteristics can never block an export.

    The blocking logic in ``_validate`` (MISSING_REQUIRED_ATTR_MAPPING,
    ERROR-severity value mapping, EMPTY_PARAMS) still honours a non-empty
    result, which keeps the semantics correct for future channels that do
    expose a real required flag (see regression tests).
    """
    return []


# List/select characteristics require an external value ID in the payload;
# text/decimal/integer characteristics pass through the raw value instead.
_SELECT_PARAM_TYPES = frozenset({
    "list", "listvalues", "combobox", "checkboxgroup", "checkboxgroupvalues",
})


def _would_produce_empty_params(cur, channel_id: int, ext_cat_id: str,
                                resolver: ChannelMappingResolver,
                                product: dict) -> bool:
    """True when the Rozetka ``params`` list for this product would be empty.

    Mirrors ``rozetka.payload._build_params``: a product attribute contributes a
    param only when it has an accepted category mapping AND the resulting
    characteristic is buildable.  List/select characteristics require an
    external value ID (missing value mappings are skipped); text/decimal/integer
    characteristics pass through the raw value string.  When every mapped
    attribute is skipped, the payload's ``params`` is ``[]`` and the Rozetka API
    rejects the item.
    """
    specs: dict[str, str] = {}
    cur.execute(
        "SELECT external_id, param_type FROM channel_external_attributes "
        "WHERE channel_id=%s AND category_external_id=%s",
        (channel_id, str(ext_cat_id)),
    )
    for row in cur.fetchall():
        specs[str(row["external_id"])] = (row["param_type"] or "").strip().lower()
    for pa in product.get("attributes") or []:
        attr_mapping = resolver.resolve_attribute(pa["attribute_id"], ext_cat_id)
        if attr_mapping is None:
            continue
        ext_attr_id = str(attr_mapping.get("external_attribute_id") or "")
        if not ext_attr_id:
            continue
        ptype = specs.get(ext_attr_id, "")
        external_value_id = None
        if pa.get("attribute_value_id"):
            val_mapping = resolver.resolve_value(pa["attribute_value_id"], ext_cat_id)
            if val_mapping:
                external_value_id = val_mapping.get("external_value_id")
        elif pa.get("value_text"):
            val_mapping = resolver.resolve_value_by_text(
                pa["attribute_id"], pa["value_text"], ext_cat_id,
            )
            if val_mapping:
                external_value_id = val_mapping.get("external_value_id")
        if ptype in _SELECT_PARAM_TYPES and external_value_id is None:
            # Select/list characteristic without a value mapping is omitted
            # from the payload — contributes nothing.
            continue
        return False
    return True
def validate_product(product_id: int, channel_code: str = "rozetka",
                     public_base_url: str | None = None,
                     export_settings: dict | None = None) -> dict:
    """Validate a product for export.

    When `export_settings` is provided (loaded via
    app.channels.export_settings.load_export_settings), stock-rule
    exclusions are reported as blocking issues so preview and real export
    share one decision path.
    """
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        return _validate(cur, product_id, channel_code, public_base_url,
                         export_settings=export_settings)
    finally:
        conn.close()


def _validate(cur, product_id: int, channel_code: str = "rozetka",
              public_base_url: str | None = None,
              export_settings: dict | None = None) -> dict:
    issues: list[dict] = []
    product = _load_product_data(cur, product_id)
    if product is None:
        return {"ready": False, "issues": [{
            "code": "PRODUCT_NOT_FOUND", "severity": SEVERITY_ERROR,
            "message": f"Товар з ID {product_id} не знайдено",
            "details": {},
        }], "sku": "", "name": "", "external_category_id": None}
    channel_id = _get_channel_id(cur, channel_code)
    if channel_id is None:
        return {"ready": False, "issues": [{
            "code": "CHANNEL_NOT_FOUND", "severity": SEVERITY_ERROR,
            "message": f"Канал {channel_code} не знайдено",
            "details": {},
        }], "sku": "", "name": "", "external_category_id": None}
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
    if export_settings is not None:
        from app.channels.export_settings import (
            EXCLUDED_BY_STOCK_RULE,
            stock_exclusion_reason,
        )
        reason = stock_exclusion_reason(stock_qty, export_settings)
        if reason:
            issues.append({
                "code": ISSUE_EXCLUDED_BY_STOCK_RULE,
                "severity": SEVERITY_ERROR,
                "message": reason,
                "details": {"stock_qty": stock_qty,
                            "min_stock_for_export":
                                export_settings.get("min_stock_for_export"),
                            "export_out_of_stock":
                                bool(export_settings.get("export_out_of_stock"))},
            })
            ready = False
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

# Phase 6.5: Strict leaf category validation
    # A Rozetka category can only be exported if it is a LEAF (has no children).
    required_attr_ids: set[str] = set()
    taxonomy_ok = True
    if ext_cat_id:
        # Get category name for error messages
        cur.execute(
            "SELECT name FROM channel_external_categories "
            "WHERE channel_id=%s AND external_id=%s",
            (channel_id, ext_cat_id),
        )
        ext_cat_row = cur.fetchone()
        cat_name = ext_cat_row["name"] if ext_cat_row else str(ext_cat_id)
        
        # Check if category has children (is a parent / non-leaf)
        cur.execute(
            "SELECT count(*) AS children FROM channel_external_categories "
            "WHERE channel_id=%s AND parent_external_id=%s",
            (channel_id, ext_cat_id),
        )
        has_children = cur.fetchone()["children"] > 0
        
        # STRICT: Non-leaf / parent categories can NEVER be exported
        if has_children:
            issues.append({
                "code": ROZETKA_CATEGORY_NOT_LEAF,
                "severity": SEVERITY_ERROR,
                "message": 'Rozetka category "' + cat_name + '" (' + str(ext_cat_id) + ') is not a leaf category and cannot be exported.',
                "details": {"external_category_id": ext_cat_id, "is_leaf": False},
            })
            ready = False
            taxonomy_ok = False
        else:
            # Leaf category: check if it has attributes for taxonomy completeness
            cur.execute(
                "SELECT count(*) AS attrs FROM channel_external_attributes "
                "WHERE channel_id=%s AND category_external_id=%s",
                (channel_id, ext_cat_id),
            )
            has_attrs = cur.fetchone()["attrs"] > 0
            if not has_attrs:
                # Leaf category but no attributes in taxonomy - incomplete data
                issues.append({
                    "code": ISSUE_NO_TAXONOMY,
                    "severity": SEVERITY_ERROR,
                    "message": f"Rozetka category ({ext_cat_id}) exists but has no attributes in taxonomy.",
                    "details": {"external_category_id": ext_cat_id, "children_count": 0, "attribute_count": 0},
                })
                ready = False
                taxonomy_ok = False
            required_rows = _get_required_attributes(cur, channel_id, ext_cat_id)
            required_attr_ids = {r["external_id"] for r in required_rows}

    # Product attribute loop — required-aware
    for pa in product.get("attributes") or []:
        attr_id = pa["attribute_id"]
        attr_name = pa["attr_name"]
        attr_mapping = resolver.resolve_attribute(attr_id, ext_cat_id)
        if attr_mapping is None:
            # Unmapped internal attribute — don't block.  Concern B (required
            # Rozetka attrs with no internal mapping) catches required cases.
            continue
        # Attribute is mapped.  Check value mapping.
        if pa["attribute_value_id"]:
            val_mapping = resolver.resolve_value(pa["attribute_value_id"], ext_cat_id)
            if val_mapping is None:
                ext_attr_id = attr_mapping.get("external_attribute_id")
                val_name = pa.get("attr_value_name") or f"id={pa['attribute_value_id']}"
                if ext_attr_id and ext_attr_id in required_attr_ids:
                    issues.append({"code": ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING,
                                   "severity": SEVERITY_ERROR,
                                   "message": f"Не знайдено відповідності значення {attr_name}: {val_name}",
                                   "details": {"attribute_id": attr_id, "attribute_name": attr_name,
                                               "attribute_value_id": pa["attribute_value_id"],
                                               "value_name": val_name}})
                    ready = False
                else:
                    # Optional attribute — missing CVM does not block export.
                    # The attribute is simply omitted from the Rozetka payload.
                    issues.append({"code": ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING,
                                   "severity": SEVERITY_WARNING,
                                   "message": f"Не знайдено відповідності значення {attr_name}: {val_name}",
                                   "details": {"attribute_id": attr_id, "attribute_name": attr_name,
                                               "attribute_value_id": pa["attribute_value_id"],
                                               "value_name": val_name}})

    # Concern B: Required Rozetka attributes without any internal mapping.
    # A missing required attribute MUST block the export (ready=False); otherwise
    # _process_product would push an item whose params are incomplete/empty and
    # the Rozetka API would reject it after a wasted round-trip.
    missing_required = False
    if ext_cat_id and taxonomy_ok and required_attr_ids:
        for req_ext_id in required_attr_ids:
            mapped_found = False
            for pa in product.get("attributes") or []:
                attr_map = resolver.resolve_attribute(pa["attribute_id"], ext_cat_id)
                if attr_map and attr_map.get("external_attribute_id") == req_ext_id:
                    mapped_found = True
                    break
            if not mapped_found:
                missing_required = True
                issues.append({"code": ISSUE_MISSING_REQUIRED_ATTR_MAPPING,
                                "severity": SEVERITY_ERROR,
                                "message": f"Відсутній обов'язковий атрибут {req_ext_id}",
                                "details": {"external_attribute_id": req_ext_id,
                                            "external_category_id": ext_cat_id}})
                ready = False

    # Concern C: EMPTY_PARAMS.  The Rozetka API rejects items whose
    # characteristics list (params) is empty.  This fires when the product
    # would contribute zero usable params — either because no accepted attribute
    # mappings exist for the category, or every mapped characteristic is a
    # list/select with a missing value mapping.
    # Blocking here prevents the pointless API round-trip that ends in
    # "empty params" rejection.
    if ext_cat_id and taxonomy_ok:
        if _would_produce_empty_params(cur, channel_id, ext_cat_id, resolver,
                                       product):
            # Count internal attributes for richer diagnostics
            pa_count = len(product.get("attributes") or [])
            mapped_count = 0
            only_brand = True
            for pa in product.get("attributes") or []:
                if pa["attribute_id"] != 353:
                    only_brand = False
                if resolver.resolve_attribute(pa["attribute_id"], ext_cat_id):
                    mapped_count += 1
            unmapped = pa_count - mapped_count

            # Build an actionable diagnostic message
            if pa_count == 1 and only_brand:
                detail_msg = (
                    f"товар має лише атрибут \"Бренд\", який передається через поле "
                    f"producer, а не як характеристика (params) — "
                    f"категорія Rozetka ({ext_cat_id}) не містить атрибута \"Бренд\" "
                    f"для params. Додайте інші характеристики товару для експорту"
                )
            elif unmapped > 0 and mapped_count == 0:
                detail_msg = (
                    f"товар має {pa_count} атрибут(ів), "
                    f"жоден з них не має прийнятого відповідності до категорії Rozetka "
                    f"({ext_cat_id}) — перевірте attribute mappings"
                )
            else:
                detail_msg = (
                    f"товар має {pa_count} атрибут(ів), "
                    f"з них {mapped_count} мапповано, {unmapped} не мапповано"
                )

            issues.append({
                "code": ISSUE_EMPTY_PARAMS,
                "severity": SEVERITY_ERROR,
                "message": (f"Категорія Rozetka ({ext_cat_id}) відхиляє товари з порожніми "
                            f"характеристиками (params) — {detail_msg}"),
                "details": {
                    "external_category_id": ext_cat_id,
                    "product_attribute_count": pa_count,
                    "mapped_attribute_count": mapped_count,
                    "unmapped_attribute_count": unmapped,
                    "has_only_brand_attribute": bool(pa_count == 1 and only_brand),
                },
            })
            ready = False
    return {"ready": ready, "issues": issues,
            "sku": product.get("sku") or product.get("supplier_sku") or "",
            "name": title,
            "external_category_id": ext_cat_id}


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
                # Value mapping missing — this attribute has been validated as
                # optional (required-attr values are blocked before reaching
                # transform).  Omit it entirely to avoid PayloadBuildError
                # for select/list types (which require external_value_id).
                # However, for TextInput/Decimal/Integer attributes the raw
                # value_text is valid and should be exported directly.
                if pa.get("value_text"):
                    entry["value"] = pa["value_text"]
                else:
                    continue
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
        "product_status": product.get("status") or "DRAFT",
    }
