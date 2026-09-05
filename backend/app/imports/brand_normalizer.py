"""Brand normalization utilities.

Normalizes brand names from various suppliers to a canonical form.
Handles case, whitespace, known aliases, and Unicode normalization.

This is the canonical normalizer used by the BrandResolver for all suppliers.
"""

import re
import unicodedata
from typing import Optional, Tuple

# =============================================================================
# Known brand aliases (lowercase → canonical form)
# =============================================================================
_BRAND_ALIASES = {
    "asustek": ("ASUS", "HIGH"),
    "asusték": ("ASUS", "HIGH"),
    "asustek computer": ("ASUS", "HIGH"),
    "deep cool": ("Deepcool", "HIGH"),
    "deepcool": ("Deepcool", "HIGH"),
    "g.skill": ("G.Skill", "HIGH"),
    "gskill": ("G.Skill", "HIGH"),
    "western digital": ("Western Digital", "HIGH"),
    "micro-star": ("MSI", "HIGH"),
    "microstar": ("MSI", "HIGH"),
    "colorway": ("ColorWay", "HIGH"),
    "сolorway": ("ColorWay", "HIGH"),
    "lian-li": ("Lian Li", "HIGH"),
    "lianli": ("Lian Li", "HIGH"),
    "tp-link": ("TP-Link", "HIGH"),
    "tplink": ("TP-Link", "HIGH"),
    "cooler master": ("Cooler Master", "HIGH"),
    "coolermaster": ("Cooler Master", "HIGH"),
    "fractal design": ("Fractal Design", "HIGH"),
    "steelseries": ("SteelSeries", "HIGH"),
    "team group": ("Team Group", "HIGH"),
    "teamgroup": ("TeamGroup", "HIGH"),
    "id-cooling": ("ID-Cooling", "HIGH"),
    "real-el": ("REAL-EL", "HIGH"),
    "d-link": ("D-Link", "HIGH"),
    "dlink": ("D-Link", "HIGH"),
    "1stplayer": ("1stPlayer", "HIGH"),
    "3dmakerpro": ("3DMakerpro", "HIGH"),
    "boox": ("BOOX", "HIGH"),
    # "WD" is ambiguous - could be Western Digital or just "wd"
    "wd": ("WD", "MEDIUM"),
    # be quiet! variations -> canonical "be quiet!"
    "be quiet": ("be quiet!", "HIGH"),
    "be quiet!": ("be quiet!", "HIGH"),
    # Invalid - not real brands
    "usb": None,
    "hdmi": None,
}

# Known short brand names (2-3 characters) that are real brands
# These are whitelisted after alias resolution
_SHORT_BRAND_WHITELIST = {
    "hp",   # Hewlett-Packard
    "2e",   # 2E brand
    "xo",   # XO accessories
    "wd",   # Western Digital
}

_GENERIC_TERMS = {
    'usb', 'hdmi', 'vga', 'dvi', 'dp', 'usb-c', 'usb3.0',
    'usb2.0', 'type-c', 'ethernet', 'lan', 'wifi', 'bluetooth',
    'pc', 'laptop', 'gaming', 'office', 'rgb', 'led', 'wireless',
    'black', 'white', 'red', 'blue', 'premium', 'standard', 'pro',
    'mini', 'micro', 'universal', 'generic', 'oem', 'bulk', 'retail',
}


def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC form."""
    if not text:
        return ""
    return unicodedata.normalize('NFC', text)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace: collapse multiple spaces, trim."""
    if not text:
        return ""
    return ' '.join(text.split())


def strip_punctuation(text: str) -> str:
    """Strip trailing punctuation from brand names."""
    if not text:
        return ""
    return text.rstrip('.,;:!?()[]{}\\\'"`"/\\-')


def is_generic_term(text: str) -> bool:
    """Check if text is a generic term, not a brand."""
    if not text:
        return True
    return text.lower().strip() in _GENERIC_TERMS


def is_too_short(text: str) -> bool:
    """Check if the brand name is suspiciously short.
    
    Returns True if the brand name is too short to be reliably identified.
    Known short brands (2 characters) are whitelisted if they exist in the
    _SHORT_BRAND_WHITELIST.
    """
    if not text:
        return True
    stripped = text.strip('.,;:!?()[]{}\\\'"`"/\\-')
    if len(stripped) <= 2:
        # Check if this is a known short brand
        return stripped.lower() not in _SHORT_BRAND_WHITELIST
    return False


def normalize_brand(raw_brand: str) -> Optional[str]:
    """Normalize a brand name to canonical form.
    
    Returns canonical brand name, or None if invalid/generic.
    """
    if not raw_brand or not raw_brand.strip():
        return None
    
    # Normalize Unicode
    normalized = normalize_unicode(raw_brand)
    # Trim and normalize whitespace
    normalized = normalize_whitespace(normalized)
    if not normalized:
        return None
    # Strip trailing punctuation
    stripped = strip_punctuation(normalized)
    if not stripped:
        return None
    # Check for generic terms
    if is_generic_term(stripped):
        return None
    # Check aliases FIRST (before length check)
    lower = stripped.lower()
    if lower in _BRAND_ALIASES:
        result = _BRAND_ALIASES[lower]
        return result[0] if result else None
    # Check for too-short names (short brands are checked via whitelist)
    if is_too_short(stripped):
        return None
    # Preserve original case for unknown brands
    if stripped and stripped[0].isupper():
        return stripped
    return stripped.title()


def get_brand_confidence(raw_brand: str, normalized_brand: str) -> str:
    """Determine confidence level of brand detection."""
    if not raw_brand or not normalized_brand:
        return "LOW"
    raw_lower = raw_brand.lower().strip()
    if raw_lower in _BRAND_ALIASES:
        _, confidence = _BRAND_ALIASES[raw_lower]
        return confidence or "MEDIUM"
    return "HIGH" if raw_lower == normalized_brand.lower() else "MEDIUM"
