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

# ── CategoryAttributeValue endpoints ────────────────────────────────────────

@router.get("/categories/{cid}/attributes/{caid}/values")
async def list_category_attribute_values(
    cid: int, caid: int,
    user: dict = Depends(require_admin),
):
    """List all canonical AttributeValues assigned to this CategoryAttribute."""
    conn, cur = db()
    try:
        cur.execute(
            "SELECT id FROM category_attributes WHERE id=%s AND category_id=%s",
            (caid, cid),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="\u0417\u0430\u043f\u0438\u0441 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        cur.execute(
            """
            SELECT cav.id, cav.attribute_value_id, av.value, av.slug,
                   av.sort, av.is_active,
                   (SELECT count(*) FROM product_attributes pa
                    JOIN product_categories pc ON pc.product_id = pa.product_id
                    WHERE pa.attribute_value_id = av.id
                      AND pc.category_id = %s
                   ) AS product_count_in_category
            FROM category_attribute_values cav
            JOIN attribute_values av ON av.id = cav.attribute_value_id
            WHERE cav.category_attribute_id = %s
            ORDER BY av.sort, av.value
            """,
            (cid, caid),
        )
        return {"items": cur.fetchall()}
    finally:
        conn.close()


@router.post("/categories/{cid}/attributes/{caid}/values")
async def add_value_to_category_attribute(
    cid: int, caid: int,
    attribute_value_id: int,
    user: dict = Depends(require_admin),
):
    """Add a canonical AttributeValue to a CategoryAttribute.

    Validates:
      - CategoryAttribute exists for this category
      - AttributeValue exists
      - AttributeValue.attribute_id == CategoryAttribute.attribute_id
    """
    conn, cur = db()
    try:
        # Get CategoryAttribute to verify ownership and get the attribute_id
        cur.execute(
            "SELECT id, attribute_id FROM category_attributes WHERE id=%s AND category_id=%s",
            (caid, cid),
        )
        ca = cur.fetchone()
        if not ca:
            raise HTTPException(status_code=404, detail="\u0417\u0430\u043f\u0438\u0441 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        # Verify the attribute value exists and belongs to the same attribute
        cur.execute(
            "SELECT id, attribute_id FROM attribute_values WHERE id=%s",
            (attribute_value_id,),
        )
        av = cur.fetchone()
        if not av:
            raise HTTPException(status_code=404, detail="\u0417\u043d\u0430\u0447\u0435\u043d\u043d\u044f \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        if av["attribute_id"] != ca["attribute_id"]:
            raise HTTPException(
                status_code=422,
                detail="\u0417\u043d\u0430\u0447\u0435\u043d\u043d\u044f \u043d\u0435 \u043d\u0430\u043b\u0435\u0436\u0438\u0442\u044c \u0434\u043e \u0446\u044c\u043e\u0433\u043e \u0430\u0442\u0440\u0438\u0431\u0443\u0442\u0430",
            )

        try:
            cur.execute(
                """INSERT INTO category_attribute_values
                    (category_attribute_id, attribute_value_id, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                RETURNING id""",
                (caid, attribute_value_id),
            )
            return {"ok": True, "id": cur.fetchone()["id"]}
        except psycopg2.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="\u0417\u043d\u0430\u0447\u0435\u043d\u043d\u044f \u0432\u0436\u0435 \u0434\u043e\u0434\u0430\u043d\u043e \u0434\u043e \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457")
    finally:
        conn.close()


@router.post("/categories/{cid}/attributes/{caid}/values/bulk")
async def bulk_add_values_to_category_attribute(
    cid: int, caid: int,
    attribute_value_ids: list[int],
    user: dict = Depends(require_admin),
):
    """Add multiple AttributeValues to a CategoryAttribute at once."""
    conn, cur = db()
    try:
        cur.execute(
            "SELECT id, attribute_id FROM category_attributes WHERE id=%s AND category_id=%s",
            (caid, cid),
        )
        ca = cur.fetchone()
        if not ca:
            raise HTTPException(status_code=404, detail="\u0417\u0430\u043f\u0438\u0441 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        created = 0
        skipped = 0
        for avid in attribute_value_ids:
            try:
                cur.execute(
                    "SELECT id, attribute_id FROM attribute_values WHERE id=%s",
                    (avid,),
                )
                av = cur.fetchone()
                if not av or av["attribute_id"] != ca["attribute_id"]:
                    skipped += 1
                    continue
                cur.execute(
                    """INSERT INTO category_attribute_values
                        (category_attribute_id, attribute_value_id, created_at, updated_at)
                    VALUES (%s, %s, NOW(), NOW())
                    ON CONFLICT (category_attribute_id, attribute_value_id) DO NOTHING""",
                    (caid, avid),
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


@router.delete("/categories/{cid}/attributes/{caid}/values/{cavid}")
async def remove_value_from_category_attribute(
    cid: int, caid: int, cavid: int,
    user: dict = Depends(require_admin),
):
    """Remove a value from a CategoryAttribute.

    This removes only the CategoryAttributeValue bridge.
    It does NOT delete the canonical AttributeValue.
    """
    conn, cur = db()
    try:
        cur.execute(
            "DELETE FROM category_attribute_values WHERE id=%s AND category_attribute_id=%s",
            (cavid, caid),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="\u0417\u0430\u043f\u0438\u0441 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")
        return {"ok": True}
    finally:
        conn.close()


@router.get("/categories/{cid}/attributes/{caid}/available-values")
async def list_available_values_for_category_attribute(
    cid: int, caid: int,
    q: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """List canonical values that are NOT yet assigned to this CategoryAttribute.

    This allows the administrator to search and add missing values.
    """
    conn, cur = db()
    try:
        cur.execute(
            "SELECT attribute_id FROM category_attributes WHERE id=%s AND category_id=%s",
            (caid, cid),
        )
        ca = cur.fetchone()
        if not ca:
            raise HTTPException(status_code=404, detail="\u0417\u0430\u043f\u0438\u0441 \u043d\u0435 \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u043e")

        conds, params = ["av.attribute_id = %s"], [ca["attribute_id"]]
        if q:
            conds.append("av.value ILIKE %s")
            params.append(f"%{q}%")

        where = " AND ".join(conds)
        cur.execute(
            f"""SELECT av.id, av.value, av.slug, av.is_active
                FROM attribute_values av
                WHERE {where}
                  AND av.is_active = true
                  AND NOT EXISTS (
                      SELECT 1 FROM category_attribute_values cav
                      WHERE cav.category_attribute_id = %s
                        AND cav.attribute_value_id = av.id
                  )
                ORDER BY av.sort, av.value
                LIMIT 200""",
            params + [caid],
        )
        return {"items": cur.fetchall()}
    finally:
        conn.close()
