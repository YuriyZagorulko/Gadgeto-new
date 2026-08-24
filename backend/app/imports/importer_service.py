"""Full import pipeline service."""
import json
import os
import psycopg2
from app.core.db_connect import DB
from app.imports.registry import SUPPLIERS


_STAGE_LABELS = {
    "initializing": "Ініціалізація імпорту",
    "authenticating": "Авторизація",
    "downloading": "Завантаження каталогу",
    "parsing": "Розбір каталогу",
    "products": "Обробка товарів",
    "finalizing": "Завершення",
    "completed": "Імпорт завершено",
}


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
    def _progress(stage, total, processed, created, updated, skipped, failed, message):
        cur = conn.cursor()
        try:
            prog = {
                "stage": stage, "total": total, "processed": processed,
                "created": created, "updated": updated,
                "skipped": skipped, "failed": failed, "message": message,
            }
            cur.execute(
                "UPDATE import_jobs SET progress_json=%s, current_stage=%s,"
                " updated_at=NOW() WHERE id=%s",
                (json.dumps(prog, ensure_ascii=False), stage, job_id),
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
    """Remove temporary working files created during a supplier import.

    Only cleans files that are known temporary/download artefacts, never
    permanent application data.
    """
    from app.core.config import settings as app_settings
    if supplier_code == "itlink":
        # IT-Link downloader saves the XML price feed to
        # SUPPLIER_FEEDS_DIR/itlink/itlink_<run_id>.yml
        # Clean up any itlink_*.yml files (all are temporary per-run files)
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
    # DC-Link processes everything in-memory — no temp files to clean.


def run_full_import(supplier_code, job_id, supplier_id, import_type="full"):
    from app.imports.import_runner import ImportRunner
    from app.imports.mapping_resolver import MappingResolver
    from app.imports.attribute_processor import set_db_resolver
    conn = psycopg2.connect(DB)
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
            "UPDATE import_jobs SET status='RUNNING', started_at=NOW(),"
            " updated_at=NOW() WHERE id=%s", (job_id,),
        )
        conn.commit()
        cur.close()
        _log(conn, job_id, "INFO", f"Початок імпорту {supplier_code.upper()}")

        progress("authenticating", 0, 0, 0, 0, 0, 0, "Авторизація...")
        progress("downloading", 0, 0, 0, 0, 0, 0, "Завантаження каталогу...")
        importer = entry["importer"](category_map=db_category_map)
        try:
            stats = importer.run(import_type)
        finally:
            # Guarantee temp-file cleanup even if parsing/persistence fails
            _cleanup_supplier_temp_files(supplier_code)

        progress("parsing", 0, 0, 0, 0, 0, 0, "Розбір каталогу...")

        normalized_products = []
        if hasattr(stats, 'products'):
            normalized_products = stats.products

        runner = ImportRunner(supplier_id=supplier_id,
                              supplier_code=supplier_code,
                              progress_cb=progress,
                              mark_removed_products=True)
        runner.total = len(normalized_products) or stats.processed or 0
        runner.initialize()

        for prod in normalized_products:
            runner.persist_product(prod)
            runner.processed += 1
            if runner.processed % 20 == 0 or runner.processed == runner.total:
                progress("products", runner.total, runner.processed,
                         runner.created, runner.updated, runner.skipped,
                         runner.failed,
                         f"Оброблено {runner.processed}/{runner.total}")

        runner.finalize()

        for w in runner.warnings:
            _log(conn, job_id, "WARNING", w)

        if hasattr(stats, 'unknown_categories') and stats.unknown_categories:
            _log(conn, job_id, "WARNING",
                 f"Категорій без маппінгу: {len(stats.unknown_categories)}")
        if hasattr(stats, 'unknown_attributes') and stats.unknown_attributes:
            _log(conn, job_id, "WARNING",
                 f"Атрибутів без маппінгу: {len(stats.unknown_attributes)}")
        if hasattr(stats, 'unknown_attribute_values') and stats.unknown_attribute_values:
            _log(conn, job_id, "WARNING",
                 f"Значень атрибутів без маппінгу: {len(stats.unknown_attribute_values)}")

        for e in runner.errors:
            _log(conn, job_id, "ERROR", str(e))

        result_stats = {
            "total": runner.total, "processed": runner.processed,
            "created": runner.created, "updated": runner.updated,
            "skipped": runner.skipped, "failed": runner.failed,
            "warnings": runner.warnings, "errors": runner.errors,
            "unknown_categories": len(stats.unknown_categories) if hasattr(stats, 'unknown_categories') else 0,
            "unknown_attributes": len(stats.unknown_attributes) if hasattr(stats, 'unknown_attributes') else 0,
            "unknown_attribute_values": len(stats.unknown_attribute_values) if hasattr(stats, 'unknown_attribute_values') else 0,
        }

        progress("completed", runner.total, runner.processed,
                 runner.created, runner.updated, runner.skipped,
                 runner.failed,
                 f"Імпорт завершено. Створено: {runner.created}, Оновлено: {runner.updated}")
        _log(conn, job_id, "SUCCESS",
             f"Імпорт завершено. Створено: {runner.created}, Оновлено: {runner.updated}")

        cur = conn.cursor()
        cur.execute(
            "UPDATE import_jobs SET status='SUCCEEDED', finished_at=NOW(),"
            " updated_at=NOW(), stats_json=%s WHERE id=%s",
            (json.dumps(result_stats, ensure_ascii=False), job_id),
        )
        conn.commit()
        cur.close()

        return {"success": True, "supplier": supplier_code,
                "import_type": import_type, "stats": result_stats}

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
