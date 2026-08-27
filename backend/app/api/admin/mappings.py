"""Admin mappings API — category/attribute/value mappings between suppliers and the catalog."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor
from app.imports.registry import SUPPLIERS as SYSTEM_SUPPLIERS

router = APIRouter()


class MappingCreate(BaseModel):
    supplier_code: Optional[str] = None
    supplier_item_id: Optional[int] = None
    supplier_item_name: Optional[str] = None
    # values kind only: holder attribute name for a brand-new supplier value
    supplier_parent_name: Optional[str] = None
    catalog_item_id: Optional[int] = None
    category_id: Optional[int] = None
    is_active: bool = True


class MappingUpdate(BaseModel):
    catalog_item_id: Optional[int] = None
    is_active: Optional[bool] = None


# Server-side sortable columns per mapping kind (whitelisted SQL expressions).
_LIST_SQL = {
    "categories": {
        "table": "category_mappings", "s_fk": "supplier_category_id", "c_fk": "category_id",
        "s_table": "supplier_categories", "c_table": "categories", "scope_alias": "sc",
        "joins": """JOIN supplier_categories sc ON sc.id = m.supplier_category_id
                    LEFT JOIN suppliers s ON s.id = sc.supplier_id
                    LEFT JOIN categories c ON c.id = m.category_id""",
        "select_names": "sc.supplier_name AS supplier_item_name, c.name AS catalog_name,\n                         (sc.supplier_id IS NULL) AS is_global",
        "search": ["sc.supplier_name", "s.code", "c.name"],
        "sort": {
            "id": "m.id", "supplier": "s.name", "supplier_code": "s.code",
            "supplier_item": "sc.supplier_name", "catalog": "c.name",
            "status": "m.is_active", "updated_at": "m.updated_at",
        },
    },
    "attributes": {
        "table": "attribute_mappings", "s_fk": "supplier_attribute_id", "c_fk": "attribute_id",
        "s_table": "supplier_attributes", "c_table": "attributes", "scope_alias": "sa",
        "joins": """JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
                    LEFT JOIN suppliers s ON s.id = sa.supplier_id
                    LEFT JOIN attributes a ON a.id = m.attribute_id
                    LEFT JOIN categories cat ON cat.id = m.category_id""",
        "select_names": "sa.supplier_name AS supplier_item_name, a.name AS catalog_name,\n                         (sa.supplier_id IS NULL) AS is_global,                         m.category_id, cat.name AS internal_category_name",
        "search": ["sa.supplier_name", "s.code", "a.name", "cat.name"],
        "sort": {
            "id": "m.id", "supplier": "s.name", "supplier_code": "s.code",
            "supplier_item": "sa.supplier_name", "catalog": "a.name",
            "status": "m.is_active", "updated_at": "m.updated_at",
            "category": "cat.name",
        },
    },
    "values": {
        "table": "attribute_value_mappings", "s_fk": "supplier_attribute_value_id",
        "c_fk": "attribute_value_id",
        "s_table": "supplier_attribute_values", "c_table": "attribute_values", "scope_alias": "ha",
        "joins": """JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
                    JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
                    LEFT JOIN suppliers s ON s.id = ha.supplier_id
                    LEFT JOIN attribute_values av ON av.id = m.attribute_value_id""",
        "select_names": """ha.supplier_name AS holder_name,
                           sav.supplier_value AS supplier_item_name, av.value AS catalog_name,
                           (ha.supplier_id IS NULL) AS is_global""",
        "search": ["ha.supplier_name", "sav.supplier_value", "av.value", "s.code"],
        "sort": {
            "id": "m.id", "supplier": "s.name", "supplier_code": "s.code",
            "attribute": "ha.supplier_name",
            "supplier_item": "sav.supplier_value", "catalog": "av.value",
            "status": "m.is_active", "updated_at": "m.updated_at",
        },
    },
}


def _list_sql_or_404(kind: str):
    if kind not in _LIST_SQL:
        raise HTTPException(status_code=404, detail="Невідомий тип відповідностей")
    return _LIST_SQL[kind]



def _paged(cur, base_sql: str, count_sql: str, params: list, page: int, per_page: int):
    cur.execute(count_sql, params)
    total = cur.fetchone()["c"]
    cur.execute(base_sql + " LIMIT %s OFFSET %s", params + [per_page, (page - 1) * per_page])
    return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}


# ------------------------------------------------------------ pickers

@router.get("/mappings/supplier-categories")
def lookup_supplier_categories(
    supplier_id: Optional[int] = None, q: Optional[str] = None,
    unmapped: bool = False, page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    conn, cur = admin_cursor()
    try:
        conds, params = ["sc.is_removed=false"], []
        if supplier_id:
            conds.append("sc.supplier_id=%s"); params.append(supplier_id)
        if q:
            conds.append("sc.supplier_name ILIKE %s"); params.append(f"%{q}%")
        unmapped_cond = ("NOT EXISTS (SELECT 1 FROM category_mappings cm "
                         "WHERE cm.supplier_category_id=sc.id)") if unmapped else "true"
        where = " AND ".join(conds)
        sql = f"""SELECT sc.id, sc.supplier_id, sc.supplier_name,
                         cm.id AS mapping_id, c.name AS catalog_name
                  FROM supplier_categories sc
                  LEFT JOIN category_mappings cm ON cm.supplier_category_id=sc.id
                  LEFT JOIN categories c ON c.id=cm.category_id
                  WHERE {where} AND {unmapped_cond} ORDER BY sc.supplier_name"""
        count = f"""SELECT COUNT(*) AS c FROM supplier_categories sc
                    WHERE {where} AND {unmapped_cond}"""
        return _paged(cur, sql, count, params, page, per_page)
    finally:
        conn.close()


@router.get("/mappings/supplier-attributes")
def lookup_supplier_attributes(
    supplier_id: Optional[int] = None, q: Optional[str] = None,
    unmapped: bool = False, page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    conn, cur = admin_cursor()
    try:
        conds, params = ["sa.is_removed=false"], []
        if supplier_id:
            conds.append("sa.supplier_id=%s"); params.append(supplier_id)
        if q:
            conds.append("sa.supplier_name ILIKE %s"); params.append(f"%{q}%")
        unmapped_cond = ("NOT EXISTS (SELECT 1 FROM attribute_mappings am "
                         "WHERE am.supplier_attribute_id=sa.id)") if unmapped else "true"
        where = " AND ".join(conds)
        sql = f"""SELECT sa.id, sa.supplier_id, sa.supplier_name,
                         am.id AS mapping_id, a.name AS catalog_name
                  FROM supplier_attributes sa
                  LEFT JOIN attribute_mappings am ON am.supplier_attribute_id=sa.id
                  LEFT JOIN attributes a ON a.id=am.attribute_id
                  WHERE {where} AND {unmapped_cond} ORDER BY sa.supplier_name"""
        count = f"""SELECT COUNT(*) AS c FROM supplier_attributes sa
                    WHERE {where} AND {unmapped_cond}"""
        return _paged(cur, sql, count, params, page, per_page)
    finally:
        conn.close()


@router.get("/mappings/supplier-values")
def lookup_supplier_values(
    attribute_id: Optional[int] = None, q: Optional[str] = None,
    unmapped: bool = False, page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    conn, cur = admin_cursor()
    try:
        conds, params = ["sav.is_removed=false"], []
        if attribute_id:
            conds.append("sav.supplier_attribute_id=%s"); params.append(attribute_id)
        if q:
            conds.append("sav.supplier_value ILIKE %s"); params.append(f"%{q}%")
        unmapped_cond = ("NOT EXISTS (SELECT 1 FROM attribute_value_mappings avm "
                         "WHERE avm.supplier_attribute_value_id=sav.id)") if unmapped else "true"
        where = " AND ".join(conds)
        sql = f"""SELECT sav.id, sav.supplier_attribute_id, sav.supplier_value,
                         avm.id AS mapping_id, av.value AS catalog_name
                  FROM supplier_attribute_values sav
                  LEFT JOIN attribute_value_mappings avm ON avm.supplier_attribute_value_id=sav.id
                  LEFT JOIN attribute_values av ON av.id=avm.attribute_value_id
                  WHERE {where} AND {unmapped_cond} ORDER BY sav.supplier_value"""
        count = f"""SELECT COUNT(*) AS c FROM supplier_attribute_values sav
                    WHERE {where} AND {unmapped_cond}"""
        return _paged(cur, sql, count, params, page, per_page)
    finally:
        conn.close()


# ------------------------------------------------------- mapping CRUD



@router.get("/mappings/category-attributes")
def lookup_category_attributes(
    category_id: int,
    q: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Get available internal Attributes for a specific category.
    Returns CategoryAttributes filtered by category, searchable by name."""
    conn, cur = admin_cursor()
    try:
        conds, params = ["ca.category_id = %s"], [category_id]
        if q:
            conds.append("a.name ILIKE %s")
            params.append(f"%{q}%")
        where = " AND ".join(conds)
        cur.execute(
            f"""SELECT ca.id, ca.attribute_id, a.name AS attribute_name,
                       a.slug AS attribute_slug, ca.required, ca.multiple,
                       ca.filterable, ca.searchable, ca.sort_order
                FROM category_attributes ca
                JOIN attributes a ON a.id = ca.attribute_id
                WHERE {where}
                ORDER BY ca.sort_order, a.name
                LIMIT 200""",
            params,
        )
        return {"items": cur.fetchall()}
    finally:
        conn.close()


@router.put("/mappings/{kind}/{mid}/category-context")
def set_mapping_category_context(
    kind: str, mid: int,
    category_id: Optional[int] = None,
    user: dict = Depends(require_admin),
):
    """Set or clear the category context on an attribute mapping.
    Only for 'attributes' kind.  NULL = global, category_id = scoped."""
    if kind != "attributes":
        raise HTTPException(status_code=400, detail="Тільки для маппінгу атрибутів")
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM attribute_mappings WHERE id=%s", (mid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        if category_id is not None:
            cur.execute("SELECT id FROM categories WHERE id=%s", (category_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Категорію не знайдено")
        cur.execute(
            "UPDATE attribute_mappings SET category_id=%s, updated_at=NOW() WHERE id=%s",
            (category_id, mid),
        )
        return {"ok": True, "category_id": category_id}
    finally:
        conn.close()


# ── Review & Repair Endpoints ───────────────────────────────────────────────

@router.get("/mappings/review/summary")
def review_summary(user: dict = Depends(require_admin)):
    """Return summary counts for the review dashboard."""
    conn, cur = admin_cursor()
    try:
        # Unassigned attributes: active mappings whose internal attr has 0 CategoryAttributes
        cur.execute("""
            SELECT count(DISTINCT m.attribute_id) AS unassigned_attrs,
                   count(*) AS unassigned_mappings
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            WHERE m.category_id IS NULL
              AND m.attribute_id IS NOT NULL
              AND m.is_active = true
              AND NOT EXISTS (
                  SELECT 1 FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id
              )
        """)
        unassigned = dict(cur.fetchone())

        # Ambiguous: active mappings whose internal attr belongs to >1 category
        cur.execute("""
            SELECT count(*) AS ambiguous_count
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            WHERE m.category_id IS NULL
              AND m.attribute_id IS NOT NULL
              AND m.is_active = true
              AND (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id) > 1
        """)
        ambiguous = cur.fetchone()["ambiguous_count"]

        # Orphan value mappings
        cur.execute("""
            SELECT count(*) AS orphan_total,
                   count(*) FILTER (WHERE am.id IS NULL) AS parent_missing,
                   count(*) FILTER (WHERE am.id IS NOT NULL AND am.is_active = false) AS parent_inactive
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            WHERE am.id IS NULL OR am.is_active = false
        """)
        orphans = dict(cur.fetchone())

        # Inconsistent value targets
        cur.execute("""
            SELECT count(*) AS inconsistent_targets
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            JOIN attribute_values av ON av.id = m.attribute_value_id
            WHERE am.attribute_id IS NOT NULL AND am.is_active = true
              AND av.attribute_id != am.attribute_id
        """)
        inconsistent = cur.fetchone()["inconsistent_targets"]

        return {
            "unassigned_attrs": unassigned["unassigned_attrs"],
            "unassigned_mappings": unassigned["unassigned_mappings"],
            "ambiguous_global": ambiguous,
            "orphans_total": orphans["orphan_total"],
            "orphans_parent_missing": orphans["parent_missing"],
            "orphans_parent_inactive": orphans["parent_inactive"],
            "inconsistent_targets": inconsistent,
        }
    finally:
        conn.close()


@router.get("/mappings/review/attributes")
def list_review_attributes(
    q: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(unassigned|global|mapped|all)$"),
    supplier_id: Optional[int] = None,
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    """List attribute mappings that need review.

    Filters:
      unassigned — internal attr has 0 CategoryAttributes
      global     — active, no category context (may be ambiguous)
      mapped     — with internal target, any status
      all        — everything
    """
    conn, cur = admin_cursor()
    try:
        conds, params = ["1=1"], []

        if supplier_id is not None:
            conds.append("sa.supplier_id = %s"); params.append(supplier_id)

        if status == "unassigned":
            conds.append("""m.attribute_id IS NOT NULL AND m.is_active = true
                AND NOT EXISTS (SELECT 1 FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id)""")
        elif status == "global":
            conds.append("m.attribute_id IS NOT NULL AND m.is_active = true AND m.category_id IS NULL")
        elif status == "mapped":
            conds.append("m.attribute_id IS NOT NULL")

        if q:
            conds.append("(sa.supplier_name ILIKE %s OR a.name ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])

        where = " AND ".join(conds)

        # Count
        cur.execute(f"""
            SELECT count(*) AS c
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            LEFT JOIN attributes a ON a.id = m.attribute_id
            LEFT JOIN suppliers s ON s.id = sa.supplier_id
            WHERE {where}
        """, params)
        total = cur.fetchone()["c"]

        # Rows
        offset = (page - 1) * per_page
        cur.execute(f"""
            SELECT m.id, m.is_active, m.category_id,
                   sa.supplier_name AS supplier_item_name,
                   sa.supplier_id,
                   s.code AS supplier_code, s.name AS supplier_name,
                   a.id AS catalog_item_id, a.name AS catalog_name,
                   (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = a.id) AS attr_category_count,
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_id = a.id) AS attr_product_usage,
                   EXISTS (SELECT 1 FROM category_attributes ca WHERE ca.attribute_id = a.id) AS has_categories,
                   (sa.supplier_id IS NULL) AS is_global
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            LEFT JOIN suppliers s ON s.id = sa.supplier_id
            LEFT JOIN attributes a ON a.id = m.attribute_id
            WHERE {where}
            ORDER BY m.id DESC
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/mappings/review/values")
def list_review_values(
    q: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(orphan|inconsistent|all)$"),
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    """List value mappings that need review.

    Filters:
      orphan       — parent missing or inactive
      inconsistent — parent attr != value attr
      all          — everything (for unfiltered browsing)
    """
    conn, cur = admin_cursor()
    try:
        if status == "orphan":
            rows = _get_orphan_value_mappings(cur, conn, q, page, per_page)
            return rows
        elif status == "inconsistent":
            rows = _get_inconsistent_value_mappings(cur, conn, q, page, per_page)
            return rows
        else:
            rows = _get_all_value_mappings(cur, conn, q, page, per_page)
            return rows
    finally:
        conn.close()


def _get_orphan_value_mappings(cur, conn, q, page, per_page):
    conds = ["(am.id IS NULL OR am.is_active = false)"]
    params = []
    if q:
        conds.append("(ha.supplier_name ILIKE %s OR sav.supplier_value ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = " AND ".join(conds)
    offset = (page - 1) * per_page

    cur.execute(f"""
        SELECT count(*) AS c
        FROM attribute_value_mappings m
        JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
        JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
        LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
        LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
        WHERE {where}
    """, params)
    total = cur.fetchone()["c"]

    cur.execute(f"""
        SELECT m.id, m.is_active,
               ha.supplier_name AS holder_name,
               sav.supplier_value AS supplier_item_name,
               av.value AS catalog_name, av.id AS catalog_item_id,
               am.id AS parent_mapping_id,
               am.is_active AS parent_active,
               am.attribute_id AS parent_attr_id,
               (SELECT a2.name FROM attributes a2 WHERE a2.id = am.attribute_id) AS parent_attr_name,
               CASE WHEN am.id IS NULL THEN 'parent_missing'
                    WHEN am.is_active = false THEN 'parent_inactive'
                    ELSE 'other'
               END AS review_status
        FROM attribute_value_mappings m
        JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
        JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
        LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
        LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
        WHERE {where}
        ORDER BY m.id
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}


def _get_inconsistent_value_mappings(cur, conn, q, page, per_page):
    conds = ["am.attribute_id IS NOT NULL AND am.is_active = true AND av.attribute_id != am.attribute_id"]
    params = []
    if q:
        conds.append("(ha.supplier_name ILIKE %s OR sav.supplier_value ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = " AND ".join(conds)
    offset = (page - 1) * per_page

    cur.execute(f"""
        SELECT count(*) AS c
        FROM attribute_value_mappings m
        JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
        JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
        JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
        JOIN attribute_values av ON av.id = m.attribute_value_id
        WHERE {where}
    """, params)
    total = cur.fetchone()["c"]

    cur.execute(f"""
        SELECT m.id, m.is_active,
               ha.supplier_name AS holder_name,
               sav.supplier_value AS supplier_item_name,
               av.value AS catalog_name, av.id AS catalog_item_id,
               am.id AS parent_mapping_id,
               pa.name AS parent_attr_name, am.attribute_id AS parent_attr_id,
               va.name AS value_attr_name, av.attribute_id AS value_attr_id,
               'inconsistent' AS review_status
        FROM attribute_value_mappings m
        JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
        JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
        JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
        JOIN attribute_values av ON av.id = m.attribute_value_id
        JOIN attributes pa ON pa.id = am.attribute_id
        JOIN attributes va ON va.id = av.attribute_id
        WHERE {where}
        ORDER BY m.id
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}


def _get_all_value_mappings(cur, conn, q, page, per_page):
    conds, params = ["1=1"], []
    if q:
        conds.append("(ha.supplier_name ILIKE %s OR sav.supplier_value ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = " AND ".join(conds)
    offset = (page - 1) * per_page

    cur.execute(f"""
        SELECT count(*) AS c
        FROM attribute_value_mappings m
        JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
        JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
        LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
        LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
        WHERE {where}
    """, params)
    total = cur.fetchone()["c"]

    cur.execute(f"""
        SELECT m.id, m.is_active,
               ha.supplier_name AS holder_name,
               sav.supplier_value AS supplier_item_name,
               av.value AS catalog_name, av.id AS catalog_item_id,
               am.id AS parent_mapping_id,
               am.is_active AS parent_active,
               am.attribute_id AS parent_attr_id,
               (SELECT a2.name FROM attributes a2 WHERE a2.id = am.attribute_id) AS parent_attr_name,
               CASE WHEN am.id IS NULL THEN 'parent_missing'
                    WHEN am.is_active = false THEN 'parent_inactive'
                    WHEN am.attribute_id IS NOT NULL AND av.attribute_id != am.attribute_id THEN 'inconsistent'
                    WHEN am.is_active = true AND am.attribute_id IS NOT NULL AND av.attribute_id = am.attribute_id THEN 'valid'
                    ELSE 'unknown'
               END AS review_status
        FROM attribute_value_mappings m
        JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
        JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
        LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
        LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
        WHERE {where}
        ORDER BY m.id
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    return {"items": cur.fetchall(), "total": total, "page": page, "per_page": per_page}


@router.get("/mappings/review/attributes/{mid}")
def get_review_attribute_detail(
    mid: int, user: dict = Depends(require_admin),
):
    """Get detailed info for an attribute mapping review."""
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            SELECT m.id, m.is_active, m.category_id,
                   sa.supplier_name AS supplier_item_name,
                   sa.supplier_id,
                   s.code AS supplier_code, s.name AS supplier_name,
                   a.id AS attribute_id, a.name AS attribute_name,
                   (sa.supplier_id IS NULL) AS is_global
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            LEFT JOIN suppliers s ON s.id = sa.supplier_id
            LEFT JOIN attributes a ON a.id = m.attribute_id
            WHERE m.id = %s
        """, (mid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")

        # If internal attr exists, get its category usage
        attr_id = row.get("attribute_id")
        if attr_id:
            cur.execute("""
                SELECT c.id, c.name, ca.filterable, ca.required
                FROM category_attributes ca
                JOIN categories c ON c.id = ca.category_id
                WHERE ca.attribute_id = %s
                ORDER BY c.name
            """, (attr_id,))
            row["categories"] = cur.fetchall()
        else:
            row["categories"] = []

        return row
    finally:
        conn.close()


@router.get("/mappings/review/values/{mid}")
def get_review_value_detail(
    mid: int, user: dict = Depends(require_admin),
):
    """Get detailed info for a value mapping review."""
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            SELECT m.id, m.is_active,
                   ha.supplier_name AS holder_name,
                   sav.supplier_value AS supplier_item_name,
                   av.value AS catalog_name, av.id AS catalog_item_id,
                   am.id AS parent_mapping_id,
                   am.is_active AS parent_active,
                   am.attribute_id AS parent_attr_id,
                   (SELECT a2.name FROM attributes a2 WHERE a2.id = am.attribute_id) AS parent_attr_name,
                   av.attribute_id AS value_attr_id,
                   (SELECT a3.name FROM attributes a3 WHERE a3.id = av.attribute_id) AS value_attr_name
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
            LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
            WHERE m.id = %s
        """, (mid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        return row
    finally:
        conn.close()


@router.put("/mappings/review/attributes/{mid}/remap")
def remap_attribute(
    mid: int, attribute_id: int,
    user: dict = Depends(require_admin),
):
    """Remap a supplier attribute mapping to a different internal attribute."""
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id, attribute_id FROM attribute_mappings WHERE id=%s", (mid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")

        cur.execute("SELECT id FROM attributes WHERE id=%s", (attribute_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Атрибут не знайдено")

        cur.execute(
            "UPDATE attribute_mappings SET attribute_id=%s, updated_at=NOW() WHERE id=%s",
            (attribute_id, mid),
        )
        return {"ok": True}
    finally:
        conn.close()


@router.put("/mappings/review/values/{mid}/reassign-value")
def reassign_value_mapping(
    mid: int, attribute_value_id: int,
    user: dict = Depends(require_admin),
):
    """Reassign a value mapping to a different internal value."""
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            SELECT m.id, m.attribute_value_id, am.attribute_id AS parent_attr_id
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            WHERE m.id = %s
        """, (mid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")

        # Validate new value belongs to the parent attribute
        cur.execute(
            "SELECT id FROM attribute_values WHERE id=%s AND attribute_id=%s",
            (attribute_value_id, row["parent_attr_id"]),
        )
        if not cur.fetchone():
            raise HTTPException(
                status_code=422,
                detail="Значення не належить до батьківського атрибута",
            )

        cur.execute(
            "UPDATE attribute_value_mappings SET attribute_value_id=%s, updated_at=NOW() WHERE id=%s",
            (attribute_value_id, mid),
        )
        return {"ok": True}
    finally:
        conn.close()


@router.post("/mappings/review/values/{mid}/link-parent")
def link_value_to_parent(
    mid: int, attribute_mapping_id: int,
    user: dict = Depends(require_admin),
):
    """Link an orphan value mapping to a valid attribute mapping.

    This recreates the parent relationship by updating the
    supplier_attribute_value to point to the correct supplier_attribute.
    """
    conn, cur = admin_cursor()
    try:
        # Get current value mapping
        cur.execute(
            "SELECT supplier_attribute_value_id FROM attribute_value_mappings WHERE id=%s",
            (mid,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")

        # Validate target attribute mapping
        cur.execute(
            "SELECT id, attribute_id, is_active FROM attribute_mappings WHERE id=%s",
            (attribute_mapping_id,),
        )
        target = cur.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Батьківський маппінг не знайдено")
        if not target["is_active"]:
            raise HTTPException(status_code=422, detail="Батьківський маппінг неактивний")

        # The value mapping's supplier_attribute_value must point to the
        # same supplier_attribute as the target mapping to be linked.
        # If they differ, we need to update the supplier_attribute_value
        # or create a new one. For simplicity, validate they share the
        # same supplier attribute name.
        cur.execute(
            """SELECT ha.id, ha.supplier_name
               FROM supplier_attribute_values sav
               JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
               WHERE sav.id = %s
            """, (row["supplier_attribute_value_id"],))
        val_holder = cur.fetchone()

        cur.execute(
            """SELECT ha2.id, ha2.supplier_name
               FROM attribute_mappings am
               JOIN supplier_attributes ha2 ON ha2.id = am.supplier_attribute_id
               WHERE am.id = %s
            """, (attribute_mapping_id,))
        target_holder = cur.fetchone()

        # They must refer to the same supplier attribute
        if val_holder["supplier_name"] != target_holder["supplier_name"]:
            raise HTTPException(
                status_code=422,
                detail=f"Атрибут постачальника не збігається: «{val_holder['supplier_name']}» ≠ «{target_holder['supplier_name']}»",
            )

        # Update the supplier_attribute_value to point to the target
        # supplier_attribute
        cur.execute(
            "UPDATE supplier_attribute_values SET supplier_attribute_id=%s WHERE id=%s",
            (target_holder["id"], row["supplier_attribute_value_id"]),
        )

        # Verify the internal value still matches
        cur.execute(
            "SELECT attribute_value_id FROM attribute_value_mappings WHERE id=%s",
            (mid,),
        )
        vm = cur.fetchone()
        if vm and vm["attribute_value_id"]:
            cur.execute(
                "SELECT id FROM attribute_values WHERE id=%s AND attribute_id=%s",
                (vm["attribute_value_id"], target["attribute_id"]),
            )
            if not cur.fetchone():
                cur.execute("UPDATE attribute_value_mappings SET attribute_value_id=NULL WHERE id=%s", (mid,))

        return {"ok": True}
    finally:
        conn.close()


# ── Grouped Review Endpoints ───────────────────────────────────────────────

@router.get("/mappings/review/groups")
def review_groups(user: dict = Depends(require_admin)):
    """Return grouped review items for the admin workflow.

    Groups:
      inconsistent_values  — grouped by (parent_attr, value_attr)
      orphans              — grouped by (parent_missing, parent_inactive)
      unassigned_attrs     — grouped by internal attribute
      ambiguous_global     — count only (individual items via /review/attributes)
    """
    conn, cur = admin_cursor()
    try:
        # Inconsistent values by (parent_attr, value_attr) group
        cur.execute("""
            SELECT pa.name AS parent_attr_name, pa.id AS parent_attr_id,
                   va.name AS value_attr_name, va.id AS value_attr_id,
                   count(*) AS cnt,
                   string_agg(DISTINCT av.value, ' | ' ORDER BY av.value) AS sample_values,
                   EXISTS (SELECT 1 FROM attribute_values av2
                    WHERE av2.attribute_id = pa.id AND av2.value = av.value) AS matching_exists
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            JOIN attribute_values av ON av.id = m.attribute_value_id
            JOIN attributes pa ON pa.id = am.attribute_id
            JOIN attributes va ON va.id = av.attribute_id
            WHERE am.attribute_id IS NOT NULL AND am.is_active = true
              AND av.attribute_id != am.attribute_id
            GROUP BY pa.name, pa.id, va.name, va.id, av.value
            ORDER BY count(*) DESC
        """)
        rows = cur.fetchall()
        # Re-group by parent_attr
        groups = {}
        for r in rows:
            key = (r["parent_attr_id"], r["parent_attr_name"], r["value_attr_id"], r["value_attr_name"])
            if key not in groups:
                groups[key] = {
                    "parent_attr_id": r["parent_attr_id"],
                    "parent_attr_name": r["parent_attr_name"],
                    "value_attr_id": r["value_attr_id"],
                    "value_attr_name": r["value_attr_name"],
                    "total": 0,
                    "with_matching_value": 0,
                    "without_matching_value": 0,
                    "sample_values": [],
                }
            g = groups[key]
            g["total"] += r["cnt"]
            if r["matching_exists"]:
                g["with_matching_value"] += r["cnt"]
            else:
                g["without_matching_value"] += r["cnt"]
            # Collect a few sample values
            if len(g["sample_values"]) < 5:
                for v in r["sample_values"].split(" | "):
                    if v not in g["sample_values"]:
                        g["sample_values"].append(v)

        # Summary
        cur.execute("""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE am.id IS NULL) AS parent_missing,
                   count(*) FILTER (WHERE am.id IS NOT NULL AND am.is_active = false) AS parent_inactive
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            WHERE am.id IS NULL OR am.is_active = false
        """)
        orphans = dict(cur.fetchone())

        # Ambiguous global attribute mappings
        cur.execute("""
            SELECT count(*) AS ambiguous_count
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            WHERE m.category_id IS NULL
              AND m.attribute_id IS NOT NULL
              AND m.is_active = true
              AND (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id) > 1
        """)
        ambiguous = cur.fetchone()["ambiguous_count"]

        # Unassigned attributes: group by internal attribute
        cur.execute("""
            SELECT a.id AS attr_id, a.name AS attr_name,
                   count(*) AS mapping_count,
                   string_agg(DISTINCT sa.supplier_name, ', ' ORDER BY sa.supplier_name) AS supplier_names,
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_id = a.id) AS product_usage
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            JOIN attributes a ON a.id = m.attribute_id
            WHERE m.category_id IS NULL
              AND m.attribute_id IS NOT NULL
              AND m.is_active = true
              AND NOT EXISTS (SELECT 1 FROM category_attributes ca WHERE ca.attribute_id = a.id)
            GROUP BY a.id, a.name
            ORDER BY a.name
        """)
        unassigned_groups = cur.fetchall()

        return {
            "inconsistent_values": {
                "total": sum(g["total"] for g in groups.values()),
                "groups": list(groups.values()),
            },
            "orphans": orphans,
            "unassigned_attrs": {
                "total": sum(g["mapping_count"] for g in unassigned_groups),
                "groups": unassigned_groups,
            },
            "ambiguous_global": {
                "total": ambiguous,
            },
        }
    finally:
        conn.close()


@router.get("/mappings/review/inconsistent-group/{parent_attr_id}")
def list_inconsistent_group(
    parent_attr_id: int,
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_admin),
):
    """List all inconsistent value mappings for a specific parent attribute."""
    conn, cur = admin_cursor()
    try:
        offset = (page - 1) * per_page
        # Count first
        cur.execute("""
            SELECT count(*) AS c
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            JOIN attribute_values av ON av.id = m.attribute_value_id
            WHERE am.attribute_id = %s
              AND am.is_active = true
              AND av.attribute_id != am.attribute_id
        """, (parent_attr_id,))
        total = cur.fetchone()["c"]
        # Then fetch rows
        cur.execute("""
            SELECT m.id, sav.supplier_value AS supplier_item_name,
                   av.value AS catalog_name, av.id AS attribute_value_id,
                   am.attribute_id AS parent_attr_id,
                   pa.name AS parent_attr_name,
                   av.attribute_id AS value_attr_id,
                   va.name AS value_attr_name,
                   EXISTS (SELECT 1 FROM attribute_values av2
                    WHERE av2.attribute_id = am.attribute_id AND av2.value = av.value) AS matching_exists
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            JOIN attribute_values av ON av.id = m.attribute_value_id
            JOIN attributes pa ON pa.id = am.attribute_id
            JOIN attributes va ON va.id = av.attribute_id
            WHERE am.attribute_id = %s
              AND am.is_active = true
              AND av.attribute_id != am.attribute_id
            ORDER BY sav.supplier_value
            LIMIT %s OFFSET %s
        """, (parent_attr_id, per_page, offset))
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


class BulkReassignRequest(BaseModel):
    mapping_ids: list[int]
    attribute_value_id: int


@router.put("/mappings/review/values/bulk-reassign")
def bulk_reassign_values(
    body: BulkReassignRequest,
    user: dict = Depends(require_admin),
):
    """Bulk reassign multiple value mappings to the same canonical value.

    All-or-nothing transactional operation.
    Validates that the target value belongs to the correct attribute for each.
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Validate ALL mappings first before any write
        parents = []
        for mid in body.mapping_ids:
            cur.execute("""
                SELECT am.attribute_id AS parent_attr_id
                FROM attribute_value_mappings m
                JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
                JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
                WHERE m.id = %s
            """, (mid,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Маппінг {mid} не знайдено")
            parents.append(row["parent_attr_id"])

        # Validate target value belongs to each parent attribute
        for pid in set(parents):
            cur.execute(
                "SELECT id FROM attribute_values WHERE id=%s AND attribute_id=%s",
                (body.attribute_value_id, pid),
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=422,
                    detail="Значення не належить до батьківського атрибута",
                )

        # All validations passed — update all mappings
        for mid in body.mapping_ids:
            cur.execute(
                "UPDATE attribute_value_mappings SET attribute_value_id=%s, updated_at=NOW() WHERE id=%s",
                (body.attribute_value_id, mid),
            )

        conn.commit()
        return {"ok": True, "updated": len(body.mapping_ids)}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


class CreateAndAssignRequest(BaseModel):
    mapping_id: int
    attribute_id: int
    value: str


@router.post("/mappings/review/values/create-and-assign")
def create_value_and_assign(
    body: CreateAndAssignRequest,
    user: dict = Depends(require_admin),
):
    """Create a canonical AttributeValue and assign a mapping to it.

    This is an explicit admin action — never automatic.
    Validates all relationships from the database (never trust frontend IDs).
    """
    value = (body.value or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail="Значення не може бути порожнім")

    conn = psycopg2.connect(DB)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Validate mapping exists and get its parent attribute
        cur.execute("""
            SELECT m.id, am.attribute_id AS parent_attr_id
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            WHERE m.id = %s AND am.is_active = true
        """, (body.mapping_id,))
        mapping = cur.fetchone()
        if not mapping:
            raise HTTPException(status_code=404, detail="Маппінг не знайдено")

        # Verify the provided attribute_id matches the parent mapping's attribute
        if mapping["parent_attr_id"] != body.attribute_id:
            raise HTTPException(
                status_code=422,
                detail="Атрибут не відповідає батьківському маппінгу",
            )

        # Validate attribute exists
        cur.execute("SELECT id FROM attributes WHERE id=%s", (body.attribute_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Атрибут не знайдено")

        # Check for existing value (UNIQUE constraint is final protection)
        cur.execute(
            "SELECT id FROM attribute_values WHERE attribute_id=%s AND value=%s",
            (body.attribute_id, value),
        )
        existing = cur.fetchone()
        if existing:
            av_id = existing["id"]
        else:
            import re
            slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "val"
            cur.execute(
                """INSERT INTO attribute_values (attribute_id, value, slug, sort, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, 0, true, NOW(), NOW()) RETURNING id""",
                (body.attribute_id, value, slug),
            )
            av_id = cur.fetchone()["id"]

        # Assign mapping to this value
        cur.execute(
            "UPDATE attribute_value_mappings SET attribute_value_id=%s, updated_at=NOW() WHERE id=%s",
            (av_id, body.mapping_id),
        )

        conn.commit()
        return {"ok": True, "attribute_value_id": av_id, "created": not existing}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Improved Review Endpoints ─────────────────────────────────────────────

@router.get("/mappings/review/inconsistent-detail/{parent_attr_id}")
def inconsistent_detail(
    parent_attr_id: int,
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_admin),
):
    """Detailed list of inconsistent value mappings with product usage."""
    conn, cur = admin_cursor()
    try:
        offset = (page - 1) * per_page
        total = 0
        cur.execute("""SELECT count(*) AS c FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            WHERE am.attribute_id = %s AND am.is_active = true
              AND EXISTS (SELECT 1 FROM attribute_values av WHERE av.id = m.attribute_value_id AND av.attribute_id != am.attribute_id)""", (parent_attr_id,))
        total = cur.fetchone()["c"]
        cur.execute("""
            SELECT m.id, sav.supplier_value AS supplier_item_name,
                   av.value AS current_value,
                   av.id AS current_av_id,
                   av.attribute_id AS current_attr_id,
                   va.name AS current_attr_name,
                   am.attribute_id AS target_attr_id,
                   pa.name AS target_attr_name,
                   (SELECT count(*) FROM product_attributes pa2 WHERE pa2.attribute_value_id = av.id) AS product_usage,
                   EXISTS (SELECT 1 FROM attribute_values av2
                    WHERE av2.attribute_id = am.attribute_id AND av2.value = av.value) AS matching_exists
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            JOIN attribute_values av ON av.id = m.attribute_value_id
            JOIN attributes pa ON pa.id = am.attribute_id
            JOIN attributes va ON va.id = av.attribute_id
            WHERE am.attribute_id = %s AND am.is_active = true
              AND av.attribute_id != am.attribute_id
            ORDER BY sav.supplier_value
            LIMIT %s OFFSET %s
        """, (parent_attr_id, per_page, offset))
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/mappings/review/orphans")
def orphan_value_mappings(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_admin),
):
    """List orphan value mappings with details."""
    conn, cur = admin_cursor()
    try:
        offset = (page - 1) * per_page
        cur.execute("""SELECT count(*) AS c FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            WHERE am.id IS NULL OR am.is_active = false""")
        total = cur.fetchone()["c"]
        cur.execute("""
            SELECT m.id, ha.supplier_name AS holder_name,
                   sav.supplier_value AS supplier_item_name,
                   av.value AS catalog_name,
                   am.id AS parent_mapping_id,
                   am.is_active AS parent_active,
                   CASE WHEN am.id IS NULL THEN 'parent_missing'
                        WHEN am.is_active = false THEN 'parent_inactive'
                        ELSE 'other'
                   END AS reason,
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_value_id = av.id) AS product_usage
            FROM attribute_value_mappings m
            JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
            JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
            LEFT JOIN attribute_mappings am ON am.supplier_attribute_id = sav.supplier_attribute_id
            LEFT JOIN attribute_values av ON av.id = m.attribute_value_id
            WHERE am.id IS NULL OR am.is_active = false
            ORDER BY ha.supplier_name, sav.supplier_value
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/mappings/review/unassigned")
def unassigned_attribute_mappings(
    user: dict = Depends(require_admin),
):
    """List all unassigned attribute mappings with context."""
    conn, cur = admin_cursor()
    try:
        cur.execute("""
            SELECT a.id AS attr_id, a.name AS attr_name,
                   count(*) AS mapping_count,
                   string_agg(DISTINCT sa.supplier_name, ', ' ORDER BY sa.supplier_name) AS supplier_names,
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_id = a.id) AS product_usage
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            JOIN attributes a ON a.id = m.attribute_id
            WHERE m.category_id IS NULL
              AND m.attribute_id IS NOT NULL
              AND m.is_active = true
              AND NOT EXISTS (SELECT 1 FROM category_attributes ca WHERE ca.attribute_id = a.id)
            GROUP BY a.id, a.name
            ORDER BY a.name
        """)
        groups = cur.fetchall()
        # For each group, get the attribute mappings
        result = []
        for g in groups:
            cur.execute("""
                SELECT m.id, sa.supplier_name AS supplier_attr,
                       m.is_active, m.category_id
                FROM attribute_mappings m
                JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
                WHERE m.attribute_id = %s AND m.is_active = true
                ORDER BY sa.supplier_name
            """, (g["attr_id"],))
            g["mappings"] = cur.fetchall()
            # Find candidate replacement attributes with similar names
            cur.execute("SELECT name FROM attributes WHERE id = %s", (g["attr_id"],))
            attr_name_row = cur.fetchone()
            if attr_name_row:
                search_pattern = f"%{attr_name_row['name']}%"
                cur.execute("""
                    SELECT a.id, a.name, count(ca.id) AS cat_count
                    FROM attributes a
                    JOIN category_attributes ca ON ca.attribute_id = a.id
                    WHERE a.name ILIKE %s
                      AND a.id != %s
                    GROUP BY a.id, a.name
                    ORDER BY cat_count DESC
                    LIMIT 5
                """, (search_pattern, g["attr_id"]))
                g["candidates"] = cur.fetchall()
            else:
                g["candidates"] = []
            g["candidates"] = cur.fetchall()
            result.append(g)
        return {"items": result, "total": len(result)}
    finally:
        conn.close()


@router.get("/mappings/review/ambiguous")
def ambiguous_global_mappings(
    page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_admin),
):
    """List ambiguous global attribute mappings with usage context."""
    conn, cur = admin_cursor()
    try:
        offset = (page - 1) * per_page
        cur.execute("""SELECT count(*) AS c FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            WHERE m.category_id IS NULL AND m.attribute_id IS NOT NULL AND m.is_active = true
              AND (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id) > 1""")
        total = cur.fetchone()["c"]
        cur.execute("""
            SELECT m.id, sa.supplier_name AS supplier_attr,
                   a.name AS internal_attr,
                   (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = a.id) AS cat_count,
                   (SELECT count(*) FROM product_attributes pa WHERE pa.attribute_id = a.id) AS product_usage
            FROM attribute_mappings m
            JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
            JOIN attributes a ON a.id = m.attribute_id
            WHERE m.category_id IS NULL AND m.attribute_id IS NOT NULL AND m.is_active = true
              AND (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = m.attribute_id) > 1
            ORDER BY (SELECT count(DISTINCT ca.category_id) FROM category_attributes ca WHERE ca.attribute_id = a.id) DESC, a.name
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()
_KINDS = {
    "categories": ("category_mappings", "supplier_category_id", "category_id",
                   "supplier_categories", "categories", "supplier_name", "name"),
    "attributes": ("attribute_mappings", "supplier_attribute_id", "attribute_id",
                   "supplier_attributes", "attributes", "supplier_name", "name"),
    "values": ("attribute_value_mappings", "supplier_attribute_value_id", "attribute_value_id",
               "supplier_attribute_values", "attribute_values", "supplier_value", "value"),
}


def _kind_or_404(kind: str):
    if kind not in _KINDS:
        raise HTTPException(status_code=404, detail="Невідомий тип відповідностей")
    return _KINDS[kind]


@router.get("/mappings/{kind}")
def list_mappings(
    kind: str, q: Optional[str] = None, supplier_id: Optional[int] = None,
    active: Optional[bool] = None, mapped: Optional[bool] = None,
    scope: Optional[str] = Query(None, pattern="^(global|supplier)$"),
    internal_category_id: Optional[int] = None,
    has_category_context: Optional[bool] = Query(None, description="Filter by whether category_id is set"),
    sort_by: Optional[str] = None, sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    """Server-side search / filtering / sorting / pagination over mapping rows."""
    L = _list_sql_or_404(kind)
    scope_col = f"{L['scope_alias']}.supplier_id"
    conn, cur = admin_cursor()
    try:
        conds, params = ["TRUE"], []
        if q:
            like = f"%{q}%"
            conds.append("(" + " OR ".join(f"{col} ILIKE %s" for col in L["search"]) + ")")
            params.extend([like] * len(L["search"]))
        if scope == "global":
            conds.append(f"{scope_col} IS NULL")
        elif scope == "supplier":
            conds.append(f"{scope_col} IS NOT NULL")
        if supplier_id:
            conds.append(f"{scope_col} = %s")
            params.append(supplier_id)
        if active is not None:
            conds.append("m.is_active = %s")
            params.append(active)
        if mapped is not None:
            conds.append(f"m.{L['c_fk']} IS " + ("NOT NULL" if mapped else "NULL"))
        if internal_category_id is not None and kind == "attributes":
            conds.append("m.category_id = %s")
            params.append(internal_category_id)
        if has_category_context is not None and kind == "attributes":
            conds.append("m.category_id IS " + ("NOT NULL" if has_category_context else "NULL"))
        where = " AND ".join(conds)

        order_col = L["sort"].get(sort_by or "", L["sort"]["id"])
        direction = "ASC" if sort_dir == "asc" else "DESC"

        base_from = f"FROM {L['table']} m {L['joins']} WHERE {where}"
        sql = f"""SELECT m.id, m.{L['s_fk']} AS supplier_item_id,
                         m.{L['c_fk']} AS catalog_item_id,
                         m.is_active, m.created_at, m.updated_at,
                         s.id AS supplier_id, s.code AS supplier_code,
                         s.name AS supplier_name, {L['select_names']}
                  {base_from}
                  ORDER BY {order_col} {direction} NULLS LAST, m.id {direction}
                  LIMIT %s OFFSET %s"""
        count_sql = f"SELECT COUNT(*) AS c {base_from}"

        cur.execute(count_sql, params)
        total = cur.fetchone()["c"]
        cur.execute(sql, params + [per_page, (page - 1) * per_page])
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


def _ensure_supplier_item(cur, kind: str, sid: int, name: str,
                          parent_name: Optional[str]) -> int:
    """Find or create the supplier-side dictionary row; returns its id."""
    if kind == "categories":
        cur.execute(
            "SELECT id FROM supplier_categories WHERE supplier_id IS NOT DISTINCT FROM %s AND supplier_name=%s",
            (sid, name))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            """INSERT INTO supplier_categories (supplier_id, supplier_name, is_removed,
                                                created_at, updated_at)
               VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id""", (sid, name))
        return cur.fetchone()["id"]

    if kind == "attributes":
        cur.execute(
            "SELECT id FROM supplier_attributes WHERE supplier_id IS NOT DISTINCT FROM %s AND supplier_name=%s",
            (sid, name))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute(
            """INSERT INTO supplier_attributes (supplier_id, supplier_name, is_removed,
                                                created_at, updated_at)
               VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id""", (sid, name))
        return cur.fetchone()["id"]

    # values — a value lives under a holder supplier attribute
    parent_name = (parent_name or "").strip()
    if not parent_name:
        raise HTTPException(status_code=422,
                            detail="Вкажіть атрибут постачальника для значення")
    cur.execute(
        "SELECT id FROM supplier_attributes WHERE supplier_id IS NOT DISTINCT FROM %s AND supplier_name=%s",
        (sid, parent_name))
    prow = cur.fetchone()
    if prow:
        parent_id = prow["id"]
    else:
        cur.execute(
            """INSERT INTO supplier_attributes (supplier_id, supplier_name, is_removed,
                                                created_at, updated_at)
               VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id""", (sid, parent_name))
        parent_id = cur.fetchone()["id"]
    cur.execute(
        """SELECT id FROM supplier_attribute_values
           WHERE supplier_attribute_id=%s AND supplier_value=%s""",
        (parent_id, name))
    vrow = cur.fetchone()
    if vrow:
        return vrow["id"]
    cur.execute(
        """INSERT INTO supplier_attribute_values (supplier_attribute_id, supplier_value,
                                                  is_removed, created_at, updated_at)
           VALUES (%s, %s, FALSE, NOW(), NOW()) RETURNING id""", (parent_id, name))
    return cur.fetchone()["id"]


@router.post("/mappings/{kind}", status_code=201)
def create_mapping(kind: str, body: MappingCreate, user: dict = Depends(require_admin)):
    K = _kind_or_404(kind)
    table, s_fk, c_fk, s_table, c_table = K[0], K[1], K[2], K[3], K[4]
    conn, cur = admin_cursor()
    try:
        # ── resolve the supplier-side item ────────────────────────────────
        if body.supplier_item_id:
            cur.execute(f"SELECT id, supplier_id FROM {s_table} WHERE id = %s",
                        (body.supplier_item_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Запис постачальника не знайдено")
            sid, s_item_id = row["supplier_id"], row["id"]
        else:
            # Global mapping by default: no supplier required.
            name = (body.supplier_item_name or "").strip()
            if not name:
                raise HTTPException(status_code=422,
                                    detail="Вкажіть запис постачальника")
            code = (body.supplier_code or "").strip() or None
            sid = None
            if code is not None:
                if code not in SYSTEM_SUPPLIERS:
                    raise HTTPException(status_code=400,
                                        detail="Невірний постачальник. Доступні: IT-Link, DC-Link")
                cur.execute("SELECT id FROM suppliers WHERE code = %s", (code,))
                srow = cur.fetchone()
                if not srow:
                    raise HTTPException(status_code=404, detail="Постачальника не знайдено")
                sid = srow["id"]
            s_item_id = _ensure_supplier_item(cur, kind, sid, name, body.supplier_parent_name)

        # ── resolve / validate the internal target ─────────────────────────
        target = body.catalog_item_id
        if target is not None:
            cur.execute(f"SELECT 1 FROM {c_table} WHERE id = %s", (target,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Запис каталогу не знайдено")
        if body.is_active and target is None and kind != "values":
            raise HTTPException(
                status_code=422,
                detail="Оберіть внутрішній об'єкт або статус «Не імпортувати»")

        # ── upsert — one mapping per supplier item (migration 013) ─────────
        cur.execute(
            f"""INSERT INTO {table} ({s_fk}, {c_fk}, is_active, created_by_user_id,
                                      category_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT ({s_fk}) DO UPDATE
                    SET {c_fk}     = EXCLUDED.{c_fk},
                        category_id = EXCLUDED.category_id,
                        is_active  = EXCLUDED.is_active,
                        updated_at = NOW()
                RETURNING id, (xmax = 0) AS inserted""",
            (s_item_id, target, body.is_active, user.get("id"), body.category_id),
        )
        row = cur.fetchone()
        return JSONResponse(
            status_code=201 if row["inserted"] else 200,
            content={"id": row["id"], "updated": not row["inserted"]},
        )
    finally:
        conn.close()


@router.put("/mappings/{kind}/{mid}")
def update_mapping(kind: str, mid: int, body: MappingUpdate,
                         clear_target: bool = False,
                         user: dict = Depends(require_admin)):
    K = _kind_or_404(kind)
    table, s_fk, c_fk, _, c_table = K[0], K[1], K[2], K[3], K[4]
    conn, cur = admin_cursor()
    try:
        cur.execute(f"SELECT id FROM {table} WHERE id=%s", (mid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")

        # explicit JSON null (or ?clear_target=true) clears the internal target —
        # that is how a row becomes / stays «Не імпортувати» without a catalog link
        explicit_null = ("catalog_item_id" in getattr(body, "model_fields_set", set())
                         and body.catalog_item_id is None)
        cur.execute(f"SELECT is_active, {c_fk} AS cur_target FROM {table} WHERE id=%s", (mid,))
        current = cur.fetchone()

        if explicit_null or clear_target:
            effective_target = None
        elif body.catalog_item_id is not None:
            effective_target = body.catalog_item_id
        else:
            effective_target = current["cur_target"]

        will_be_active = body.is_active if body.is_active is not None else current["is_active"]
        if effective_target is None and will_be_active and kind != "values":
            raise HTTPException(
                status_code=422,
                detail="Оберіть внутрішній об'єкт або статус «Не імпортувати»")

        if effective_target is not None and effective_target != current["cur_target"]:
            cur.execute(f"SELECT 1 FROM {c_table} WHERE id=%s", (effective_target,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Запис каталогу не знайдено")

        sets, params = ["updated_at=NOW()"], []
        if explicit_null or clear_target:
            sets.append(f"{c_fk}=NULL")
        elif body.catalog_item_id is not None:
            sets.append(f"{c_fk}=%s")
            params.append(body.catalog_item_id)
        if body.is_active is not None:
            sets.append("is_active=%s")
            params.append(body.is_active)
        params.append(mid)
        cur.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id=%s", params)
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/mappings/{kind}/{mid}")
def delete_mapping(kind: str, mid: int, user: dict = Depends(require_admin)):
    table, _, _, _, _, _, _ = _kind_or_404(kind)
    conn, cur = admin_cursor()
    try:
        cur.execute(f"DELETE FROM {table} WHERE id=%s", (mid,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        return {"ok": True}
    finally:
        conn.close()

