"""Customer authentication API (separate from admin auth)."""
import secrets, hashlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
DB = "dbname=gadgeto user=gadgeto password=gadgeto host=localhost port=5432"

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

def get_user_from_token(token: str) -> Optional[dict]:
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    th = hashlib.sha256(token.encode()).hexdigest()
    cur.execute("""
        SELECT u.id, u.email, u.full_name, u.phone, u.role FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = %s AND s.expires_at > NOW()
    """, (th,))
    user = cur.fetchone()
    conn.close()
    return user

@router.post("/register")
async def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    import psycopg2
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (req.email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    from passlib.hash import bcrypt
    pwd = bcrypt.hash(req.password)
    cur.execute("""
        INSERT INTO users (email, password_hash, full_name, phone, role, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, 'CUSTOMER', 'ACTIVE', NOW(), NOW()) RETURNING id
    """, (req.email, pwd, req.full_name, req.phone))
    conn.commit()
    conn.close()
    return await login(LoginRequest(email=req.email, password=req.password))

@router.post("/login")
async def login(req: LoginRequest):
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, email, password_hash, full_name, phone, role FROM users WHERE email = %s", (req.email,))
    user = cur.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    from passlib.hash import bcrypt
    if not bcrypt.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn2 = psycopg2.connect(DB)
    cur2 = conn2.cursor()
    cur2.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, created_at, updated_at) VALUES (%s, %s, NOW() + INTERVAL '7 days', NOW(), NOW())",
        (token_hash, user["id"]))
    conn2.commit()
    conn2.close()
    return AuthResponse(access_token=token, user={"id": user["id"], "email": user["email"]})

@router.post("/logout")
async def logout(token: str = ""):
    import psycopg2
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    th = hashlib.sha256(token.encode()).hexdigest()
    cur.execute("DELETE FROM sessions WHERE token_hash = %s", (th,))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.get("/me")
async def me(token: str = ""):
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
