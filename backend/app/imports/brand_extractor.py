"""Brand extraction for DC-Link supplier products.

DC-Link product names follow the pattern: [Product Type] [Brand] [Model].
This module extracts the brand by matching known brand names against the
product name. It has no external dependencies and can be tested
without database or network access.

Pattern examples:
  "Корпус DeepCool AG620"          → brand = "DeepCool"
  "Миша A4Tech X-710MK"           → brand = "A4Tech"
  "Кулер be quiet! Dark Rock Pro"  → brand = "be quiet!"
  "Корпус Lian Li O11 Dynamic"    → brand = "Lian Li"
  "SteelSeries QcK Heavy"         → brand = "SteelSeries"
  "ADATA XPG 1TB NVMe"            → brand = "ADATA"
"""

import re
from typing import Dict, List, Tuple


# =============================================================================
# Multi-word brands (checked before single-word matching)
# Format: (lowercase_pattern, canonical_name)
# Canonical name must match the internal brands table name.
# =============================================================================
_MULTI_WORD_BRANDS: List[Tuple[str, str]] = sorted([
    # Internal multi-word brands
    ("be quiet!", "be quiet!"),
    ("be quiet", "be quiet!"),
    ("lian li", "Lian Li"),
    ("fractal design", "Fractal Design"),
    ("cooler master", "Cooler Master"),
    ("coolermaster", "Cooler Master"),
    ("thermalright", "Thermalright"),
    ("steel series", "SteelSeries"),
    ("steelseries", "SteelSeries"),
    ("team group", "Team Group"),
    ("teamgroup", "TeamGroup"),
    ("silicon power", "Silicon Power"),
    ("western digital", "Western Digital"),
    ("dream machines", "Dream Machines"),
    ("luxe cube", "Luxe Cube"),
    ("real-el", "REAL-EL"),
    ("id-cooling", "ID-Cooling"),
    ("1stplayer", "1stPlayer"),
    ("powercom", "Powercom"),
    ("spaceriver", "Spaceriver"),
    ("gamemax", "GameMax"),
    ("pccooler", "PcCOOLER"),
    ("tp-link", "TP-Link"),
    ("g.skill", "G.Skill"),
    # Confirmed DCL multi-word brands
    ("cablexpert", "Cablexpert"),
    ("ruijie", "Ruijie"),
    ("proarch", "Proarch"),
    ("brauberg", "Brauberg"),
    ("3dmakerpro", "3DMakerpro"),
    ("colorway", "ColorWay"),
    ("сolorway", "ColorWay"),  # Cyrillic С
    ("aerocool", "AeroCool"),
    ("sigma mobile", "Sigma Mobile"),
    ("frime", "FrimeCom"),
    ("tecro", "Tecro"),
    ("prologix", "Prologix"),
    ("drobak", "Drobak"),
    ("drobo", "Drobo"),
    ("boox", "BOOX"),
    ("cabletime", "Cabletime"),
    ("ajazz", "Ajazz"),
    ("remax", "Remax"),
    ("choetech", "Choetech"),
    ("foneng", "Foneng"),
    ("proove", "Proove"),
    ("maxxter", "Maxxter"),
    ("gtl", "GTL"),
    ("aula", "Aula"),
    ("casecom", "CaseCom"),
    ("promate", "Promate"),
    ("grand-x", "Grand-X"),
    ("keychron", "Keychron"),
    ("modecom", "Modecom"),
    ("wacom", "Wacom"),
    ("anda seat", "Anda Seat"),
    ("usams", "Usams"),
    ("havn", "HAVN"),
    ("infinix", "Infinix"),
    ("atcom", "Atcom"),
    ("zyxel", "ZYXEL"),
    ("ttec", "Ttec"),
], key=lambda x: -len(x[0]))


# =============================================================================
# Single-word brands
# Format: lowercase_key -> canonical_name
# Canonical name must match the internal brands table name.
# =============================================================================
_KNOWN_SINGLE_WORD_BRANDS: Dict[str, str] = {
    # Major internal brands
    "samsung": "Samsung", "kingston": "Kingston", "seagate": "Seagate",
    "crucial": "Crucial", "intel": "Intel", "amd": "AMD",
    "corsair": "Corsair", "patriot": "Patriot", "pny": "PNY",
    "lexar": "Lexar", "micron": "Micron", "sk hynix": "SK hynix",
    "toshiba": "Toshiba", "hitachi": "Hitachi", "hgst": "HGST",
    "fujitsu": "Fujitsu", "dell": "Dell",
    "lenovo": "Lenovo", "asus": "ASUS", "acer": "Acer",
    "apple": "Apple", "msi": "MSI", "gigabyte": "Gigabyte",
    "asrock": "ASRock", "evga": "EVGA", "zotac": "Zotac",
    "palit": "Palit", "gainward": "Gainward", "inno3d": "Inno3D",
    "noctua": "Noctua", "deepcool": "DeepCool", "arctic": "Arctic",
    "nzxt": "NZXT", "phanteks": "Phanteks",
    "logitech": "Logitech", "razer": "Razer", "hyperx": "HyperX",
    "netgear": "Netgear", "huawei": "Huawei", "xiaomi": "Xiaomi",
    "realtek": "Realtek", "broadcom": "Broadcom", "marvell": "Marvell",
    "nvidia": "NVIDIA", "matrox": "Matrox", "sonnet": "Sonnet",
    "startech": "StarTech", "delock": "Delock",
    "anker": "Anker", "belkin": "Belkin", "apc": "APC",
    "cyberpower": "CyberPower", "eaton": "Eaton",
    "yamaha": "Yamaha", "pioneer": "Pioneer", "lg": "LG",
    "sony": "Sony", "panasonic": "Panasonic",
    "epson": "Epson", "canon": "Canon", "brother": "Brother",
    "kyocera": "Kyocera", "xerox": "Xerox",
    "viewsonic": "ViewSonic", "benq": "BenQ", "aoc": "AOC",
    "philips": "Philips", "iiyama": "Iiyama",
    # Internal brands (existing in brands table)
    "adata": "ADATA", "wd": "WD", "transcend": "Transcend",
    "g.skill": "G.Skill", "team group": "Team Group",
    "goodram": "Goodram", "sandisk": "Sandisk",
    "powercolor": "PowerColor", "sapphire": "Sapphire",
    "lapara": "Lapara", "maiwo": "Maiwo", "manli": "Manli",
    "stlab": "STLab", "pccooler": "PcCOOLER", "gamestorm": "GamerStorm",
    "borofone": "Borofone", "hoco": "HOCO",
    # Additional confirmed DCL brands
    "a4tech": "A4Tech", "anycubic": "Anycubic", "baseus": "Baseus",
    "becover": "BeCover", "canyon": "Canyon",
    "dahua": "Dahua", "edimax": "Edimax", "elegoo": "Elegoo",
    "elecom": "Elecom", "grandstream": "Grandstream",
    "zte": "ZTE", "bloody": "Bloody", "edifier": "Edifier",
    "chieftec": "Chieftec", "amazon": "Amazon",
    "apacer": "Apacer", "dynamode": "Dynamode", "axtel": "Axtel",
    "hator": "Hator", "targus": "Targus", "sumdex": "Sumdex",
    "xo": "XO", "agestar": "AgeStar", "delux": "Delux",
    "1stplayer": "1stPlayer", "spaceriver": "Spaceriver",
    "ugreen": "Ugreen", "poco": "POCO", "continent": "Continent",
    "dengos": "Dengos", "tenda": "Tenda", "printpro": "PrintPro",
    "titan": "Titan", "motorola": "Motorola", "boox": "BOOX",
    "cabletime": "Cabletime", "skydolphin": "SkyDolphin",
    "gembird": "Gembird", "sigma mobile": "Sigma Mobile",
    "hikvision": "Hikvision", "zalman": "Zalman", "oppo": "Oppo",
    "realme": "Realme", "doogee": "Doogee", "cougar": "Cougar",
    "essager": "Essager", "vention": "Vention", "fellowes": "Fellowes",
    "powerplant": "PowerPlant", "gamepro": "GamePro", "apnx": "APNX",
    "frimecom": "FrimeCom", "prologix": "Prologix", "drobak": "Drobak",
    "d-link": "D-Link", "dlink": "D-Link", "cisco": "Cisco",
    "ubiquiti": "Ubiquiti", "mikrotik": "MikroTik",
    "hp": "HP",
    "2e": "2E",
    "cobra": "COBRA",
    "t&g": "T&G",
    "tg": "T&G",
    "anda seat": "Anda Seat",
    "andaseat": "Anda Seat",
}


# Backwards compatibility: list of all brand names (lowercase)
KNOWN_BRANDS = sorted(_KNOWN_SINGLE_WORD_BRANDS.values(), key=lambda s: (-len(s), s))


def find_brand_in_name(name: str) -> str:
    """Extract brand name from a DC-Link product name.

    DC-Link product names follow the pattern: [Product Type] [Brand] [Model].
    E.g.: "Корпус DeepCool ..." → brand = "DeepCool"
           "Миша A4Tech X-710MK" → brand = "A4Tech"
           "Кулер be quiet! Dark Rock" → brand = "be quiet!"
           "Корпус Lian Li O11 Dynamic" → brand = "Lian Li"

    Multi-word brands are checked first, then single-word brands.
    Returns the canonical brand name if found, otherwise an empty string.
    """
    if not name:
        return ""

    cleaned = re.sub(r'\s+', ' ', name.strip())
    name_lower = cleaned.lower()

    # Check multi-word patterns first (sorted by length descending)
    for pattern, canonical in _MULTI_WORD_BRANDS:
        if pattern in name_lower:
            return canonical

    # Check single-word brands
    for word in cleaned.split():
        stripped = word.rstrip('.,;:!?()[]{}\"\'"/\\')
        stripped_lower = stripped.lower()
        if stripped_lower in _KNOWN_SINGLE_WORD_BRANDS:
            return _KNOWN_SINGLE_WORD_BRANDS[stripped_lower]

    return ""
