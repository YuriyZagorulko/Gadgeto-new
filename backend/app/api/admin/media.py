"""Media Library API - WordPress-style central media management.

Storage layout: MEDIA_DIR/products/<uuid>.<ext>
Public URL:     /media/products/<uuid>.<ext>  (served by FastAPI StaticFiles)

Deletion safety: a media file is only deleted when NO product_images row
references its URL. Removing an image from a product never deletes media.
"""
import os
import uuid

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from typing import Optional, List
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.config import settings
from app.core.db_connect import DB

router = APIRouter()

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


def db():
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


def detect_mime(body: bytes) -> Optional[str]:
    """Detect MIME from magic bytes (never trust the client extension)."""
    for magic, mime in MAGIC.items():
        if body.startswith(magic):
            return mime
    # WEBP: RIFF....WEBP
    if len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    return None


def save_upload(body: bytes, mime: str) -> dict:
    """Persist an uploaded image to storage + DB. Returns the media row."""
    from PIL import Image
    import io

    ext = EXT_BY_MIME[mime]
    filename = uuid.uuid4().hex + ext
    rel_path = f"products/{filename}"
    abs_path = os.path.join(settings.MEDIA_DIR, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(body)

    width = height = None
    try:
        with Image.open(io.BytesIO(body)) as im:
            width, height = im.size
    except Exception:
        pass  # dimensions are informational only

    base_url = (settings.MEDIA_BASE_URL or "/media").rstrip("/")
    url = f"{base_url}/{rel_path}"

    conn, cur = db()
    try:
        cur.execute(
            """INSERT INTO media_files (filename, storage_path, url, mime_type,
                                        size_bytes, width, height)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (filename, rel_path, url, mime, len(body), width, height),
        )
        mid = cur.fetchone()["id"]
        cur.execute("SELECT * FROM media_files WHERE id=%s", (mid,))
        return dict(cur.fetchone())
    finally:
        conn.close()


@router.post("/media/upload")
async def upload_media(file: UploadFile = File(...), user: dict = Depends(require_admin)):
    body = await file.read()
    if len(body) > MAX_SIZE:
        raise HTTPException(400, "Файл завеликий (макс. 10 MB)")
    mime = detect_mime(body)
    if not mime or mime not in ALLOWED_MIME:
        raise HTTPException(400, "Дозволено лише JPG, PNG, WEBP або GIF зображення")
    return save_upload(body, mime)

@router.get("/media")
async def list_media(
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    search: Optional[str] = None,
    usage: str = Query("all", pattern="^(all|used|unused|missing)$"),
    sort: str = Query("created_at", pattern="^(created_at|filename|size_bytes|mime_type|width|height|usage_count)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    user: dict = Depends(require_admin),
):
    conn, cur = db()
    try:
        conds, params = ["1=1"], []
        if search:
            conds.append("m.filename ILIKE %s")
            params.append(f"%{search}%")
        having = ""
        if usage == "used":
            having = "HAVING COUNT(pi.id) > 0"
        elif usage == "unused":
            having = "HAVING COUNT(pi.id) = 0"

        where = " AND ".join(conds)
        direction = "ASC" if order == "asc" else "DESC"
        offset = (page - 1) * per_page

        base_sql = f"""
            FROM media_files m
            LEFT JOIN product_images pi ON pi.url = m.url
            WHERE {where}
            GROUP BY m.id
            {having}
        """
        cur.execute(f"SELECT COUNT(*) AS c FROM ({'SELECT m.id' + base_sql}) t", params)
        total = cur.fetchone()["c"]

        sort_col = {"created_at": "m.created_at", "filename": "m.filename",
                    "size_bytes": "m.size_bytes", "mime_type": "m.mime_type",
                    "width": "m.width", "height": "m.height",
                    "usage_count": "COUNT(pi.id)"}[sort]
        cur.execute(
            f"""SELECT m.*, COUNT(pi.id) AS usage_count
                {base_sql}
                ORDER BY {sort_col} {direction}, m.id DESC
                LIMIT %s OFFSET %s""",
            params + [per_page, offset],
        )
        items = [dict(r) for r in cur.fetchall()]
        # Compute status: USED / UNUSED / MISSING_FILE
        for item in items:
            if item["usage_count"] > 0:
                if os.path.exists(os.path.join(settings.MEDIA_DIR, item["storage_path"])):
                    item["status"] = "used"
                else:
                    item["status"] = "missing"
            else:
                if os.path.exists(os.path.join(settings.MEDIA_DIR, item["storage_path"])):
                    item["status"] = "unused"
                else:
                    item["status"] = "missing"
        # If filtering by missing, filter in Python (approximate, small edge case)
        if usage == "missing":
            items = [it for it in items if it["status"] == "missing"]
        return {"items": items, "total": total, "page": page,
                "pages": max(1, -(-total // per_page))}
    finally:
        conn.close()


@router.get("/media/stats")
async def media_stats(user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("""SELECT COUNT(*) AS total,
                       COALESCE(SUM(size_bytes),0) AS total_size FROM media_files""")
        row = cur.fetchone()
        cur.execute("""SELECT COUNT(*) AS used FROM media_files m
                       WHERE EXISTS (SELECT 1 FROM product_images pi WHERE pi.url=m.url)""")
        used = cur.fetchone()["used"]

        orphaned_count, orphaned_size = 0, 0
        products_dir = os.path.join(settings.MEDIA_DIR, "products")
        if os.path.isdir(products_dir):
            cur.execute("SELECT storage_path FROM media_files")
            known = {r["storage_path"] for r in cur.fetchall()}
            for fn in os.listdir(products_dir):
                rel = f"products/{fn}"
                if rel not in known:
                    orphaned_count += 1
                    try:
                        orphaned_size += os.path.getsize(os.path.join(products_dir, fn))
                    except OSError:
                        pass

        return {"total": row["total"], "total_size": int(row["total_size"]),
                "used": used, "unused": row["total"] - used,
                "orphaned": orphaned_count, "orphaned_size": orphaned_size}
    finally:
        conn.close()


@router.post("/media/scan")
async def scan_storage(user: dict = Depends(require_admin)):
    """Storage audit: detect orphaned files and missing files. Nothing is deleted."""
    conn, cur = db()
    try:
        cur.execute("SELECT storage_path FROM media_files")
        known = {r["storage_path"] for r in cur.fetchall()}
        missing_on_disk, orphans = [], []
        for path in known:
            if not os.path.exists(os.path.join(settings.MEDIA_DIR, path)):
                missing_on_disk.append(path)
        products_dir = os.path.join(settings.MEDIA_DIR, "products")
        if os.path.isdir(products_dir):
            for fn in sorted(os.listdir(products_dir)):
                rel = f"products/{fn}"
                if rel not in known:
                    fp = os.path.join(products_dir, fn)
                    orphans.append({"path": rel, "size": os.path.getsize(fp)})
        return {"db_records": len(known), "orphaned": orphans,
                "orphaned_count": len(orphans),
                "orphaned_size": sum(o["size"] for o in orphans),
                "missing_on_disk": missing_on_disk}
    finally:
        conn.close()


@router.get("/media/{media_id}")
async def get_media(media_id: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT * FROM media_files WHERE id=%s", (media_id,))
        m = cur.fetchone()
        if not m:
            raise HTTPException(404, "Медіа не знайдено")
        cur.execute(
            """SELECT pi.product_id, pi.is_primary, p.name AS product_name
               FROM product_images pi JOIN products p ON p.id = pi.product_id
               WHERE pi.url=%s ORDER BY pi.product_id""", (m["url"],))
        return {"media": dict(m), "usage": [dict(r) for r in cur.fetchall()]}
    finally:
        conn.close()


@router.delete("/media/{media_id}")
async def delete_media(media_id: int, user: dict = Depends(require_admin)):
    conn, cur = db()
    try:
        cur.execute("SELECT * FROM media_files WHERE id=%s", (media_id,))
        m = cur.fetchone()
        if not m:
            raise HTTPException(404, "Медіа не знайдено")

        cur.execute("SELECT COUNT(*) AS c FROM product_images WHERE url=%s",
                    (m["url"],))
        used_by = cur.fetchone()["c"]
        if used_by > 0:
            raise HTTPException(
                409,
                f"Файл використовується у {used_by} товарах. Спочатку від'єднайте його.",
            )

        abs_path = os.path.join(settings.MEDIA_DIR, m["storage_path"])
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except OSError as e:
                raise HTTPException(500, f"Не вдалося видалити файл: {e}")
        cur.execute("DELETE FROM media_files WHERE id=%s", (media_id,))
        return {"ok": True}
    finally:
        conn.close()


@router.post("/media/cleanup-unused")
async def cleanup_unused_media(user: dict = Depends(require_admin)):
    """Delete all media_files that have ZERO product_image references.

    Workflow:
    1. Identify unreferenced media (no product_images row with matching URL).
    2. Delete physical file if it exists.
    3. Delete the media_files DB row.

    Returns stats about what was deleted.
    """
    conn, cur = db()
    try:
        cur.execute(
            """SELECT mf.id, mf.storage_path, mf.url, mf.filename
               FROM media_files mf
               WHERE NOT EXISTS (
                   SELECT 1 FROM product_images pi WHERE pi.url = mf.url
               )"""
        )
        rows = cur.fetchall()
        deleted_count = 0
        deleted_size = 0
        errors = []

        for row in rows:
            media_id = row["id"]
            storage_path = row["storage_path"]
            abs_path = os.path.join(settings.MEDIA_DIR, storage_path)
            if os.path.exists(abs_path):
                try:
                    deleted_size += os.path.getsize(abs_path)
                    os.remove(abs_path)
                except OSError as e:
                    errors.append(f"{storage_path}: {e}")
                    continue
            cur.execute("DELETE FROM media_files WHERE id=%s", (media_id,))
            deleted_count += 1

        return {
            "ok": True,
            "deleted": deleted_count,
            "deleted_size": deleted_size,
            "errors": errors,
        }
    finally:
        conn.close()


class MediaBulkDelete(BaseModel):
    ids: List[int]


@router.post("/media/bulk-delete")
async def bulk_delete_media(body: MediaBulkDelete, user: dict = Depends(require_admin)):
    """Delete multiple media files. Refuses to delete any that are still referenced."""
    if not body.ids:
        raise HTTPException(status_code=400, detail="Список ID порожній")
    conn, cur = db()
    try:
        deleted = 0
        skipped = 0
        errors = []
        for mid in body.ids:
            cur.execute("SELECT * FROM media_files WHERE id=%s", (mid,))
            m = cur.fetchone()
            if not m:
                skipped += 1
                continue
            cur.execute("SELECT COUNT(*) AS c FROM product_images WHERE url=%s", (m["url"],))
            used_by = cur.fetchone()["c"]
            if used_by > 0:
                skipped += 1
                errors.append(f"ID {mid}: використовується у {used_by} товарах")
                continue
            abs_path = os.path.join(settings.MEDIA_DIR, m["storage_path"])
            if os.path.exists(abs_path):
                try:
                    os.remove(abs_path)
                except OSError as e:
                    errors.append(f"{m['storage_path']}: {e}")
                    continue
            cur.execute("DELETE FROM media_files WHERE id=%s", (mid,))
            deleted += 1
        return {"ok": True, "deleted": deleted, "skipped": skipped, "errors": errors}
    finally:
        conn.close()
