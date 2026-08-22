"""Admin mappings API — category/attribute/value mappings between suppliers and the catalog."""
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class MappingCreate(BaseModel):
    supplier_item_id: int
    catalog_item_id: Optional[int] = None
    is_active: bool = True


class MappingUpdate(BaseModel):
    catalog_item_id: Optional[int] = None
    is_active: Optional[bool] = None


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
    active: Optional[bool] = None, page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_admin),
):
    table, s_fk, c_fk, s_table, c_table, s_name, c_name = _kind_or_404(kind)
    conn, cur = db()
    try:
        conds, params = ["1=1"], []
        if q:
            conds.append(f"(s.{s_name} ILIKE %s OR c.{c_name} ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])
        if supplier_id:
            conds.append(f"m.{s_fk} IN (SELECT id FROM {s_table} WHERE supplier_id=%s)")
            params.append(supplier_id)
        if active is not None:
            conds.append("m.is_active=%s"); params.append(active)
        where = " AND ".join(conds)
        sql = f"""SELECT m.id, m.{s_fk}, m.{c_fk}, m.is_active, m.created_at, m.updated_at,
                         s.{s_name} AS supplier_name, c.{c_name} AS catalog_name
                  FROM {table} m
                  JOIN {s_table} s ON s.id=m.{s_fk}
                  LEFT JOIN {c_table} c ON c.id=m.{c_fk}
                  WHERE {where} ORDER BY m.id DESC"""
        count = f"SELECT COUNT(*) AS c FROM {table} m WHERE {where}"
        return _paged(cur, sql, count, params, page, per_page)
    finally:
        conn.close()


@router.post("/mappings/{kind}", status_code=201)
async def create_mapping(kind: str, body: MappingCreate, user: dict = Depends(require_admin)):
    table, s_fk, c_fk, s_table, c_table, _, _ = _kind_or_404(kind)
    if body.catalog_item_id is None and kind != "values":
        raise HTTPException(status_code=422, detail="Потрібно вказати об'єкт каталогу")
    conn, cur = db()
    try:
        cur.execute(f"SELECT 1 FROM {s_table} WHERE id=%s", (body.supplier_item_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Запис постачальника не знайдено")
        if body.catalog_item_id is not None:
            cur.execute(f"SELECT 1 FROM {c_table} WHERE id=%s", (body.catalog_item_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Запис каталогу не знайдено")
        # one mapping per supplier item — update instead of duplicating
        cur.execute(f"SELECT id FROM {table} WHERE {s_fk}=%s", (body.supplier_item_id,))
        existing = cur.fetchone()
        if existing:
            cur.execute(f"UPDATE {table} SET {c_fk}=%s, is_active=%s, updated_at=NOW() WHERE id=%s",
                        (body.catalog_item_id, body.is_active, existing["id"]))
            return {"id": existing["id"], "updated": True}
        cur.execute(f"""INSERT INTO {table} ({s_fk}, {c_fk}, is_active, created_by_user_id)
                        VALUES (%s, %s, %s, %s) RETURNING id""",
                    (body.supplier_item_id, body.catalog_item_id, body.is_active, user.get("id")))
        return {"id": cur.fetchone()["id"], "updated": False}
    finally:
        conn.close()


@router.put("/mappings/{kind}/{mid}")
async def update_mapping(kind: str, mid: int, body: MappingUpdate,
                         user: dict = Depends(require_admin)):
    table, s_fk, c_fk, _, c_table, _, _ = _kind_or_404(kind)
    conn, cur = db()
    try:
        cur.execute(f"SELECT id FROM {table} WHERE id=%s", (mid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Відповідність не знайдено")
        if body.catalog_item_id is not None:
            cur.execute(f"SELECT 1 FROM {c_table} WHERE id=%s", (body.catalog_item_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Запис каталогу не знайдено")
        sets, params = ["updated_at=NOW()"], []
        if body.catalog_item_id is not None:
            sets.append(f"{c_fk}=%s"); params.append(body.catalog_item_id)
        if body.is_active is not None:
            sets.append("is_active=%s"); params.append(body.is_active)
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

