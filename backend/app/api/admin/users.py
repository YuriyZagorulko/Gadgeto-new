"""Admin users API (customer & staff account administration)."""
import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.api.admin.deps import require_admin
from app.core.db_connect import DB

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


USER_ROLES = ("CUSTOMER", "STAFF", "ADMIN")
# Must match the DB enum userstatus: {ACTIVE, INACTIVE, PENDING, BANNED}
USER_STATUSES = ("ACTIVE", "INACTIVE", "PENDING", "BANNED")


class UserUpdate(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Paginated user list. Never exposes password hashes."""
    conn, cur = db()
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
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        items = cur.fetchall()
        return {"items": items, "total": total, "page": page, "per_page": per_page}
    finally:
        conn.close()


@router.get("/users/{user_id}")
async def get_user(user_id: int, user: dict = Depends(require_admin)):
    conn, cur = db()
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
async def update_user(
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

    conn, cur = db()
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

