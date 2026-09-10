"""Brain supplier taxonomy helpers (supplier_id=3, code='brain').

Final implementation stage. Authoritative sources:
  * BRAIN_TAXONOMY_IMPLEMENTATION_SPECIFICATION_V2.md
  * BRAIN_FINAL_4_BUSINESS_DECISIONS.md
  * BRAIN_FINAL_TECHNICAL_GATE.md

Scope (deliberately minimal): Brain identity is ALWAYS
(supplier_id=3 + external_id TEXT). Numeric IDs use CAST AS INTEGER
semantics. Only the four FINAL approved mappings are seeded:
1366->126, 1402->60, 1209/1487->NEW "Носії інформації" (parent_id=40).
No Alembic migration here (repo has multiple heads); all DDL is
idempotent ADD COLUMN IF NOT EXISTS, all seeds idempotent.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import psycopg2
import psycopg2.extras

from app.core.db_connect import DB

BRAIN_SUPPLIER_ID = 3
BRAIN_SUPPLIER_CODE = "brain"

NEW_MEDIA_CATEGORY_NAME = "Носії інформації"
NEW_MEDIA_PARENT_ID = 40
NEW_MEDIA_SLUG_BASE = "nosii-informatsii"


def _to_int(value) -> Optional[int]:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def sort_numeric(external_ids: Iterable) -> List[str]:
    ids = [str(x) for x in external_ids]
    numeric = sorted(
        (x for x in ids if _to_int(x) is not None),
        key=lambda x: int(str(x).strip()),
    )
    non_numeric = sorted(x for x in ids if _to_int(x) is None)
    return numeric + non_numeric


def pick_fallback_min(external_ids: Iterable) -> Optional[str]:
    ids = [str(x) for x in external_ids]
    numeric = [x for x in ids if _to_int(x) is not None]
    if numeric:
        return min(numeric, key=lambda x: int(str(x).strip()))
    if ids:
        return sorted(ids)[0]
    return None


def _norm_cat(cat: dict):
    cid = cat.get("categoryID")
    if cid is None:
        return None
    ext_id = str(cid).strip()
    if not ext_id:
        return None
    parent = cat.get("parentID")
    parent_ext = str(parent).strip() if parent is not None else None
    if parent_ext == "":
        parent_ext = None
    name = str(cat.get("name") or "").strip()
    realcat = cat.get("realcat")
    try:
        real_int = int(realcat or 0)
    except (TypeError, ValueError):
        real_int = 0
    real_ext = str(real_int).strip() if real_int > 0 else None
    return ext_id, parent_ext, name, real_ext


def order_for_insert(categories: List[dict]) -> List[dict]:
    normed: Dict[str, dict] = {}
    for cat in categories or []:
        parsed = _norm_cat(cat)
        if parsed is None:
            continue
        ext_id = parsed[0]
        if ext_id not in normed:
            normed[ext_id] = cat
    children: Dict[Optional[str], List[str]] = {}
    for ext_id, cat in normed.items():
        parsed = _norm_cat(cat)
        parent_ext = parsed[1] if parsed else None
        if parent_ext is None or parent_ext not in normed:
            children.setdefault(None, []).append(ext_id)
        else:
            children.setdefault(parent_ext, []).append(ext_id)
    for key in children:
        children[key] = sort_numeric(children[key])
    ordered: List[dict] = []
    seen: set = set()
    queue: List[str] = list(children.get(None, []))
    while queue:
        ext_id = queue.pop(0)
        if ext_id in seen:
            continue
        seen.add(ext_id)
        ordered.append(normed[ext_id])
        for child in children.get(ext_id, []):
            if child not in seen:
                queue.append(child)
    for ext_id in sort_numeric(normed.keys()):
        if ext_id not in seen:
            ordered.append(normed[ext_id])
    return ordered


def build_realcat_map(categories: List[dict]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for cat in categories or []:
        parsed = _norm_cat(cat)
        if parsed is None:
            continue
        ext_id, _p, _n, real_ext = parsed
        if real_ext and real_ext != ext_id:
            mapping[ext_id] = real_ext
    return mapping


def resolve_real_external_id(external_id, realcat_map: Dict[str, str]):
    if external_id is None:
        return None
    cid = str(external_id).strip()
    if not cid:
        return None
    if cid not in realcat_map:
        return cid
    seen: set = set()
    while cid in realcat_map and cid not in seen:
        seen.add(cid)
        nxt = realcat_map[cid]
        if not nxt or nxt == cid:
            return cid
        cid = nxt
    return cid


def compute_depths(categories: List[dict]) -> Dict[str, int]:
    parent_of: Dict[str, Optional[str]] = {}
    for cat in categories or []:
        parsed = _norm_cat(cat)
        if parsed is None:
            continue
        if parsed[0] not in parent_of:
            parent_of[parsed[0]] = parsed[1]
    depths: Dict[str, int] = {}

    def _depth(ext_id: str, trail: frozenset = frozenset()) -> int:
        if ext_id in depths:
            return depths[ext_id]
        if ext_id in trail:
            return 0
        parent = parent_of.get(ext_id)
        if not parent or parent not in parent_of:
            depths[ext_id] = 0
            return 0
        d = _depth(parent, trail | {ext_id}) + 1
        depths[ext_id] = d
        return d

    for ext_id in parent_of:
        _depth(ext_id)
    return depths
def pick_product_category(
    candidate_external_ids: Iterable,
    realcat_map: Dict[str, str],
    depths: Optional[Dict[str, int]] = None,
    business_rules: Optional[Dict[str, str]] = None,
):
    """Deterministic V2 routing: realcat -> depth -> business rule -> MIN(int)."""
    cands = [str(x).strip() for x in (candidate_external_ids or []) if str(x).strip()]
    if not cands:
        return None
    resolved: List[str] = []
    for cand in cands:
        real = resolve_real_external_id(cand, realcat_map or {})
        resolved.append(real if real is not None else cand)
    resolved = sorted(
        set(resolved),
        key=lambda x: (0, int(x)) if _to_int(x) is not None else (1, x),
    )
    if len(resolved) == 1:
        return resolved[0]
    depths = depths or {}
    max_depth = max(int(depths.get(x, 0) or 0) for x in resolved)
    deepest = [x for x in resolved if int(depths.get(x, 0) or 0) == max_depth]
    if len(deepest) == 1:
        return deepest[0]
    if business_rules:
        for cand in sort_numeric(deepest):
            if cand in business_rules:
                return business_rules[cand]
    return pick_fallback_min(deepest)


def extract_brain_attribute_ids(option: dict) -> Tuple[str, str, str, str]:
    """Brain identity per V2: OptionID=attr, ValueID=value. FilterID ignored."""
    opt = option or {}
    name = str(opt.get("OptionName") or opt.get("name") or "").strip()
    value = str(opt.get("ValueName") or opt.get("value") or "").strip()
    option_id = str(opt.get("OptionID") or opt.get("option_id") or "").strip()
    value_id = str(opt.get("ValueID") or opt.get("value_id") or "").strip()
    return name, value, option_id, value_id


TAXONOMY_COLUMNS_DDL = (
    "ALTER TABLE supplier_categories ADD COLUMN IF NOT EXISTS parent_external_id TEXT",
    "ALTER TABLE supplier_categories ADD COLUMN IF NOT EXISTS realcat_external_id TEXT",
)


def ensure_taxonomy_columns(cur) -> None:
    for ddl in TAXONOMY_COLUMNS_DDL:
        cur.execute(ddl)


def _brain_supplier_id(cur) -> int:
    cur.execute("SELECT id FROM suppliers WHERE code = 'brain'")
    row = cur.fetchone()
    if not row:
        raise ValueError("Supplier 'brain' not found (expected id=3)")
    sid = row["id"] if isinstance(row, dict) else row[0]
    return int(sid)


def sync_brain_taxonomy(categories: List[dict], cur) -> dict:
    """Mirror Brain taxonomy locally (idempotent, supplier_id=3 only).

    Identity is (supplier_id, external_id). Duplicate Brain NAMES are
    legitimate — rows are keyed by external_id only, never by name, so
    1209/1487 (both «Носії інформації») stay distinct. The legacy
    UNIQUE(supplier_id, supplier_name) index predates external-ID identity;
    same-name rows get a suffixed supplier_name («name [ext]») to satisfy it
    while keeping external_id as the stable identity.
    """
    ensure_taxonomy_columns(cur)
    sid = _brain_supplier_id(cur)
    if int(sid) != BRAIN_SUPPLIER_ID:
        raise ValueError(f"Brain supplier id must be 3, got {sid}")
    stats = {"categories_synced": 0, "updated": 0, "virtual": 0, "real": 0}
    for cat in order_for_insert(categories or []):
        parsed = _norm_cat(cat)
        if parsed is None:
            continue
        ext_id, parent_ext, name, real_ext = parsed
        if not name:
            continue
        is_virtual = real_ext is not None
        cur.execute(
            "SELECT id, supplier_name FROM supplier_categories"
            " WHERE supplier_id=%s AND external_id=%s",
            (sid, ext_id),
        )
        row = cur.fetchone()
        store_name = name
        if row is None:
            # Legacy UNIQUE(supplier_id, supplier_name): disambiguate
            # duplicate Brain names with the stable external_id suffix.
            cur.execute(
                "SELECT id, external_id FROM supplier_categories"
                " WHERE supplier_id=%s AND supplier_name=%s",
                (sid, name),
            )
            clash = cur.fetchone()
            if clash is not None:
                clash_ext = clash["external_id"] if isinstance(clash, dict) else clash[1]
                if clash_ext != ext_id:
                    store_name = f"{name} [{ext_id}]"
        if row:
            sc_id = row["id"] if isinstance(row, dict) else row[0]
            old_name = row["supplier_name"] if isinstance(row, dict) else None
            if old_name in (name, f"{name} [{ext_id}]"):
                store_name = old_name
            else:
                cur.execute(
                    "SELECT 1 FROM supplier_categories WHERE supplier_id=%s"
                    " AND supplier_name=%s AND external_id IS DISTINCT FROM %s",
                    (sid, name, ext_id),
                )
                if cur.fetchone():
                    store_name = f"{name} [{ext_id}]"
            cur.execute(
                "UPDATE supplier_categories SET supplier_name=%s, "
                "parent_external_id=%s, realcat_external_id=%s, "
                "is_removed=FALSE, updated_at=NOW() WHERE id=%s",
                (store_name, parent_ext, real_ext, sc_id),
            )
            stats["updated"] += 1
        else:
            try:
                cur.execute(
                    "INSERT INTO supplier_categories (supplier_id, external_id, supplier_name,"
                    " parent_external_id, realcat_external_id, is_removed, created_at, updated_at)"
                    " VALUES (%s,%s,%s,%s,%s,FALSE,NOW(),NOW())",
                    (sid, ext_id, store_name, parent_ext, real_ext),
                )
            except Exception:
                # Concurrent/legacy name clash on retry — suffix and retry once.
                store_name = f"{name} [{ext_id}]"
                cur.execute(
                    "INSERT INTO supplier_categories (supplier_id, external_id, supplier_name,"
                    " parent_external_id, realcat_external_id, is_removed, created_at, updated_at)"
                    " VALUES (%s,%s,%s,%s,%s,FALSE,NOW(),NOW())",
                    (sid, ext_id, store_name, parent_ext, real_ext),
                )
            stats["categories_synced"] += 1
        if is_virtual:
            stats["virtual"] += 1
        else:
            stats["real"] += 1
    return stats


def ensure_media_category(cur) -> int:
    """Idempotent get-or-create of global Nosiiv category (parent_id=40)."""
    cur.execute(
        "SELECT id FROM categories WHERE name=%s AND parent_id=%s",
        (NEW_MEDIA_CATEGORY_NAME, NEW_MEDIA_PARENT_ID),
    )
    row = cur.fetchone()
    if row:
        return int(row["id"] if isinstance(row, dict) else row[0])
    slug = NEW_MEDIA_SLUG_BASE
    cur.execute("SELECT 1 FROM categories WHERE slug=%s", (slug,))
    suffix = 2
    while cur.fetchone():
        slug = f"{NEW_MEDIA_SLUG_BASE}-{suffix}"
        suffix += 1
        cur.execute("SELECT 1 FROM categories WHERE slug=%s", (slug,))
    cur.execute(
        "INSERT INTO categories (name, slug, parent_id, is_active, sort_order,"
        " created_at, updated_at) VALUES (%s,%s,%s,TRUE,0,NOW(),NOW())"
        " ON CONFLICT (slug) DO NOTHING RETURNING id",
        (NEW_MEDIA_CATEGORY_NAME, slug, NEW_MEDIA_PARENT_ID),
    )
    created = cur.fetchone()
    if created:
        return int(created["id"] if isinstance(created, dict) else created[0])
    cur.execute(
        "SELECT id FROM categories WHERE name=%s AND parent_id=%s",
        (NEW_MEDIA_CATEGORY_NAME, NEW_MEDIA_PARENT_ID),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Failed to create Nosii category")
    return int(row["id"] if isinstance(row, dict) else row[0])


def ensure_final_mappings(cur) -> Dict[str, int]:
    """Seed ONLY the four FINAL approved Brain mappings (idempotent)."""
    sid = _brain_supplier_id(cur)
    if int(sid) != BRAIN_SUPPLIER_ID:
        raise ValueError(f"Brain supplier id must be 3, got {sid}")
    try:
        ensure_taxonomy_columns(cur)
    except Exception:
        pass
    media_id = ensure_media_category(cur)
    targets: Dict[str, int] = {"1366": 126, "1402": 60, "1209": media_id, "1487": media_id}
    names = {
        "1366": "Папір і плівка для друку",
        "1402": "Розетки та короба",
        "1209": "Носії інформації",
        "1487": "Носії інформації",
    }
    for ext_id, target in targets.items():
        cur.execute("SELECT id FROM categories WHERE id=%s", (target,))
        if not cur.fetchone():
            raise ValueError(f"Gadgeto target category {target} does not exist")
        cur.execute(
            "SELECT id FROM supplier_categories WHERE supplier_id=%s AND external_id=%s",
            (sid, ext_id),
        )
        row = cur.fetchone()
        if row:
            sc_id = row["id"] if isinstance(row, dict) else row[0]
        else:
            base_name = names[ext_id]
            cur.execute(
                "SELECT id, external_id FROM supplier_categories"
                " WHERE supplier_id=%s AND supplier_name=%s",
                (sid, base_name),
            )
            clash = cur.fetchone()
            store = base_name
            if clash is not None:
                cext = clash["external_id"] if isinstance(clash, dict) else clash[1]
                if cext != ext_id:
                    store = f"{base_name} [{ext_id}]"
            try:
                cur.execute(
                    "INSERT INTO supplier_categories (supplier_id, external_id, supplier_name,"
                    " is_removed, created_at, updated_at) VALUES (%s,%s,%s,FALSE,NOW(),NOW())"
                    " RETURNING id",
                    (sid, ext_id, store),
                )
            except Exception:
                store = f"{base_name} [{ext_id}]"
                cur.execute(
                    "INSERT INTO supplier_categories (supplier_id, external_id, supplier_name,"
                    " is_removed, created_at, updated_at) VALUES (%s,%s,%s,FALSE,NOW(),NOW())"
                    " RETURNING id",
                    (sid, ext_id, store),
                )
            created = cur.fetchone()
            sc_id = created["id"] if isinstance(created, dict) else created[0]
        cur.execute(
            "SELECT id FROM category_mappings WHERE supplier_category_id=%s",
            (sc_id,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE category_mappings SET category_id=%s, is_active=TRUE,"
                " updated_at=NOW() WHERE supplier_category_id=%s",
                (target, sc_id),
            )
        else:
            cur.execute(
                "INSERT INTO category_mappings (supplier_category_id, category_id,"
                " is_active, created_at, updated_at) VALUES (%s,%s,TRUE,NOW(),NOW())",
                (sc_id, target),
            )
    return targets


def sync_brain_taxonomy_standalone(categories: List[dict]) -> dict:
    conn = psycopg2.connect(DB)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            stats = sync_brain_taxonomy(categories, cur)
            conn.commit()
            return stats
        finally:
            cur.close()
    finally:
        conn.close()
