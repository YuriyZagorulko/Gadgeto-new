"""
SEO metadata generator.

Replicates the legacy `woocommerce_seo_generator.py` functionality
without the `attributesManager` dependency.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Known brand names (sorted by length descending for greedy matching) ─────
_KNOWN_BRANDS: List[str] = sorted([
    "Samsung", "Kingston", "Western Digital", "WD", "Seagate",
    "Crucial", "Intel", "AMD", "ADATA", "Corsair", "G.Skill",
    "Team Group", "TeamGroup", "Transcend", "Silicon Power",
    "Patriot", "PNY", "Lexar", "Micron", "SK hynix", "Hynix",
    "Toshiba", "Hitachi", "HGST", "Fujitsu", "Dell", "HP",
    "Lenovo", "ASUS", "Acer", "Apple", "MSI", "Gigabyte",
    "ASRock", "EVGA", "Zotac", "Palit", "Gainward", "Inno3D",
    "Noctua", "be quiet", "Cooler Master", "DeepCool",
    "Thermalright", "Arctic", "Fractal Design", "NZXT",
    "Lian Li", "Phanteks", "Logitech", "Razer",
    "SteelSeries", "HyperX", "TP-Link", "Netgear",
    "Ubiquiti", "MikroTik", "Cisco", "Huawei", "Xiaomi",
    "Realtek", "Broadcom", "Marvell", "NVIDIA", "AMD Radeon",
    "Matrox", "Sonnet", "StarTech", "Delock", "Ugreen",
    "Anker", "Belkin", "APC", "CyberPower", "Eaton",
    "Yamaha", "Pioneer", "LG", "Sony", "Panasonic",
    "Epson", "Canon", "Brother", "Kyocera", "Xerox",
    "ViewSonic", "BenQ", "AOC", "Philips", "Iiyama",
], key=lambda s: (-len(s), s))

# ── Patterns ──────────────────────────────────────────────────────────────
_CAPACITY_RE = re.compile(r"(\d+[\s]*(?:ГБ|GB|TB|ТБ|MB|МБ|PB|ПБ))", re.IGNORECASE)


@dataclass
class ParsedProductName:
    """Structured product name data."""
    raw: str = ""
    cleaned: str = ""
    brand: str = ""
    model: str = ""
    capacity: str = ""
    interface: str = ""
    color: str = ""
    form_factor: str = ""


def _clean_name(name: str) -> str:
    """Clean product name."""
    return re.sub(r"\s+", " ", name.strip())


def parse_product_name(name: str) -> ParsedProductName:
    """Parse product name into components."""
    parsed = ParsedProductName(raw=name, cleaned=_clean_name(name))
    
    # Extract brand
    for brand in _KNOWN_BRANDS:
        if parsed.cleaned.lower().startswith(brand.lower()):
            parsed.brand = brand
            rest = parsed.cleaned[len(brand):].strip()
            parsed.model = rest
            break
    
    # Extract capacity
    cap_match = _CAPACITY_RE.search(parsed.cleaned)
    if cap_match:
        parsed.capacity = cap_match.group(1).strip()
    
    return parsed


def generate_product_seo(product: dict) -> Dict[str, str]:
    """
    Generate SEO metadata for a product.
    
    Args:
        product: Dict with at least "Name" key.
    
    Returns:
        Dict with seo_title, meta_description, focus_keyphrase.
    """
    raw_name = product.get("Name", "")
    if not raw_name:
        return {
            "seo_title": "",
            "meta_description": "",
            "focus_keyphrase": "",
        }
    
    cleaned = _clean_name(raw_name)
    parsed = parse_product_name(raw_name)
    
    # SEO title
    seo_title = f"{cleaned} — купити в Україні | Gadgeto"
    
    # Meta description
    meta_description = (
        f"Купуйте {cleaned} в Gadgeto. "
        f"Висока якість, швидка доставка по Україні, гарантія. "
        f"Вигідні ціни на комп'ютерну техніку та аксесуари."
    )
    
    # Focus keyphrase
    kp_parts = []
    if parsed.brand:
        kp_parts.append(parsed.brand)
    if parsed.model:
        kp_parts.append(parsed.model)
    elif cleaned:
        kp_parts.append(cleaned)
    focus_keyphrase = " ".join(kp_parts)
    
    return {
        "seo_title": seo_title,
        "meta_description": meta_description,
        "focus_keyphrase": focus_keyphrase,
    }
