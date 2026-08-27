"""Admin authentication API."""
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor, get_cursor
from app.core.security import verify_password

router = APIRouter()


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(req: LoginRequest, request: Request):
    """Authenticate an admin/staff user and issue a session token."""
    conn, cur = admin_cursor()
    try:
        cur.execute(
            "SELECT id, email, password_hash, full_name, role, status FROM users WHERE lower(email) = %s",
            (req.email.strip().lower(),),
        )
        user = cur.fetchone()

        # Uniform 401 for unknown email / bad password / non-admin users.
        if (
            not user
            or not verify_password(req.password, user["password_hash"])
            or user["role"] not in ("ADMIN", "STAFF")
            or user["status"] != "ACTIVE"
        ):
            raise HTTPException(status_code=401, detail="Невірна електронна пошта або пароль")

        token = secrets.token_urlsafe(32)
        th = hashlib.sha256(token.encode()).hexdigest()
        cur.execute(
            """
            INSERT INTO sessions (token_hash, user_id, expires_at, ip, user_agent,
                                  created_at, updated_at, last_activity_at)
            VALUES (%s, %s, NOW() + INTERVAL '7 days', %s, %s, NOW(), NOW(), NOW())
            """,
            (
                th,
                user["id"],
                request.client.host if request.client else None,
                (request.headers.get("user-agent") or "")[:500],
            ),
        )
        cur.execute(
            "UPDATE users SET last_login_at = NOW(), login_count = COALESCE(login_count, 0) + 1 WHERE id = %s",
            (user["id"],),
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
            },
        }
    finally:
        conn.close()


@router.get("/me")
def me(user: dict = Depends(require_admin)):
    """Return the authenticated admin user."""
    return {k: user[k] for k in ("id", "email", "full_name", "phone", "role", "status")}


@router.post("/logout")
def logout(request: Request, user: dict = Depends(require_admin)):
    """Invalidate the current session token."""
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    cur = get_cursor()
    try:
        th = hashlib.sha256(token.encode()).hexdigest()
        cur.execute("DELETE FROM sessions WHERE token_hash = %s", (th,))
        cur.connection.commit()
    finally:
        cur.connection.close()
    return {"ok": True}

