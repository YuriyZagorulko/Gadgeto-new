"""Shared dependencies for admin API: token-based authentication/authorization."""
import hashlib
from typing import Optional

from fastapi import Depends, HTTPException, Request

from app.core.db_connect import get_cursor


def get_user_from_token(token: str) -> Optional[dict]:
    """Resolve a session token (as issued by /auth/login) to an active user."""
    cur = get_cursor()
    try:
        th = hashlib.sha256(token.encode()).hexdigest()
        cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.phone, u.role, u.status
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > NOW()
            """,
            (th,),
        )
        return cur.fetchone()
    finally:
        cur.connection.close()


def require_admin(request: Request) -> dict:
    """FastAPI dependency: valid Bearer session token belonging to staff/admin."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Необхідна автентифікація")
    user = get_user_from_token(auth[7:].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Сесію не знайдено або термін її дії закінчився")
    if user["status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail="Обліковий запис деактивовано")
    if user["role"] not in ("ADMIN", "STAFF"):
        raise HTTPException(status_code=403, detail="Немає доступу до адмін-панелі")
    return user


def require_admin_role(user: dict = Depends(require_admin)) -> dict:
    """Dependency for admin-only operations (role management, settings, deletes)."""
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Потрібні права адміністратора")
    return user
