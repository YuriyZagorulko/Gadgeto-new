"""
Centralised pricing service for supplier imports.

Handles the full pipeline:
  1. Determine base UAH price from supplier feed (UAH or USD).
  2. Fetch applicable markup rules from DB (category-aware).
  3. Apply markup → final UAH price.
  4. Convert to integer kopecks for storage.

Markup rule fallback priority:
  A. Exact (supplier_code, category_id)
  B. (supplier_code, NULL)
  C. ('*', category_id)
  D. ('*', NULL) — global fallback

Category resolution for multi-category products:
  Uses ancestor chain (self → parent → grandparent) for best match.
"""

import json
from typing import Optional, List, Tuple

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_setting(key: str) -> Optional[str]:
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _set_setting(key: str, value: str) -> None:
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    conn.autocommit = True
    try:
        cur.execute(
            """INSERT INTO settings (key, value, is_secret, created_at, updated_at)
               VALUES (%s, %s, FALSE, NOW(), NOW())
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
            (key, value),
        )
    finally:
        conn.close()


def get_usd_rate() -> float:
    """Return the configured USD→UAH exchange rate.

    Falls back to 44.3 if not yet configured (legacy default).
    """
    raw = _get_setting("import_usd_rate")
    if raw:
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass
    return 44.3


def set_usd_rate(rate: float) -> None:
    """Persist the USD→UAH exchange rate."""
    _set_setting("import_usd_rate", str(rate))


def _load_rules() -> List[dict]:
    """Load all active markup rules from the DB."""
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """SELECT id, supplier_code, category_id, price_threshold,
                      multiplier, sort_order, is_active
               FROM markup_rules
               WHERE is_active = TRUE
               ORDER BY supplier_code NULLS LAST,
                        category_id NULLS LAST,
                        price_threshold ASC"""
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
# ── Category resolution ─────────────────────────────────────────────────────

def _find_category_id_for_path(category_path: str) -> Optional[int]:
    """Resolve a category path string (e.g. 'Комп'ютери > SSD') to a category id.

    Walks the path segments and queries by name + parent_id.
    Returns the id of the leaf (deepest) category, or None.
    """
    if not category_path or not category_path.strip():
        return None
    parts = [p.strip() for p in category_path.split(">") if p.strip()]
    if not parts:
        return None

    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        parent_id: Optional[int] = None
        leaf_id: Optional[int] = None
        for name in parts:
            if parent_id is None:
                cur.execute(
                    "SELECT id FROM categories WHERE name = %s AND parent_id IS NULL",
                    (name,),
                )
            else:
                cur.execute(
                    "SELECT id FROM categories WHERE name = %s AND parent_id = %s",
                    (name, parent_id),
                )
            row = cur.fetchone()
            if not row:
                return leaf_id  # return deepest matched so far
            leaf_id = row["id"]
            parent_id = leaf_id
        return leaf_id
    finally:
        conn.close()


def _collect_category_ancestor_ids(category_id: Optional[int]) -> List[int]:
    """Walk the category parent chain and return [self, parent, grandparent, ...]."""
    if category_id is None:
        return []
    ids = [category_id]
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        current = category_id
        for _ in range(50):  # safety cap
            cur.execute("SELECT parent_id FROM categories WHERE id = %s", (current,))
            row = cur.fetchone()
            if not row or row["parent_id"] is None:
                break
            current = row["parent_id"]
            ids.append(current)
        return ids
    finally:
        conn.close()


# ── Markup resolution ───────────────────────────────────────────────────────

def find_markup_multiplier(
    base_price_uah: float,
    supplier_code: str = "*",
    category_path: Optional[str] = None,
    category_ids: Optional[List[int]] = None,
    rules: Optional[List[dict]] = None,
) -> float:
    """Determine the markup multiplier for a product.

    Rule evaluation:
      1. Sort candidate rules by scope priority, then threshold ASC.
      2. First matching scope where base_price <= threshold wins.

    Returns:
        Multiplier (e.g. 1.50 for +50%). Defaults to 1.30 if no rules found.
    """
    if rules is None:
        rules = _load_rules()

    if not rules:
        return 1.30  # safe fallback if no rules at all

    # Resolve category ancestor chain
    candidate_cat_ids: List[int] = []
    if category_ids:
        for cid in category_ids:
            candidate_cat_ids.extend(_collect_category_ancestor_ids(cid))
    elif category_path:
        cid = _find_category_id_for_path(category_path)
        if cid:
            candidate_cat_ids.extend(_collect_category_ancestor_ids(cid))

    def cat_matches(r: dict) -> bool:
        if r["category_id"] is None:
            return True
        return r["category_id"] in candidate_cat_ids

    def scope_rank(r: dict) -> int:
        if r["supplier_code"] == supplier_code and r["category_id"] is not None:
            return 0
        if r["supplier_code"] == supplier_code:
            return 1
        if r["category_id"] is not None:
            return 2
        return 3

    # Group rules by scope, pick best-matching scope
    relevant = [r for r in rules if r.get("is_active", True)]
    scopes: dict = {}
    for r in relevant:
        sr = scope_rank(r)
        scopes.setdefault(sr, [])
        scopes[sr].append(r)

    for sr in sorted(scopes):
        group = sorted(scopes[sr], key=lambda x: x["price_threshold"])
        # Check if any rule in this group matches category
        has_cat_match = any(cat_matches(r) for r in group)
        if not has_cat_match and sr in (0, 2):
            continue  # skip category-specific scope if category doesn't match

        for r in group:
            if not cat_matches(r):
                continue
            if base_price_uah <= r["price_threshold"]:
                return r["multiplier"]

        # All thresholds exceeded — return the last (highest) rule's multiplier
        if has_cat_match and group:
            return group[-1]["multiplier"]

    return 1.30


# ── Main pricing pipeline ───────────────────────────────────────────────────

def calculate_price(
    price_uah: Optional[float] = None,
    price_usd: Optional[float] = None,
    usd_rate: Optional[float] = None,
    supplier_code: str = "*",
    category_path: Optional[str] = None,
    category_ids: Optional[List[int]] = None,
) -> int:
    """Full pricing pipeline: source → base UAH → markup → kopecks.

    Returns:
        Final price in integer kopecks (minor units), or 0 if no valid price.
    """
    # Step 1 — determine base UAH price
    if price_uah is not None and price_uah > 0:
        base_price_uah = price_uah
    elif price_usd is not None and price_usd > 0:
        rate = usd_rate if usd_rate is not None else get_usd_rate()
        base_price_uah = price_usd * rate
    else:
        return 0  # no valid price

    if base_price_uah <= 0:
        return 0

    # Step 2 — find markup multiplier
    multiplier = find_markup_multiplier(
        base_price_uah=base_price_uah,
        supplier_code=supplier_code,
        category_path=category_path,
        category_ids=category_ids,
    )

    # Step 3 — apply markup
    final_uah = base_price_uah * multiplier

    # Step 4 — convert to integer kopecks (minor units)
    return round(final_uah * 100)


def calculate_old_price(
    source_old_price_uah: Optional[float] = None,
    markup: Optional[float] = None,
) -> Optional[int]:
    """Calculate an old/RRP price in kopecks from a source UAH price.

    If markup is given, it is applied; otherwise raw UAH × 100.
    """
    if source_old_price_uah is None or source_old_price_uah <= 0:
        return None
    if markup and markup > 0:
        return round(source_old_price_uah * markup * 100)
    return round(source_old_price_uah * 100)


# ── Admin helpers ───────────────────────────────────────────────────────────

def get_pricing_config() -> dict:
    """Return the full pricing config for the admin UI."""
    rules = _load_rules()
    usd_rate = get_usd_rate()
    return {
        "usd_rate": usd_rate,
        "rules": rules,
    }