"""Admin API for Rozetka pricing/commission management."""

import json
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from app.api.admin.deps import require_admin
from app.core.db_connect import admin_cursor

router = APIRouter()

_ALLOWED_EXTENSIONS = {".xlsx"}
_MAX_FILE_SIZE = 50 * 1024 * 1024


def _get_active_import(cur):
    cur.execute("""
        SELECT id, original_filename, status, total_rows, categories_found,
               rules_imported, invalid_rows, duplicate_rows, errors_json,
               created_at, updated_at
        FROM rozetka_pricing_imports
        WHERE is_active = true
        ORDER BY id DESC LIMIT 1
    """)
    return cur.fetchone()


@router.get("/pricing/rozetka/status")
def pricing_status(user=Depends(require_admin)):
    conn, cur = admin_cursor()
    try:
        active = _get_active_import(cur)
        if not active:
            return {"active": False, "imports": []}
        # Get the previous import for history display
        cur.execute("""
            SELECT id, original_filename, created_at, status, total_rows,
                   categories_found, rules_imported, invalid_rows, duplicate_rows
            FROM rozetka_pricing_imports
            WHERE is_active = false AND status = 'SUCCESS'
            ORDER BY id DESC LIMIT 1
        """)
        prev = cur.fetchone()
        return {
            "active": True,
            "import_id": active["id"],
            "filename": active["original_filename"],
            "status": active["status"],
            "total_rows": active["total_rows"],
            "categories_found": active["categories_found"],
            "rules_imported": active["rules_imported"],
            "invalid_rows": active["invalid_rows"],
            "duplicate_rows": active["duplicate_rows"],
            "errors": json.loads(active["errors_json"]) if active["errors_json"] else [],
            "created_at": active["created_at"].isoformat() if active["created_at"] else None,
            "updated_at": active["updated_at"].isoformat() if active["updated_at"] else None,
            "previous": {
                "filename": prev["original_filename"],
                "created_at": prev["created_at"].isoformat() if prev["created_at"] else None,
                "rules_imported": prev["rules_imported"],
            } if prev else None,
        }
    finally:
        conn.close()


@router.post("/pricing/rozetka/import")
def import_pricing_file(file: UploadFile = File(...),
                        user=Depends(require_admin)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(422, detail="Дозволено лише файли .xlsx")
    try:
        contents = file.file.read(_MAX_FILE_SIZE + 1)
    except Exception:
        raise HTTPException(400, detail="Помилка читання файлу")
    if len(contents) > _MAX_FILE_SIZE:
        raise HTTPException(422, detail="Файл занадто великий (макс. 50 MB)")

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        tmp.write(contents)
        tmp.close()

        from app.services.rozetka_pricing_parser import parse_rozetka_pricing
        parsed = parse_rozetka_pricing(tmp.name)

        if parsed.errors:
            return {"ok": False, "errors": parsed.errors, "detail": "Не вдалося відкрити файл"}

        conn, cur = admin_cursor()
        try:
            cur.execute("""
                INSERT INTO rozetka_pricing_imports
                    (original_filename, status, total_rows, categories_found,
                     rules_imported, invalid_rows, duplicate_rows, errors_json,
                     is_active, imported_by_user_id, created_at, updated_at)
                VALUES (%s, 'PROCESSING', %s, %s, %s, %s, %s, %s, false, %s, NOW(), NOW())
                RETURNING id
            """, (
                file.filename or "unknown.xlsx",
                parsed.total_rows, len(parsed.unique_categories),
                len(parsed.rows), len(parsed.invalid), parsed.duplicates,
                json.dumps([r.errors for r in parsed.invalid], ensure_ascii=False) if parsed.invalid else None,
                user.get("id"),
            ))
            import_id = cur.fetchone()["id"]

            for rule in parsed.rows:
                cur.execute("""
                    INSERT INTO rozetka_category_pricing_rules
                        (import_id, external_category_id, category_name,
                         brand, price_min, price_max, commission_percent, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    import_id, rule.external_category_id, rule.category_name,
                    rule.brand, rule.price_min, rule.price_max, rule.commission_percent,
                ))

            if len(parsed.rows) == 0:
                cur.execute("UPDATE rozetka_pricing_imports SET status='FAILED', updated_at=NOW() WHERE id=%s", (import_id,))
                conn.commit()
                return {"ok": False, "import_id": import_id, "detail": "Файл не містить жодного коректного правила", "total_rows": parsed.total_rows, "invalid_rows": len(parsed.invalid), "duplicates": parsed.duplicates}

            # Save the previously active import ID (for history + cleanup)
            cur.execute("SELECT id FROM rozetka_pricing_imports WHERE is_active=true LIMIT 1")
            old_active = cur.fetchone()

            # Deactivate previous active import
            cur.execute("UPDATE rozetka_pricing_imports SET is_active=false WHERE is_active=true")

            # Keep the previous import for history, delete everything older
            if old_active:
                cur.execute("""
                    DELETE FROM rozetka_category_pricing_rules
                    WHERE import_id IN (
                        SELECT id FROM rozetka_pricing_imports
                        WHERE is_active = false AND id != %s AND id != %s
                    )
                """, (import_id, old_active["id"]))
                cur.execute("""
                    DELETE FROM rozetka_pricing_imports
                    WHERE is_active = false AND id != %s AND id != %s
                """, (import_id, old_active["id"]))
            else:
                cur.execute("""
                    DELETE FROM rozetka_category_pricing_rules
                    WHERE import_id IN (
                        SELECT id FROM rozetka_pricing_imports
                        WHERE is_active = false AND id != %s
                    )
                """, (import_id,))
                cur.execute("""
                    DELETE FROM rozetka_pricing_imports
                    WHERE is_active = false AND id != %s
                """, (import_id,))

            # Activate new import
            cur.execute("UPDATE rozetka_pricing_imports SET status='SUCCESS', is_active=true, updated_at=NOW() WHERE id=%s", (import_id,))
            conn.commit()

            return {
                "ok": True, "import_id": import_id,
                "total_rows": parsed.total_rows,
                "categories_found": len(parsed.unique_categories),
                "rules_imported": len(parsed.rows),
                "invalid_rows": len(parsed.invalid),
                "duplicates": parsed.duplicates,
                "sample_errors": [r.errors for r in parsed.invalid[:5]],
            }
        finally:
            conn.close()
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@router.get("/pricing/rozetka/rules")
def list_pricing_rules(
        q: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        per_page: int = Query(25, ge=1, le=200),
        user=Depends(require_admin),
):
    conn, cur = admin_cursor()
    try:
        active = _get_active_import(cur)
        if not active:
            return {"items": [], "total": 0, "page": page, "per_page": per_page, "import_id": None}

        import_id = active["id"]
        filters = ["r.import_id = %s"]
        params: list = [import_id]

        if q:
            filters.append("(r.category_name ILIKE %s OR r.external_category_id ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%"])

        where = " AND ".join(filters)
        cur.execute(f"SELECT count(*) AS c FROM rozetka_category_pricing_rules r WHERE {where}", params)
        total = cur.fetchone()["c"]

        cur.execute(f"""
            SELECT r.id, r.external_category_id, r.category_name, r.brand,
                   r.price_min, r.price_max, r.commission_percent, r.created_at
            FROM rozetka_category_pricing_rules r
            WHERE {where}
            ORDER BY r.category_name, r.price_min NULLS LAST, r.brand NULLS LAST
            LIMIT %s OFFSET %s
        """, params + [per_page, (page - 1) * per_page])

        items = [dict(r) for r in cur.fetchall()]
        return {
            "items": items, "total": total, "page": page, "per_page": per_page,
            "import_id": import_id, "filename": active["original_filename"],
            "created_at": active["created_at"].isoformat() if active["created_at"] else None,
        }
    finally:
        conn.close()
