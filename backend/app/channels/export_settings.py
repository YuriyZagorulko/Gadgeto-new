"""Channel export settings — pricing and stock rules (Phase 6.3).

Single source of truth for:
  * loading per-channel export settings from `channel_settings`
  * computing the authoritative export price (markup + rounding)
  * deciding whether a product passes the stock rules

The SAME functions are used by:
  * POST /export/channels/{code}/export/preview
  * POST /export/channels/{code}/export        (real background run)

The frontend never computes authoritative prices.
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


def apply_export_settings(transformed: dict, settings: dict) -> dict:
    """Apply export settings onto a transformed product payload IN PLACE
    (adds `export_price` next to the untouched base fields).

    Preview and real export both call this — they cannot diverge.
    """
    transformed["export_price"] = calculate_export_price(
        transformed.get("price") or 0, settings)
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
