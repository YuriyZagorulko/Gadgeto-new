"""Rozetka payload builder (Phase 6.3).

Converts our channel-neutral transformed product into EXACTLY the shapes
documented at the official Rozetka Seller API.
"""

from __future__ import annotations
import logging
from typing import Any, Optional
from app.channels.export_settings import parse_bool, parse_float

logger = logging.getLogger("channels.rozetka.payload")

SELECT_TYPES = {"list", "listvalues", "combobox", "checkboxgroup","checkboxgroupvalues"}
INT_TYPES = {"integer"}
DECIMAL_TYPES = {"decimal"}
BOOL_TYPES = {"checkbox"}
TEXT_TYPES = {"text", "textarea", "textinput"}

class PayloadBuildError(Exception):
    pass

def normalize_param_type(param_type):
    return (param_type or "").strip().lower()

def format_param_value(param_type, *, external_value_id=None, value_name=None, warnings=None):
    t = normalize_param_type(param_type)
    if t in SELECT_TYPES:
        if external_value_id is None:
            raise PayloadBuildError("For list characteristic need Rozetka value ID")
        return [{"id": int(str(external_value_id)), "value": value_name or ""}]
    if t in INT_TYPES:
        n = parse_float(value_name)
        if not value_name or (n == 0.0 and not str(value_name or "").strip("0., ")):
            raise PayloadBuildError("Empty numeric characteristic value")
        return int(round(n))
    if t in DECIMAL_TYPES:
        return parse_float(value_name)
    if t in BOOL_TYPES:
        return parse_bool(value_name)
    if t in TEXT_TYPES:
        return value_name or ""
    if t:
        if warnings is not None:
            warnings.append("Undefined type '%s' - sent as text" % param_type)
        return value_name or ""
    if warnings is not None:
        warnings.append("Type '%s' missing from taxonomy" % param_type)
    return value_name or ""

def _require_category(transformed):
    category = transformed.get("category") or {}
    ext_cat_id = category.get("external_id")
    if not ext_cat_id:
        raise PayloadBuildError("No Rozetka external category found")
    try:
        return int(str(ext_cat_id))
    except (TypeError, ValueError) as exc:
        raise PayloadBuildError(f"Bad Rozetka category ID: {ext_cat_id!r}") from exc

def _build_params(transformed, attr_specs, warnings):
    params = []
    for entry in transformed.get("attributes") or []:
        ext_attr_id = str(entry.get("external_attribute_id") or "")
        if not ext_attr_id:
            continue
        spec = attr_specs.get(ext_attr_id)
        if spec is None:
            warnings.append("Attr %s missing from local taxonomy - skipped" % ext_attr_id)
            continue
        ptype = spec.get("type")
        try:
            formatted = format_param_value(ptype, external_value_id=entry.get("external_value_id"), value_name=entry.get("value"), warnings=warnings)
        except PayloadBuildError as exc:
            raise PayloadBuildError("Attr '%s': %s" % (entry.get("external_attribute_name") or ext_attr_id, exc)) from exc
        params.append({
            "id": int(ext_attr_id),
            "title": entry.get("external_attribute_name") or spec.get("name") or "",
            "type": ptype,
            "value": formatted,
        })
    return params

def _pictures(transformed):
    pictures = []
    for img in transformed.get("images") or []:
        url = (img.get("url") or "").strip()
        if url and url.startswith(("http://", "https://")):
            pictures.append({"link": url})
    if not pictures:
        raise PayloadBuildError("No public images (need http/https URL)")
    return pictures

def build_create_payload(transformed, attr_specs):
    warnings = []
    title = (transformed.get("title") or "").strip()
    if not title:
        raise PayloadBuildError("Missing product title")
    description = (transformed.get("description") or "").strip()
    stock_qty = int(transformed.get("stock_qty") or 0)
    export_price = transformed.get("export_price")
    base_price = transformed.get("price") or 0
    price_value = export_price if export_price is not None else base_price
    price = int(round(parse_float(price_value)))
    if price <= 0:
        raise PayloadBuildError(f"Invalid export price: {price}")
    producer = None
    brand = (transformed.get("brand") or "").strip()
    if brand:
        producer = {"id": 0, "title": brand}
    payload = {
        "name": title, "name_ua": title,
        "category_id": _require_category(transformed),
        "price": price, "stock_quantity": stock_qty,
        "pictures": _pictures(transformed),
    }
    sku = (transformed.get("sku") or "").strip()
    if sku:
        payload["article"] = sku
    if description:
        payload["description"] = description
        payload["description_ua"] = description
    if producer:
        payload["producer"] = producer
    payload["available"] = stock_qty > 0
    params = _build_params(transformed, attr_specs, warnings)
    # Rozetka requires the params field to exist even if empty
    payload["params"] = params
    return payload, warnings

def build_basic_data_item(external_ref, transformed, attr_specs, include_category=False):
    warnings = []
    title = (transformed.get("title") or "").strip()
    if not title:
        raise PayloadBuildError("Missing product title")
    ref_key = None
    if external_ref.get("item_id") is not None:
        ref_key = "item_id"
    elif external_ref.get("rz_item_id") is not None:
        ref_key = "rz_item_id"
    if ref_key is None:
        raise PayloadBuildError("Need item_id or rz_item_id for update")
    item = {ref_key: int(external_ref[ref_key]), "name": title, "name_ua": title}
    description = (transformed.get("description") or "").strip()
    if description:
        item["description"] = description
        item["description_ua"] = description
    brand = (transformed.get("brand") or "").strip()
    if brand:
        item["producer"] = {"id": 0, "title": brand}
    sku = (transformed.get("sku") or "").strip()
    if sku:
        item["article"] = sku
    if include_category and ref_key == "item_id":
        try:
            item["category_id"] = _require_category(transformed)
        except PayloadBuildError:
            warnings.append("Cannot update category - mapping missing")
    item["params"] = _build_params(transformed, attr_specs, warnings)
    item["pictures"] = _pictures(transformed)
    return item, warnings
