"""Admin settings API — exposes only DB-stored business settings.

Secrets (is_secret=true) are never returned to the client; they can only be
overwritten. Infrastructure secrets (env vars) are not exposed at all.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

router = APIRouter()

_KEY_RE = r"^[a-z0-9_.-]{1,255}$"


class SettingUpdate(BaseModel):
    value: Optional[str] = None


@router.get("/settings")
def list_settings(user: dict = Depends(require_admin)):
    """All settings; secret values are masked."""
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT key, value, is_secret FROM settings ORDER BY key")
        items = []
        for r in cur.fetchall():
            items.append({
                "key": r["key"],
                "value": None if r["is_secret"] else r["value"],
                "is_secret": r["is_secret"],
                "has_value": r["value"] is not None,
            })
        return {"items": items}
    finally:
        conn.close()


@router.put("/settings/{key}")
def update_setting(key: str, body: SettingUpdate,
                         user: dict = Depends(require_admin)):
    import re
    if not re.match(_KEY_RE, key):
        raise HTTPException(status_code=422, detail="Невірний ключ налаштування")
    conn, cur = admin_cursor()
    try:
        cur.execute("SELECT key, is_secret FROM settings WHERE key=%s", (key,))
        row = cur.fetchone()
        if not row:
            # only keys already known to the backend can be edited
            raise HTTPException(status_code=404, detail="Налаштування не знайдено")
        cur.execute("UPDATE settings SET value=%s WHERE key=%s", (body.value, key))
        return {"key": key, "value": None if row["is_secret"] else body.value}
    finally:
        conn.close()
