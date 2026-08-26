"""Rozetka-specific export validation (Phase 6.4).

Extends the generic channel validation with detailed Rozetka API compatibility
checks: category validity, required attributes, value correctness, type checks,
and payload format verification.
"""

from __future__ import annotations
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from app.channels.mapping_resolver import ChannelMappingResolver
from app.channels.rozetka.payload import (
    PayloadBuildError,
    build_create_payload,
    format_param_value,
    normalize_param_type,
)
from app.channels.validation import (
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    _get_external_category_id,
    _load_product_data,
    _build_transform_payload,
    validate_product as _validate_generic,
)
from app.channels.export_settings import (
    load_export_settings,
    apply_export_settings,
)
from app.core.db_connect import DB


ROZETKA_CATEGORY_INVALID = "ROZETKA_CATEGORY_INVALID"
ROZETKA_CATEGORY_NOT_LEAF = "ROZETKA_CATEGORY_NOT_LEAF"
ROZETKA_REQUIRED_ATTR_MISSING = "ROZETKA_REQUIRED_ATTR_MISSING"
ROZETKA_ATTR_MAPPING_MISSING = "ROZETKA_ATTR_MAPPING_MISSING"
ROZETKA_VALUE_MAPPING_MISSING = "ROZETKA_VALUE_MAPPING_MISSING"
ROZETKA_VALUE_INVALID = "ROZETKA_VALUE_INVALID"
ROZETKA_PARAMS_EMPTY = "ROZETKA_PARAMS_EMPTY"
ROZETKA_PARAM_VALUE_INVALID = "ROZETKA_PARAM_VALUE_INVALID"
ROZETKA_NO_IMAGES = "ROZETKA_NO_IMAGES"
ROZETKA_BRAND_REQUIRED = "ROZETKA_BRAND_REQUIRED"


def validate_rozetka_export(product_id: int,
                              channel_code: str = "rozetka",
                              channel_id: int = 1,
                              public_base_url: str | None = None,
                              export_settings: dict | None = None) -> dict:
    """Comprehensive Rozetka-specific validation for one product."""
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        return _validate_rozetka(cur, product_id, channel_code, channel_id,
                                 public_base_url, export_settings)
    finally:
        conn.close()


def _validate_rozetka(cur, product_id, channel_code, channel_id,
                       public_base_url, export_settings):
    issues = []

    product = _load_product_data(cur, product_id)
    if product is None:
        return {"ready": False, "category": None,
                "required_attributes": {"total": 0, "mapped": 0, "missing": 0},
                "attributes": [],
                "issues": [{"code": "PRODUCT_NOT_FOUND", "severity": SEVERITY_ERROR,
                             "message": f"Product {product_id} not found"}]}

    resolver = ChannelMappingResolver(channel_id=channel_id,
                                       channel_code=channel_code)
    ext_cat_id = _get_external_category_id(resolver, product)

    generic = _validate_generic(product_id, channel_code=channel_code,
                                public_base_url=public_base_url,
                                export_settings=export_settings)
    ready = generic.get("ready", False)

    cat_result = _validate_category(cur, channel_id, resolver, product, ext_cat_id, issues)
    category_info = cat_result.get("result", {})
    if not cat_result.get("valid"):
        ready = False

    attr_specs = {}
    attr_audit = _audit_attributes(cur, channel_id, ext_cat_id, resolver, product,
                                    issues, attr_specs)

    payload_valid, payload_issues, payload_warnings = _validate_payload(
        product, resolver, ext_cat_id, attr_specs, public_base_url, export_settings)
    for pi in payload_issues:
        issues.append(pi)
    if not payload_valid:
        ready = False

    return {
        "ready": ready,
        "category": category_info,
        "required_attributes": {
            "total": attr_audit["total_required"],
            "mapped": attr_audit["mapped_required"],
            "missing": attr_audit["missing_required"],
        },
        "attributes": attr_audit.get("details", []),
        "issues": issues,
        "warnings": payload_warnings,
    }


def _validate_category(cur, channel_id, resolver, product, ext_cat_id, issues):
    result = {"internal_id": None, "internal_name": None,
              "external_id": ext_cat_id, "external_name": None,
              "valid": False}
    for cat in product.get("categories") or []:
        result["internal_id"] = cat["category_id"]
        result["internal_name"] = cat.get("category_name")
        cm = resolver.resolve_category(cat["category_id"])
        if cm:
            result["external_id"] = cm.get("external_category_id")
            result["external_name"] = cm.get("external_category_name")

    if ext_cat_id is None:
        issues.append({"code": ROZETKA_CATEGORY_INVALID,
                        "severity": SEVERITY_ERROR,
                        "message": "No Rozetka category mapping found"})
        return {"valid": False, "result": result}

    cur.execute("SELECT name, parent_external_id FROM channel_external_categories "
                "WHERE channel_id=%s AND external_id=%s", (channel_id, ext_cat_id))
    ext_cat = cur.fetchone()
    if ext_cat is None:
        issues.append({"code": ROZETKA_CATEGORY_INVALID,
                        "severity": SEVERITY_ERROR,
                        "message": f"Rozetka category {ext_cat_id} not in local taxonomy"})
        return {"valid": False, "result": result}
    result["external_name"] = ext_cat["name"]

    cur.execute("SELECT count(*) AS c FROM channel_external_categories "
                "WHERE channel_id=%s AND parent_external_id=%s", (channel_id, ext_cat_id))
    if cur.fetchone()["c"] > 0:
        issues.append({"code": ROZETKA_CATEGORY_NOT_LEAF,
                        "severity": SEVERITY_ERROR,
                        "message": f"Category '{ext_cat['name']}' ({ext_cat_id}) is not a leaf"})
        return {"valid": False, "result": result}

    result["valid"] = True
    return {"valid": True, "result": result}


def _audit_attributes(cur, channel_id, ext_cat_id, resolver, product, issues, attr_specs):
    total_required = 0
    mapped_required = 0
    missing_required = 0
    details = []

    if ext_cat_id is None:
        return {"total_required": 0, "mapped_required": 0,
                "missing_required": 0, "details": []}

    cur.execute("SELECT external_id, name, param_type, is_required, unit "
                "FROM channel_external_attributes "
                "WHERE channel_id=%s AND category_external_id=%s "
                "ORDER BY is_required DESC, name", (channel_id, ext_cat_id))

    for ta in cur.fetchall():
        ext_id = ta["external_id"]
        attr_name = ta["name"]
        param_type = ta["param_type"]
        is_required = bool(ta["is_required"])
        attr_specs[str(ext_id)] = {"name": attr_name, "type": param_type}

        entry = {"external_attribute_id": ext_id, "name": attr_name,
                 "type": param_type, "is_required": is_required,
                 "mapped": False, "has_value": False,
                 "value_valid": None, "issues": []}

        if is_required:
            total_required += 1

        for pa in product.get("attributes") or []:
            attr_map = resolver.resolve_attribute(pa["attribute_id"], ext_cat_id)
            if attr_map and attr_map.get("external_attribute_id") == ext_id:
                entry["mapped"] = True
                if is_required:
                    mapped_required += 1
                if pa["attribute_value_id"]:
                    val_map = resolver.resolve_value(pa["attribute_value_id"], ext_cat_id)
                    if val_map:
                        entry["has_value"] = True
                        try:
                            format_param_value(param_type,
                                external_value_id=val_map.get("external_value_id"),
                                value_name=val_map.get("external_value_name"))
                            entry["value_valid"] = True
                        except PayloadBuildError as exc:
                            entry["value_valid"] = False
                            entry["issues"].append({"code": ROZETKA_VALUE_INVALID,
                                "message": f"Invalid value: {exc}"})
                elif pa.get("value_text"):
                    t = normalize_param_type(param_type)
                    if t in {"integer", "decimal"}:
                        try:
                            float(pa["value_text"].replace(",", "."))
                            entry["has_value"] = True
                        except ValueError:
                            entry["issues"].append({"code": ROZETKA_VALUE_INVALID,
                                "message": f"Text '{pa['value_text']}' not valid for {param_type}"})
                    else:
                        entry["has_value"] = True
                break

        if not entry["mapped"]:
            if is_required:
                missing_required += 1
                entry["issues"].append({"code": ROZETKA_REQUIRED_ATTR_MISSING,
                    "message": f"Required attribute '{attr_name}' has no mapping"})

        for iss in entry["issues"]:
            issues.append({**iss, "severity": SEVERITY_ERROR if is_required else SEVERITY_WARNING,
                           "details": {"external_attribute_id": ext_id}})

        details.append(entry)

    return {"total_required": total_required, "mapped_required": mapped_required,
            "missing_required": missing_required, "details": details}


def _validate_payload(product, resolver, ext_cat_id, attr_specs,
                      public_base_url, export_settings):
    issues = []
    warnings = []

    try:
        transformed = _build_transform_payload(product, resolver, ext_cat_id, public_base_url)
        if export_settings:
            apply_export_settings(transformed, export_settings)

        valid_images = [i for i in (transformed.get("images") or [])
                        if not i.get("is_suppressed")
                        and i.get("url", "").startswith(("http://", "https://"))]
        if not valid_images:
            issues.append({"code": ROZETKA_NO_IMAGES, "severity": SEVERITY_ERROR,
                           "message": "No public http/https images"})

        has_params = any(a.get("external_attribute_id")
                        for a in (transformed.get("attributes") or []))
        if not has_params:
            issues.append({"code": ROZETKA_PARAMS_EMPTY, "severity": SEVERITY_ERROR,
                           "message": "No mapped attributes - Rozetka requires at least one param"})

        build_create_payload(transformed, attr_specs)
        return len(issues) == 0, issues, warnings

    except PayloadBuildError as exc:
        issues.append({"code": "ROZETKA_PAYLOAD_ERROR", "severity": SEVERITY_ERROR,
                       "message": f"Payload build error: {exc}"})
        return False, issues, warnings
    except Exception as exc:
        issues.append({"code": "ROZETKA_PAYLOAD_ERROR", "severity": SEVERITY_ERROR,
                       "message": f"Unexpected error: {exc}"})
        return False, issues, warnings
