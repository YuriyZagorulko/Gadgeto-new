"""Admin mappings API — category/attribute/value mappings between suppliers and the catalog."""
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import DB
from app.imports.registry import SUPPLIERS as SYSTEM_SUPPLIERS

router = APIRouter()


def db():
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class MappingCreate(BaseModel):
    supplier_code: Optional[str] = None
    supplier_item_id: Optional[int] = None
    supplier_item_name: Optional[str] = None
    # values kind only: holder attribute name for a brand-new supplier value
    supplier_parent_name: Optional[str] = None
    catalog_item_id: Optional[int] = None
    is_active: bool = True


class MappingUpdate(BaseModel):
    catalog_item_id: Optional[int] = None
    is_active: Optional[bool] = None


# Server-side sortable columns per mapping kind (whitelisted SQL expressions).
_LIST_SQL = {
    "categories": {
        "table": "category_mappings", "s_fk": "supplier_category_id", "c_fk": "category_id",
        "s_table": "supplier_categories", "c_table": "categories",
        "joins": """JOIN supplier_categories sc ON sc.id = m.supplier_category_id
                    JOIN suppliers s ON s.id = sc.supplier_id
                    LEFT JOIN categories c ON c.id = m.category_id""",
        "select_names": "sc.supplier_name AS supplier_item_name, c.name AS catalog_name",
        "search": ["sc.supplier_name", "s.code", "c.name"],
        "sort": {
            "id": "m.id", "supplier": "s.name", "supplier_code": "s.code",
            "supplier_item": "sc.supplier_name", "catalog": "c.name",
            "status": "m.is_active", "updated_at": "m.updated_at",
        },
    },
    "attributes": {
        "table": "attribute_mappings", "s_fk": "supplier_attribute_id", "c_fk": "attribute_id",
        "s_table": "supplier_attributes", "c_table": "attributes",
        "joins": """JOIN supplier_attributes sa ON sa.id = m.supplier_attribute_id
                    JOIN suppliers s ON s.id = sa.supplier_id
                    LEFT JOIN attributes a ON a.id = m.attribute_id""",
        "select_names": "sa.supplier_name AS supplier_item_name, a.name AS catalog_name",
        "search": ["sa.supplier_name", "s.code", "a.name"],
        "sort": {
            "id": "m.id", "supplier": "s.name", "supplier_code": "s.code",
            "supplier_item": "sa.supplier_name", "catalog": "a.name",
            "status": "m.is_active", "updated_at": "m.updated_at",
        },
    },
    "values": {
        "table": "attribute_value_mappings", "s_fk": "supplier_attribute_value_id",
        "c_fk": "attribute_value_id",
        "s_table": "supplier_attribute_values", "c_table": "attribute_values",
        "joins": """JOIN supplier_attribute_values sav ON sav.id = m.supplier_attribute_value_id
                    JOIN supplier_attributes ha ON ha.id = sav.supplier_attribute_id
                    JOIN suppliers s ON s.id = ha.supplier_id
                    LEFT JOIN attribute_values av ON av.id = m.attribute_value_id""",
        "select_names": """ha.supplier_name AS holder_name,
                           sav.supplier_value AS supplier_item_name, av.value AS catalog_name""",
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
async def lookup_supplier_categories(
    supplier_id: Optional[int] = None, q: Optional[str] = None,
    unmapped: bool = False, page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    conn, cur = db()
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
async def lookup_supplier_attributes(
    supplier_id: Optional[int] = None, q: Optional[str] = None,
    unmapped: bool = False, page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    conn, cur = db()
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
async def lookup_supplier_values(
    attribute_id: Optional[int] = None, q: Optional[str] = None,
    unmapped: bool = False, page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    conn, cur = db()
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
async def list_mappings(
    kind: str, q: Optional[str] = None, supplier_id: Optional[int] = None,
    active: Optional[bool] = None,
    sort_by: Optional[str] = None, sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    """Server-side search / sorting / pagination over mapping rows."""
    L = _list_sql_or_404(kind)
    conn, cur = db()
    try:
        conds, params = ["TRUE"], []
        if q:
            like = f"%{q}%"
            conds.append("(" + " OR ".join(f"{col} ILIKE %s" for col in L["search"]) + ")")
            params.extend([like] * len(L["search"]))
        if supplier_id:
            conds.append("s.id = %s")
            params.append(supplier_id)
        if active is not None:
            conds.append("m.is_active = %s")
            params.append(active)
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
            "SELECT id FROM supplier_categories WHERE supplier_id=%s AND supplier_name=%s",
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
            "SELECT id FROM supplier_attributes WHERE supplier_id=%s AND supplier_name=%s",
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
        "SELECT id FROM supplier_attributes WHERE supplier_id=%s AND supplier_name=%s",
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
async def create_mapping(kind: str, body: MappingCreate, user: dict = Depends(require_admin)):
    K = _kind_or_404(kind)
    table, s_fk, c_fk, s_table, c_table = K[0], K[1], K[2], K[3], K[4]
    conn, cur = db()
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
            code = (body.supplier_code or "").strip()
            name = (body.supplier_item_name or "").strip()
            if not code or not name:
                raise HTTPException(status_code=422,
                                    detail="Вкажіть постачальника та запис постачальника")
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
                                      created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT ({s_fk}) DO UPDATE
                    SET {c_fk}     = EXCLUDED.{c_fk},
                        is_active  = EXCLUDED.is_active,
                        updated_at = NOW()
                RETURNING id, (xmax = 0) AS inserted""",
            (s_item_id, target, body.is_active, user.get("id")),
        )
        row = cur.fetchone()
        return JSONResponse(
            status_code=201 if row["inserted"] else 200,
            content={"id": row["id"], "updated": not row["inserted"]},
        )
    finally:
        conn.close()


@router.put("/mappings/{kind}/{mid}")
async def update_mapping(kind: str, mid: int, body: MappingUpdate,
                         clear_target: bool = False,
                         user: dict = Depends(require_admin)):
    K = _kind_or_404(kind)
    table, s_fk, c_fk, _, c_table = K[0], K[1], K[2], K[3], K[4]
    conn, cur = db()
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
async def delete_mapping(kind: str, mid: int, user: dict = Depends(require_admin)):
    table, _, _, _, _, _, _ = _kind_or_404(kind)
    conn, cur = db()
    try:
        cur.execute(f"DELETE FROM {table} WHERE id=%s", (mid,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        return {"ok": True}
    finally:
        conn.close()

