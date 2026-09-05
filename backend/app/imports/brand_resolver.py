"""Brand Resolution Layer - unified brand extraction and resolution."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import psycopg2
import psycopg2.extras
from app.core.db_connect import DB
from app.imports.brand_normalizer import normalize_brand

logger = logging.getLogger("imports.brand_resolver")


class BrandSource(Enum):
    EXPLICIT_FIELD = "explicit_field"
    VENDOR_FIELD = "vendor_field"
    MANUFACTURER_FIELD = "manufacturer_field"
    EXTRACTED_FROM_NAME = "extracted_from_name"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


class BrandConfidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class BrandCandidate:
    raw_brand: str
    source: BrandSource
    confidence: BrandConfidence
    normalized: Optional[str] = None

    def __post_init__(self):
        if self.normalized is None:
            self.normalized = normalize_brand(self.raw_brand)


@dataclass
class ResolvedBrand:
    name: str
    id: int
    confidence: BrandConfidence
    source: BrandSource
    is_new: bool = False


class BrandResolver:
    def __init__(self, auto_create_brands: bool = False):
        self.auto_create_brands = auto_create_brands
        self._brand_cache = None
        self._cache_loaded = False

    def _load_brand_cache(self) -> dict:
        if self._cache_loaded:
            return self._brand_cache
        self._brand_cache = {}
        conn = psycopg2.connect(DB)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM brands WHERE is_active = TRUE")
            for row in cur:
                self._brand_cache[row[1].lower()] = {'id': row[0], 'name': row[1]}
            cur.close()
        finally:
            conn.close()
        self._cache_loaded = True
        return self._brand_cache

    def resolve(self, raw_brand: str, source: BrandSource = None,
                confidence: BrandConfidence = BrandConfidence.MEDIUM) -> Optional[ResolvedBrand]:
        if not raw_brand or not raw_brand.strip():
            return None
        if source is None:
            source = BrandSource.UNKNOWN
        candidate = BrandCandidate(raw_brand, source, confidence)
        return self._resolve_candidate(candidate)

    def _resolve_candidate(self, candidate: BrandCandidate) -> Optional[ResolvedBrand]:
        if not candidate.normalized:
            return None
        cache = self._load_brand_cache()
        normalized_lower = candidate.normalized.lower()
        if normalized_lower in cache:
            info = cache[normalized_lower]
            return ResolvedBrand(
                name=info['name'], id=info['id'],
                confidence=candidate.confidence, source=candidate.source
            )
        conn = psycopg2.connect(DB)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name FROM brands WHERE LOWER(name) = %s AND is_active = TRUE",
                (normalized_lower,)
            )
            row = cur.fetchone()
            if row:
                cache[normalized_lower] = {'id': row[0], 'name': row[1]}
                return ResolvedBrand(
                    name=row[1], id=row[0],
                    confidence=candidate.confidence, source=candidate.source
                )
            cur.close()
        finally:
            conn.close()
        return None

    def resolve_with_fallback(self, candidates: List[BrandCandidate]) -> Optional[ResolvedBrand]:
        for candidate in candidates:
            result = self._resolve_candidate(candidate)
            if result:
                return result
        return None

    def get_brand_by_id(self, brand_id: int) -> Optional[ResolvedBrand]:
        conn = psycopg2.connect(DB)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM brands WHERE id = %s", (brand_id,))
            row = cur.fetchone()
            cur.close()
            if row:
                return ResolvedBrand(
                    name=row[1], id=row[0],
                    confidence=BrandConfidence.HIGH, source=BrandSource.UNKNOWN
                )
            return None
        finally:
            conn.close()


def extract_brand_dclink(product_name: str) -> Optional[BrandCandidate]:
    from app.imports.brand_extractor import find_brand_in_name as _find_brand_in_name
    if not product_name:
        return None
    extracted = _find_brand_in_name(product_name)
    if not extracted:
        return None
    return BrandCandidate(
        raw_brand=extracted,
        source=BrandSource.EXTRACTED_FROM_NAME,
        confidence=BrandConfidence.MEDIUM,
    )


def extract_brand_itlink(vendor: str, product_name: str = "") -> Optional[BrandCandidate]:
    if not vendor:
        if product_name:
            return extract_brand_dclink(product_name)
        return None
    normalized = normalize_brand(vendor)
    if not normalized:
        return None
    return BrandCandidate(
        raw_brand=vendor,
        source=BrandSource.VENDOR_FIELD,
        confidence=BrandConfidence.HIGH,
        normalized=normalized,
    )


def resolve_supplier_brand(
    supplier_code: str,
    vendor: str = None,
    manufacturer: str = None,
    product_name: str = None,
) -> Optional[ResolvedBrand]:
    resolver = BrandResolver(auto_create_brands=False)
    candidates = []
    if vendor:
        c = extract_brand_itlink(vendor, product_name)
        if c:
            candidates.append(c)
    if manufacturer:
        normalized = normalize_brand(manufacturer)
        if normalized:
            candidates.append(BrandCandidate(
                raw_brand=manufacturer,
                source=BrandSource.MANUFACTURER_FIELD,
                confidence=BrandConfidence.HIGH,
                normalized=normalized,
            ))
    if product_name and supplier_code == 'dclink':
        c = extract_brand_dclink(product_name)
        if c:
            candidates.append(c)
    return resolver.resolve_with_fallback(candidates) if candidates else None


def get_products_needing_brand_backfill(limit: int = 1000) -> List[dict]:
    conn = psycopg2.connect(DB)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT p.id as product_id, p.name, p.supplier_sku, s.code as supplier_code
            FROM products p
            JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.brand_id IS NULL
            ORDER BY p.id
            LIMIT %s
        """, (limit,))
        return list(cur.fetchall())
    finally:
        conn.close()


def backfill_brand_for_product(product_id: int, dry_run: bool = True) -> dict:
    conn = psycopg2.connect(DB)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT p.id, p.name, p.supplier_sku, s.code as supplier_code
            FROM products p
            JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.id = %s
        """, (product_id,))
        product = cur.fetchone()
        if not product:
            return {'status': 'error', 'message': 'Product not found'}

        result = {
            'product_id': product_id,
            'supplier_code': product['supplier_code'],
            'name': product['name'],
            'old_brand_id': None,
            'new_brand_id': None,
            'new_brand_name': None,
            'status': 'skipped',
            'reason': None,
        }

        resolved = resolve_supplier_brand(
            supplier_code=product['supplier_code'],
            product_name=product['name'],
        )

        if resolved:
            result['new_brand_id'] = resolved.id
            result['new_brand_name'] = resolved.name
            result['status'] = 'resolved'
            result['reason'] = f"Extracted: {resolved.name}"
            if not dry_run:
                cur.execute(
                    "UPDATE products SET brand_id = %s, updated_at = NOW() WHERE id = %s",
                    (resolved.id, product_id)
                )
                conn.commit()
        else:
            result['status'] = 'not_found'
            result['reason'] = 'Could not determine brand'

        cur.close()
        return result
    except Exception as e:
        conn.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        conn.close()
