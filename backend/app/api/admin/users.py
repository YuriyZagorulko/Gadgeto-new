"""Admin users API (customer & staff account administration)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin, require_admin_role
from app.core.db_connect import admin_cursor

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


USER_ROLES = ("CUSTOMER", "STAFF", "ADMIN")
# Must match the DB enum userstatus: {ACTIVE, INACTIVE, PENDING, BANNED}
USER_STATUSES = ("ACTIVE", "INACTIVE", "PENDING", "BANNED")

# Whitelist of sortable column names → SQL expressions
SORT_COLUMNS = {
    "email": "u.email",
    "name": "u.full_name",
    "phone": "u.phone",
    "role": "u.role",
    "status": "u.status",
    "orders": "orders_count",
    "last_login": "u.last_login_at",
    "registered": "u.created_at",
}


class UserUpdate(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = Query("desc"),
    user: dict = Depends(require_admin),
):
    """Paginated user list with sorting, search and filtering. Never exposes password hashes."""
    conn, cur = admin_cursor()
    try:
        conds, params = ["1=1"], []
        if q:
            conds.append("(u.email ILIKE %s OR u.full_name ILIKE %s OR u.phone ILIKE %s)")
            like = f"%{q}%"
            params.extend([like, like, like])
        if role:
            conds.append("u.role = %s")
            params.append(role)
        if status:
            conds.append("u.status = %s")
            params.append(status)
        where = " AND ".join(conds)

        # Validate and build ORDER BY
        if sort_by and sort_by not in SORT_COLUMNS:
            raise HTTPException(status_code=400, detail=f"Невірне поле для сортування: {sort_by}")
        if sort_order not in ("asc", "desc"):
            sort_order = "desc"

        if sort_by:
            order_expr = SORT_COLUMNS[sort_by]
            order_clause = f"{order_expr} {sort_order.upper()}"
        else:
            order_clause = "u.created_at DESC"

        cur.execute(f"SELECT COUNT(*) AS c FROM users u WHERE {where}", params)
        total = cur.fetchone()["c"]

        offset = (page - 1) * per_page
        cur.execute(
            f"""
            SELECT u.id, u.email, u.full_name, u.phone, u.role, u.status,
                   u.email_verified_at, u.last_login_at, u.login_count,
                   u.created_at,
                   (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS orders_count
            FROM users u
            WHERE {where}
            ORDER BY {order_clause}
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/users/{user_id}")
def get_user(user_id: int, user: dict = Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.phone, u.role, u.status,
                   u.email_verified_at, u.last_login_at, u.login_count,
                   u.created_at, u.updated_at,
                   (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) AS orders_count,
                   (SELECT COALESCE(SUM(total_amount), 0) FROM orders o WHERE o.user_id = u.id) AS orders_total
            FROM users u WHERE u.id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Користувача не знайдено")
        return row
    finally:
        conn.close()


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    user: dict = Depends(require_admin),
):
    """Change role/status. An admin cannot demote or block their own account."""
    if data.role is not None and data.role not in USER_ROLES:
        raise HTTPException(status_code=400, detail="Невірна роль")
    if data.status is not None and data.status not in USER_STATUSES:
        raise HTTPException(status_code=400, detail="Невірний статус")

    if user["id"] == user_id:
        if data.role and data.role != "ADMIN":
            raise HTTPException(status_code=400, detail="Не можна змінити власну роль")
        if data.status and data.status != "ACTIVE":
            raise HTTPException(status_code=400, detail="Не можна деактивувати власний акаунт")

    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Користувача не знайдено")

        sets, params = [], []
        if data.role is not None:
            sets.append("role = %s")
            params.append(data.role)
        if data.status is not None:
            sets.append("status = %s")
            params.append(data.status)
        sets.append("updated_at = NOW()")
        params.append(user_id)

        cur.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = %s", params)
        cur.execute(
            "SELECT id, email, role, status FROM users WHERE id = %s", (user_id,)
        )
        return cur.fetchone()
    finally:
        conn.close()

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    user: dict = Depends(require_admin_role),
):
    """Delete a user. Only ADMIN role can delete users.

    - Self-deletion is forbidden.
    - The last administrator in the system cannot be deleted.
    - Related sessions, carts, cart items and shipping addresses are deleted.
    - Orders are preserved (user_id set to NULL to keep financial records).
    - Product reviews are preserved (ON DELETE SET NULL in DB).
    - Mapping audit records (created_by_user_id) are set to NULL.
    """
    conn, cur = admin_cursor()
    try:
        # 1. Prevent self-deletion
        if user["id"] == user_id:
            raise HTTPException(
                status_code=400,
                detail="Неможливо видалити поточний обліковий запис адміністратора.",
            )

        # 2. Load target user
        cur.execute(
            "SELECT id, email, role, status FROM users WHERE id = %s",
            (user_id,),
        )
        target = cur.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Користувача не знайдено")

        # 3. Prevent deleting the last ADMIN
        if target["role"] == "ADMIN":
            cur.execute(
                "SELECT COUNT(*) AS c FROM users WHERE role = 'ADMIN' AND status = 'ACTIVE'",
            )
            admin_count = cur.fetchone()["c"]
            if admin_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Неможливо видалити останнього адміністратора системи.",
                )

        # 4. Handle related records

        # 4a. Delete sessions (ephemeral, safe to remove)
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))

        # 4b. Delete carts and their items
        cur.execute("SELECT id FROM carts WHERE user_id = %s", (user_id,))
        cart_ids = [r["id"] for r in cur.fetchall()]
        for cid in cart_ids:
            cur.execute("DELETE FROM cart_items WHERE cart_id = %s", (cid,))
            cur.execute("DELETE FROM carts WHERE id = %s", (cid,))

        # 4c. Delete shipping addresses (exclusive to the user)
        cur.execute("DELETE FROM shipping_addresses WHERE user_id = %s", (user_id,))

        # 4d. Set orders.user_id to NULL (preserve financial/business records)
        cur.execute(
            "UPDATE orders SET user_id = NULL, updated_at = NOW() WHERE user_id = %s",
            (user_id,),
        )

        # 4e. Set mapping created_by_user_id to NULL (audit trail integrity)
        cur.execute(
            "UPDATE category_mappings SET created_by_user_id = NULL WHERE created_by_user_id = %s",
            (user_id,),
        )
        cur.execute(
            "UPDATE attribute_mappings SET created_by_user_id = NULL WHERE created_by_user_id = %s",
            (user_id,),
        )
        cur.execute(
            "UPDATE attribute_value_mappings SET created_by_user_id = NULL WHERE created_by_user_id = %s",
            (user_id,),
        )

        # 4f. Product reviews: ON DELETE SET NULL is handled at DB level; no action needed.

        # 5. Finally delete the user
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))

        return {"ok": True, "detail": f"Користувача {target['email']} видалено."}
    finally:
        conn.close()
