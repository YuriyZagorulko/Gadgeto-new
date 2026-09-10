"""Channel export settings — pricing and stock rules (Phase 6.3).

Single source of truth for:
  * loading per-channel export settings from `channel_settings`
  * computing the authoritative export price (markup + rounding)
  * deciding whether a product passes the stock rules
  * Rozetka-specific pricing: category rule → commission, fallback → markup

The SAME functions are used by:
  * POST /export/channels/{code}/export/preview
  * POST /export/channels/{code}/export        (real background run)

The frontend never computes authoritative prices.

Rozetka pricing model:
  - `products.price` already contains the business markup from import.
  - For Rozetka export we must NOT apply an additional global business markup.
  - Instead: if a Rozetka category pricing rule exists, apply commission
    compensation only (price / (1 - commission)).
  - If no rule exists, fall back to the configured default markup (e.g. 30%).
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional


# ── Defaults ─────────────────────────────────────────────────────────────────

MARKUP_TYPE_PERCENTAGE = "percentage"
MARKUP_TYPE_FIXED = "fixed"

DEFAULT_EXPORT_SETTINGS: dict = {
    "price_markup_type": MARKUP_TYPE_PERCENTAGE,  # "percentage" | "fixed"
    "price_markup_value": 0.0,
    "price_rounding": 0,                          # step (UAH); 0 = disabled
    "min_stock_for_export": 1,
    "export_out_of_stock": False,
}

_TRUE_VALUES = {"true", "1", "yes", "on", "так"}
_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


# ── Parsing helpers ──────────────────────────────────────────────────────────

def parse_float(value, default: float = 0.0) -> float:
    """Parse a possibly-string number ('15', '15,5') keeping only the numeric
    part; returns `default` when nothing usable is found."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    m = _NUM_RE.search(str(value))
    if not m:
        return default
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return default


def parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in _TRUE_VALUES:
        return True
    if s in {"false", "0", "no", "off", "ні", ""}:
        return False
    return default


def load_export_settings(cur, channel_id: int) -> dict:
    """Load export settings for a channel from channel_settings, falling back
    to documented defaults for missing keys.

    Raises ValueError on an unknown markup type so callers can surface a clear
    configuration error instead of exporting with wrong prices.
    """
    settings = dict(DEFAULT_EXPORT_SETTINGS)
    cur.execute(
        "SELECT key, value FROM channel_settings WHERE channel_id = %s",
        (channel_id,),
    )
    stored = {r["key"]: r["value"] for r in cur.fetchall()}
    if "price_markup_type" in stored and stored["price_markup_type"] not in (
            "", MARKUP_TYPE_PERCENTAGE, MARKUP_TYPE_FIXED):
        raise ValueError(
            f"Невірний тип націнки: {stored['price_markup_type']!r} "
            f"(очікується '{MARKUP_TYPE_PERCENTAGE}' або '{MARKUP_TYPE_FIXED}')")
    if "price_markup_type" in stored and stored["price_markup_type"]:
        settings["price_markup_type"] = stored["price_markup_type"]
    settings["price_markup_value"] = parse_float(stored.get("price_markup_value"), 0.0)
    settings["price_rounding"] = int(parse_float(stored.get("price_rounding"), 0.0))
    settings["min_stock_for_export"] = int(parse_float(stored.get("min_stock_for_export"), 1))
    settings["export_out_of_stock"] = parse_bool(stored.get("export_out_of_stock"))
    return settings


# ── Pricing ──────────────────────────────────────────────────────────────────

def calculate_export_price(base_price, settings: dict) -> float:
    """Compute the final export price from the internal base price.

    IMPORTANT: `base_price` is stored in minor units (kopiykas) — e.g.
    175_408 means 1_754.08 UAH.  This function converts to major units
    *before* applying markup so the Rozetka API receives a correct UAH price.

    Rules (server-side authority):
      percentage: base * (1 + value / 100)
      fixed:      base + value
    followed by optional rounding to the nearest multiple of `price_rounding`
    (ROUND_HALF_UP; 0 disables rounding).  Never negative.

    NOTE: This is the GENERIC markup calculator. For Rozetka export use
    `calculate_rozetka_export_price()` which applies category-specific
    commission rules with fallback to this markup only when no rule exists.
    """
    base = Decimal(str(parse_float(base_price))) / Decimal('100')
    markup_value = Decimal(str(settings.get("price_markup_value", 0.0)))

    if settings.get("price_markup_type") == MARKUP_TYPE_FIXED:
        price = base + markup_value
    else:
        price = base * (Decimal("1") + markup_value / Decimal("100"))

    step = int(settings.get("price_rounding") or 0)
    if step > 0:
        quantum = Decimal(step)
        price = (price / quantum).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * quantum

    if price < 0:
        price = Decimal("0")
    return float(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_rozetka_export_price(
    base_price,
    ext_cat_id: Optional[str],
    pricing_resolver,
    settings: dict,
    brand: Optional[str] = None,
) -> float:
    """Compute the Rozetka export price using category-specific commission rules.

    `products.price` already contains the business markup from import, so we
    must NOT apply an additional global business markup when a category rule
    exists.

    Logic:
      1. If a Rozetka category pricing rule exists for ext_cat_id:
         apply commission compensation only: price / (1 - commission).
      2. If no rule exists (or no category is mapped):
         fall back to the configured default markup (e.g. 30%).

    Args:
        base_price: products.price in kopecks (minor units).
        ext_cat_id: Rozetka external category ID (may be None).
        pricing_resolver: RozetkaPricingResolver instance.
        settings: Export settings dict with fallback markup config.
        brand: Optional brand name for rule matching.

    Returns:
        Final export price in UAH (major units).
    """
    base_kopecks = int(parse_float(base_price))

    # Try to find a category-specific commission rule
    if ext_cat_id and pricing_resolver and pricing_resolver.has_rules:
        commission_kopecks = pricing_resolver.calculate_export_price(
            str(ext_cat_id), base_kopecks, brand)
        if commission_kopecks is not None:
            # Rule found: apply commission compensation only (no global markup)
            return commission_kopecks / 100.0

    # No rule found: fall back to the configured default markup
    return calculate_export_price(base_price, settings)


def apply_export_settings(transformed: dict, settings: dict) -> dict:
    """Apply export settings onto a transformed product payload IN PLACE
    (adds `export_price` next to the untouched base fields).

    Preview and real export both call this — they cannot diverge.

    NOTE: This is the GENERIC applicator. For Rozetka export use
    `apply_rozetka_export_settings()` which uses category-specific pricing.
    """
    transformed["export_price"] = calculate_export_price(
        transformed.get("price") or 0, settings)
    return transformed


def apply_rozetka_export_settings(
    transformed: dict,
    settings: dict,
    pricing_resolver,
    brand: Optional[str] = None,
) -> dict:
    """Apply Rozetka-specific export settings onto a transformed product payload
    IN PLACE (adds `export_price` next to the untouched base fields).

    Uses category-specific commission rules with fallback to default markup
    when no rule exists. Does NOT apply global business markup when a rule
    exists (products.price already contains the business markup).

    Args:
        transformed: Product payload dict with at least 'price' key.
        settings: Export settings dict with fallback markup config.
        pricing_resolver: RozetkaPricingResolver instance.
        brand: Optional brand name for rule matching.

    Returns:
        The modified transformed dict.
    """
    ext_cat_id = transformed.get("external_category_id")
    transformed["export_price"] = calculate_rozetka_export_price(
        transformed.get("price") or 0,
        ext_cat_id,
        pricing_resolver,
        settings,
        brand,
    )
    return transformed


# ── Stock rules ──────────────────────────────────────────────────────────────

EXCLUDED_BY_STOCK_RULE = "EXCLUDED_BY_STOCK_RULE"


def stock_exclusion_reason(stock_qty, settings: dict) -> Optional[str]:
    """All products are exported regardless of stock quantity.

    The only difference is stock_quantity in the Rozetka payload:
    in_stock → 10, out_of_stock → 0.  This function always returns None
    (no exclusion) because stock-based filtering is no longer applied.
    """
    return None
