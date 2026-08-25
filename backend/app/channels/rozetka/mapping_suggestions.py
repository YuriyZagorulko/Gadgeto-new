"""Mapping suggestion engine for Rozetka channel.

Generates suggested mappings from internal catalog entities to Rozetka
taxonomy entities using deterministic matching.

Suggestion priority:
  1. Exact name match (after normalization)
  2. High-confidence normalized match (case/whitespace/punctuation)
  3. Medium-confidence fuzzy match
  4. No suggestion (low confidence)

Value matching is stricter than category/attribute matching.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = text.replace("'", "").replace("\u02bc", "").replace("`", "").replace("\u2019", "")
    text = text.replace('"', '').replace("\u00ab", "").replace("\u00bb", "")
    text = text.replace("-", " ").replace("\u2014", " ").replace("\u2013", " ")
    text = re.sub(r'[^a-z\u0430-\u044f\u0456\u0457\u0454\u0491\u0451\u0435\u0438\u0439\u043a\u043b\u043c\u043d\u043e\u043f\u0440\u0441\u0442\u0443\u0444\u0445\u0446\u0447\u0448\u0449\u044a\u044b\u044c\u044d\u044e\u044f0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _suggest_categories(cur, channel_id: int, internal_cat_id: int) -> list[dict]:
    cur.execute("SELECT name FROM categories WHERE id = %s", (internal_cat_id,))
    cat = cur.fetchone()
    if not cat:
        return []
    internal_name = cat["name"]
    internal_norm = _normalize(internal_name)
    suggestions = []
    cur.execute(
        "SELECT external_id, name FROM channel_external_categories WHERE channel_id = %s",
        (channel_id,),
    )
    for row in cur.fetchall():
        ext_name = row["name"] or ""
        ext_norm = _normalize(ext_name)
        if not ext_norm:
            continue
        if ext_norm == internal_norm:
            suggestions.append({"external_id": row["external_id"], "external_name": ext_name,
                                "confidence": 1.0, "method": "exact"})
            continue
        sim = _similarity(ext_norm, internal_norm)
        if sim >= 0.85:
            suggestions.append({"external_id": row["external_id"], "external_name": ext_name,
                                "confidence": round(sim, 4), "method": "fuzzy_high"})
        elif sim >= 0.65:
            suggestions.append({"external_id": row["external_id"], "external_name": ext_name,
                                "confidence": round(sim, 4), "method": "fuzzy_medium"})
    suggestions.sort(key=lambda x: -x["confidence"])
    return suggestions[:5]


def _suggest_attributes(cur, channel_id: int, internal_attr_id: int,
                        ext_cat_id: Optional[str] = None) -> list[dict]:
    cur.execute("SELECT name FROM attributes WHERE id = %s", (internal_attr_id,))
    attr = cur.fetchone()
    if not attr:
        return []
    internal_name = attr["name"]
    internal_norm = _normalize(internal_name)
    suggestions = []
    query = "SELECT external_id, name FROM channel_external_attributes WHERE channel_id = %s"
    params = [channel_id]
    if ext_cat_id:
        query += " AND (category_external_id = %s OR is_global = 1)"
        params.append(ext_cat_id)
    cur.execute(query, params)
    for row in cur.fetchall():
        ext_name = row["name"] or ""
        ext_norm = _normalize(ext_name)
        if not ext_norm:
            continue
        if ext_norm == internal_norm:
            suggestions.append({"external_id": row["external_id"], "external_name": ext_name,
                                "confidence": 1.0, "method": "exact"})
            continue
        sim = _similarity(ext_norm, internal_norm)
        if sim >= 0.80:
            suggestions.append({"external_id": row["external_id"], "external_name": ext_name,
                                "confidence": round(sim, 4), "method": "fuzzy_high"})
        elif sim >= 0.60:
            suggestions.append({"external_id": row["external_id"], "external_name": ext_name,
                                "confidence": round(sim, 4), "method": "fuzzy_medium"})
    suggestions.sort(key=lambda x: -x["confidence"])
    return suggestions[:5]


def _suggest_values(cur, channel_id: int, internal_value_id: int,
                    ext_attr_id: Optional[str] = None,
                    ext_cat_id: Optional[str] = None) -> list[dict]:
    cur.execute("SELECT value FROM attribute_values WHERE id = %s", (internal_value_id,))
    val = cur.fetchone()
    if not val:
        return []
    internal_value = val["value"]
    internal_norm = _normalize(internal_value)
    suggestions = []
    query = "SELECT external_id, value, attribute_external_id FROM channel_external_values WHERE channel_id = %s"
    params = [channel_id]
    if ext_attr_id:
        query += " AND attribute_external_id = %s"
        params.append(ext_attr_id)
    cur.execute(query, params)
    for row in cur.fetchall():
        ext_value = row["value"] or ""
        ext_norm = _normalize(ext_value)
        if not ext_norm:
            continue
        if ext_norm == internal_norm:
            suggestions.append({"external_id": row["external_id"], "external_value": ext_value,
                                "attribute_external_id": row["attribute_external_id"],
                                "confidence": 1.0, "method": "exact"})
            continue
        sim = _similarity(ext_norm, internal_norm)
        if sim >= 0.90:
            suggestions.append({"external_id": row["external_id"], "external_value": ext_value,
                                "attribute_external_id": row["attribute_external_id"],
                                "confidence": round(sim, 4), "method": "fuzzy_high"})
    suggestions.sort(key=lambda x: -x["confidence"])
    return suggestions[:5]


def suggest_mappings(channel_id: int, kind: str, internal_id: int,
                     ext_cat_id: Optional[str] = None,
                     ext_attr_id: Optional[str] = None) -> list[dict]:
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if kind == "categories":
            return _suggest_categories(cur, channel_id, internal_id)
        elif kind == "attributes":
            return _suggest_attributes(cur, channel_id, internal_id, ext_cat_id)
        elif kind == "values":
            return _suggest_values(cur, channel_id, internal_id, ext_attr_id, ext_cat_id)
        return []
    finally:
        conn.close()
