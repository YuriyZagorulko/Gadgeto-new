"""Admin CategoryAttribute API — manage attribute/category relationships.

Follows the existing psycopg2 raw-SQL pattern used by the rest of the admin API.

Routes:
    GET    /categories/{cid}/attributes       — list attributes for a category
    POST   /categories/{cid}/attributes        — add an attribute to a category
    PUT    /categories/{cid}/attributes/{caid} — update CategoryAttribute config
    DELETE /categories/{cid}/attributes/{caid} — remove attribute from category
"""
from typing import Optional
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class CategoryAttributeCreate(BaseModel):
    attribute_id: int
    required: bool = False
    multiple: bool = False
    filterable: bool = True
    searchable: bool = False
    sort_order: int = 0
    filter_type: Optional[str] = None


class CategoryAttributeUpdate(BaseModel):
    required: Optional[bool] = None
    multiple: Optional[bool] = None
    filterable: Optional[bool] = None
    searchable: Optional[bool] = None
    sort_order: Optional[int] = None
    filter_type: Optional[str] = None


class CategoryAttributeBulkAssign(BaseModel):
    attribute_ids: list[int]
    required: bool = False
    multiple: bool = False
    filterable: bool = True
    searchable: bool = False
    sort_order: int = 0
    filter_type: Optional[str] = None

@router.get("/categories/{cid}/attributes")
async def list_category_attributes(
    cid: int,
    filterable_only: bool = False,
    user: dict = Depends(require_admin),
):
    """List all CategoryAttributes for a category."""
    conn, cur = db()
    try:
        cur.execute("SELECT id FROM categories WHERE id=%s", (cid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u044e \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        extra_where = "AND ca.filterable = true" if filterable_only else ""

        cur.execute(f"""
            SELECT ca.id, ca.category_id, ca.attribute_id,
                   ca.required, ca.multiple, ca.filterable, ca.searchable,
                   ca.sort_order, ca.filter_type,
                   a.name AS attribute_name, a.slug AS attribute_slug,
                   a.type AS attribute_type,
                   (SELECT count(*) FROM attribute_values av
                    WHERE av.attribute_id = a.id AND av.is_active = true
                   ) AS values_count
            FROM category_attributes ca
            JOIN attributes a ON a.id = ca.attribute_id
            WHERE ca.category_id = %s {extra_where}
            ORDER BY ca.sort_order, a.name, ca.id
        """, (cid,))
        items = cur.fetchall()
        return {"items": items}
    finally:
        conn.close()


@router.post("/categories/{cid}/attributes")
async def add_attribute_to_category(
    cid: int,
    data: CategoryAttributeCreate,
    user: dict = Depends(require_admin),
):
    """Add an attribute to a category (create CategoryAttribute)."""
    conn, cur = db()
    try:
        cur.execute("SELECT id FROM categories WHERE id=%s", (cid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u044e \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")
        cur.execute("SELECT id, name FROM attributes WHERE id=%s", (data.attribute_id,))
        attr_row = cur.fetchone()
        if not attr_row:
            raise HTTPException(status_code=404, detail="\u0410\u0442\u0440\u0438\u0431\u0443\u0442 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        cur.execute(
            "SELECT id FROM category_attributes WHERE category_id=%s AND attribute_id=%s",
            (cid, data.attribute_id),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail=f"\u0410\u0442\u0440\u0438\u0431\u0443\u0442 \u00ab{attr_row['name']}\u00bb \u0432\u0436\u0435 \u0434\u043e\u0434\u0430\u043d\u043e \u0434\u043e \u0446\u0456\u0454\u0457 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457",
            )

        cur.execute(
            """INSERT INTO category_attributes
                (category_id, attribute_id, required, multiple,
                 filterable, searchable, sort_order, filter_type,
                 created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            RETURNING id""",
            (cid, data.attribute_id, data.required, data.multiple,
             data.filterable, data.searchable, data.sort_order, data.filter_type),
        )
        new_id = cur.fetchone()["id"]
        return {"ok": True, "id": new_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=409, detail=f"\u0410\u0442\u0440\u0438\u0431\u0443\u0442 \u0432\u0436\u0435 \u0434\u043e\u0434\u0430\u043d\u043e: {e}")
    finally:
        conn.close()

@router.post("/categories/{cid}/attributes/bulk")
async def bulk_assign_attributes(
    cid: int,
    data: CategoryAttributeBulkAssign,
    user: dict = Depends(require_admin),
):
    """Assign multiple attributes to a category at once."""
    conn, cur = db()
    try:
        cur.execute("SELECT id FROM categories WHERE id=%s", (cid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u044e \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        created = 0
        skipped = 0
        for attr_id in data.attribute_ids:
            try:
                cur.execute(
                    """INSERT INTO category_attributes
                        (category_id, attribute_id, required, multiple,
                         filterable, searchable, sort_order, filter_type,
                         created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                    ON CONFLICT (category_id, attribute_id) DO NOTHING""",
                    (cid, attr_id, data.required, data.multiple,
                     data.filterable, data.searchable, data.sort_order,
                     data.filter_type),
                )
                if cur.rowcount > 0:
                    created += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        return {"ok": True, "created": created, "skipped": skipped}
    finally:
        conn.close()


@router.put("/categories/{cid}/attributes/{caid}")
async def update_category_attribute(
    cid: int,
    caid: int,
    data: CategoryAttributeUpdate,
    user: dict = Depends(require_admin),
):
    """Update CategoryAttribute configuration."""
    conn, cur = db()
    try:
        cur.execute(
            "SELECT id FROM category_attributes WHERE id=%s AND category_id=%s",
            (caid, cid),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="\u0417\u0430\u043f\u0438\u0441 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e \u0432 \u0446\u0456\u0439 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457")

        sets, params = [], []
        if data.required is not None:
            sets.append("required=%s"); params.append(data.required)
        if data.multiple is not None:
            sets.append("multiple=%s"); params.append(data.multiple)
        if data.filterable is not None:
            sets.append("filterable=%s"); params.append(data.filterable)
        if data.searchable is not None:
            sets.append("searchable=%s"); params.append(data.searchable)
        if data.sort_order is not None:
            sets.append("sort_order=%s"); params.append(data.sort_order)
        if data.filter_type is not None:
            sets.append("filter_type=%s"); params.append(data.filter_type)
        if not sets:
            return {"ok": True}

        params.append(caid)
        cur.execute(
            f"UPDATE category_attributes SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s",
            params,
        )
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/categories/{cid}/attributes/{caid}")
async def remove_attribute_from_category(
    cid: int,
    caid: int,
    user: dict = Depends(require_admin),
):
    """Remove an attribute from a category.

    Deletes the CategoryAttribute row.  Does NOT delete the canonical
    Attribute or any product data.  CategoryAttributeValue children
    are cascade-deleted automatically.
    """
    conn, cur = db()
    try:
        cur.execute(
            "SELECT id FROM category_attributes WHERE id=%s AND category_id=%s",
            (caid, cid),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="\u0417\u0430\u043f\u0438\u0441 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        cur.execute("DELETE FROM category_attributes WHERE id=%s", (caid,))
        return {"ok": True}
    finally:
        conn.close()
