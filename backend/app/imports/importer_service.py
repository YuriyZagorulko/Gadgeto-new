"""Full import pipeline service."""
import json
import os
import threading
import psycopg2

from app.core.db_connect import DB
from app.imports.registry import SUPPLIERS
from app.imports.job_health import is_cancelled, refresh_heartbeat


_STAGE_LABELS = {
    "initializing": "Ініціалізація імпорту",
    "authenticating": "Авторизація",
    "downloading": "Завантаження каталогу",
    "parsing": "Розбір каталогу",
    "products": "Обробка товарів",
    "finalizing": "Завершення",
    "completed": "Імпорт завершено",
}

# Progress flush cadence (products) — lightweight, throttled DB updates.
PROGRESS_EVERY = 20


class ImportCancelled(Exception):
    """Raised internally when an administrator cancels a running import."""


def _log(conn, job_id, level, message):
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO import_logs (job_id, level, message, created_at, updated_at)"
            " VALUES (%s, %s, %s, NOW(), NOW())",
            (job_id, level, message),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        cur.close()


def _make_progress(conn, job_id):
    last_stage = {"v": None}

    def _progress(stage, total, processed, created, updated, skipped, failed,
                  message, current_item=None, error_count=None, warning_count=None):
        cur = conn.cursor()
        try:
            prog = {
                "stage": stage, "total": total or 0, "processed": processed or 0,
                "created": created or 0, "updated": updated or 0,
                "skipped": skipped or 0, "failed": failed or 0, "message": message,
            }
            cur.execute(
                "UPDATE import_jobs SET progress_json=%s, current_stage=%s,"
                " current_item=%s, heartbeat_at=NOW(), last_activity_at=NOW(),"
                " total_count=%s, processed_count=%s, created_count=%s,"
                " updated_count=%s, skipped_count=%s, failed_count=%s,"
                " error_count=%s, warning_count=%s, updated_at=NOW()"
                " WHERE id=%s",
                (json.dumps(prog, ensure_ascii=False), stage,
                 current_item or None,
                 total or 0, processed or 0, created or 0,
                 updated or 0, skipped or 0, failed or 0,
                 error_count or 0, warning_count or 0, job_id),
            )
            conn.commit()
            if stage != last_stage["v"]:
                last_stage["v"] = stage
                label = _STAGE_LABELS.get(stage, message or stage)
                _log(conn, job_id, "INFO", label)
        except Exception:
            pass
        finally:
            cur.close()
    return _progress


def _cleanup_supplier_temp_files(supplier_code: str):
    """Remove temporary working files created during a supplier import."""
    from app.core.config import settings as app_settings
    if supplier_code == "itlink":
        feeds_dir = app_settings.SUPPLIER_FEEDS_DIR or "/data/feeds"
        itlink_dir = os.path.join(feeds_dir, "itlink")
        if os.path.isdir(itlink_dir):
            for fn in os.listdir(itlink_dir):
                if fn.startswith("itlink_") and (fn.endswith(".yml") or fn.endswith(".yml.tmp")):
                    path = os.path.join(itlink_dir, fn)
                    try:
                        if os.path.isfile(path):
                            os.remove(path)
                    except OSError:
                        pass


def _start_heartbeat(job_id: int):
    """Background daemon thread that keeps heartbeat_at fresh.

    The importer reports real progress every N products, but long stages
    (feed download/parse, finalize) may not emit progress for a while. The
    heartbeat guarantees the stale detector never fires for a genuinely
    working job, while a dead process stops heartbeating immediately.
    """
    stop = threading.Event()

    def _loop():
        while not stop.wait(30):
            try:
                refresh_heartbeat(job_id)
            except Exception:
                break

    t = threading.Thread(target=_loop, daemon=True, name=f"import-heartbeat-{job_id}")
    t.start()
    return stop, t


def _cancelled(job_id: int) -> bool:
    try:
        return is_cancelled(job_id)
    except Exception:
        return False


def _flush_error_counts(conn, job_id, runner):
    """Sync error/warning counters to the job row (throttled by caller)."""
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE import_jobs SET error_count=%s, warning_count=%s WHERE id=%s",
            (len(runner.errors), len(runner.warnings), job_id),
        )
        conn.commit()
        cur.close()
    except Exception:
        pass


def run_full_import(supplier_code, job_id, supplier_id, import_type="full"):
    """Run a full import for one job and drive its lifecycle in import_jobs.

    Status flow: QUEUED -> RUNNING -> SUCCEEDED / FAILED / CANCELLED.
    Progress counters and heartbeat are persisted in a throttled fashion.
    """
    from app.imports.import_runner import ImportRunner
    from app.imports.mapping_resolver import MappingResolver
    from app.imports.attribute_processor import set_db_resolver

    conn = psycopg2.connect(DB)
    heartbeat_stop = None
    cancelled = False
    try:
        entry = SUPPLIERS.get(supplier_code)
        if not entry:
            raise ValueError(f"Unknown supplier: {supplier_code}")

        db_category_map = None
        try:
            resolver = MappingResolver(supplier_code)
            if resolver.has_rules():
                set_db_resolver(resolver)
                cat_map = resolver.build_category_map()
                if cat_map:
                    db_category_map = cat_map
        except Exception:
            set_db_resolver(None)

        progress = _make_progress(conn, job_id)

        cur = conn.cursor()
        cur.execute(
            "UPDATE import_jobs SET status='RUNNING', started_at=COALESCE(started_at, NOW()),"
            " heartbeat_at=NOW(), last_activity_at=NOW(), updated_at=NOW()"
            " WHERE id=%s", (job_id,),
        )
        conn.commit()
        cur.close()
        _log(conn, job_id, "INFO", f"Початок імпорту {supplier_code.upper()}")

        heartbeat_stop, _ = _start_heartbeat(job_id)

        progress("authenticating", 0, 0, 0, 0, 0, 0, "Авторизація...")
        progress("downloading", 0, 0, 0, 0, 0, 0, "Завантаження каталогу...")
        importer = entry["importer"](category_map=db_category_map)
        try:
            stats = importer.run(import_type)
        finally:
            _cleanup_supplier_temp_files(supplier_code)

        if _cancelled(job_id):
            raise ImportCancelled()

        progress("parsing", 0, 0, 0, 0, 0, 0, "Розбір каталогу...")

        normalized_products = []
        if hasattr(stats, "products"):
            normalized_products = stats.products

        image_storage_mode = "supplier_url"
        try:
            sup_cur = conn.cursor()
            sup_cur.execute("SELECT config_json FROM suppliers WHERE id = %s", (supplier_id,))
            sup_row = sup_cur.fetchone()
            sup_cur.close()
            if sup_row and sup_row[0]:
                sup_config = json.loads(sup_row[0])
                image_storage_mode = sup_config.get("image_storage_mode", "supplier_url")
        except Exception:
            pass

        runner = ImportRunner(supplier_id=supplier_id,
                              supplier_code=supplier_code,
                              progress_cb=progress,
                              mark_removed_products=True,
                              image_storage_mode=image_storage_mode)
        runner.total = len(normalized_products) or stats.processed or 0
        runner.initialize()

        for prod in normalized_products:
            runner.persist_product(prod)
            runner.processed += 1
            if runner.processed % PROGRESS_EVERY == 0 or runner.processed == runner.total:
                if _cancelled(job_id):
                    raise ImportCancelled()
                progress("products", runner.total, runner.processed,
                         runner.created, runner.updated, runner.skipped,
                         runner.failed,
                         f"Оброблено {runner.processed}/{runner.total}",
                         current_item=getattr(prod, "supplier_sku", None) or getattr(prod, "sku", None) or "",
                         error_count=len(runner.errors), warning_count=len(runner.warnings))

        if _cancelled(job_id):
            raise ImportCancelled()

        runner.finalize()

        for w in runner.warnings:
            _log(conn, job_id, "WARNING", w)

        if hasattr(stats, "warnings") and stats.warnings:
            for w in stats.warnings:
                _log(conn, job_id, "WARNING", w)

        if hasattr(stats, "unknown_categories") and stats.unknown_categories:
            _log(conn, job_id, "WARNING",
                 f"Категорій без маппінгу: {len(stats.unknown_categories)}")
        if hasattr(stats, "unknown_attributes") and stats.unknown_attributes:
            _log(conn, job_id, "WARNING",
                 f"Атрибутів без маппінгу: {len(stats.unknown_attributes)}")
        if hasattr(stats, "unknown_attribute_values") and stats.unknown_attribute_values:
            _log(conn, job_id, "WARNING",
                 f"Значень атрибутів без маппінгу: {len(stats.unknown_attribute_values)}")

        for e in runner.errors:
            _log(conn, job_id, "ERROR", str(e))

        result_stats = {
            "total": runner.total, "processed": runner.processed,
            "created": runner.created, "updated": runner.updated,
            "skipped": runner.skipped, "failed": runner.failed,
            "warnings": runner.warnings, "errors": runner.errors,
            "unknown_categories": len(stats.unknown_categories) if hasattr(stats, "unknown_categories") else 0,
            "unknown_attributes": len(stats.unknown_attributes) if hasattr(stats, "unknown_attributes") else 0,
            "unknown_attribute_values": len(stats.unknown_attribute_values) if hasattr(stats, "unknown_attribute_values") else 0,
        }

        progress("completed", runner.total, runner.processed,
                 runner.created, runner.updated, runner.skipped,
                 runner.failed,
                 f"Імпорт завершено. Створено: {runner.created}, Оновлено: {runner.updated}",
                 error_count=len(runner.errors), warning_count=len(runner.warnings))
        _log(conn, job_id, "SUCCESS",
             f"Імпорт завершено. Створено: {runner.created}, Оновлено: {runner.updated}")

        cur = conn.cursor()
        cur.execute(
            "UPDATE import_jobs SET status='SUCCEEDED', finished_at=NOW(),"
            " updated_at=NOW(), heartbeat_at=NOW(), last_activity_at=NOW(),"
            " stats_json=%s, total_count=%s, processed_count=%s, created_count=%s,"
            " updated_count=%s, skipped_count=%s, failed_count=%s,"
            " error_count=%s, warning_count=%s WHERE id=%s",
            (json.dumps(result_stats, ensure_ascii=False), runner.total,
             runner.processed, runner.created, runner.updated, runner.skipped,
             runner.failed, len(runner.errors), len(runner.warnings), job_id),
        )
        conn.commit()
        cur.close()

        return {"success": True, "supplier": supplier_code,
                "import_type": import_type, "stats": result_stats}

    except ImportCancelled:
        cancelled = True
        from app.imports.job_health import CANCEL_DONE_MSG
        try:
            _log(conn, job_id, "INFO", CANCEL_DONE_MSG)
            cur = conn.cursor()
            cur.execute(
                "UPDATE import_jobs SET status='CANCELLED', finished_at=NOW(),"
                " updated_at=NOW(), cancel_requested=TRUE, error_details_json=%s"
                " WHERE id=%s AND status IN ('QUEUED','RUNNING')",
                (json.dumps({"reason": CANCEL_DONE_MSG}, ensure_ascii=False), job_id),
            )
            conn.commit()
            cur.close()
        except Exception:
            pass
        return {"success": False, "cancelled": True}

    except Exception as exc:
        try:
            _log(conn, job_id, "ERROR", f"Помилка імпорту: {exc}")
            cur = conn.cursor()
            cur.execute(
                "UPDATE import_jobs SET status='FAILED', finished_at=NOW(),"
                " updated_at=NOW(), error_details_json=%s WHERE id=%s",
                (json.dumps({"error": str(exc)}, ensure_ascii=False), job_id),
            )
            conn.commit()
            cur.close()
        except Exception:
            pass
        return {"success": False, "error": str(exc)}

    finally:
        if heartbeat_stop is not None:
            heartbeat_stop.set()
            del heartbeat_stop
        try:
            set_db_resolver(None)
        except Exception:
            pass
        try:
            _cleanup_supplier_temp_files(supplier_code)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
