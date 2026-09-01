"""Background Rozetka product export runner (Phase 6.3).

Orchestrates the missing final stage of the pipeline in a worker thread:

    load_product -> validate (shared settings) -> transform (existing
    mapping resolver) -> apply_export_settings (shared pricing/stock) ->
    build_rozetka_payload -> RozetkaAdapter push

Progress goes into the EXISTING `sync_runs` table (run_type = EXPORT), like
the taxonomy runner; per-product state into channel_listings via the
export_listings helpers.  Only officially documented Rozetka endpoints are
used (via rozetka/api.py).

Idempotency (the official API has NO upsert):
  1. stored external_id AND unchanged content/commercial hashes -> skip;
  2. external_id present -> GET /goods/details resolves official ids;
  3. no external_id but SKU set -> documented /goods/all?article= adoption;
  4. otherwise POST /items-create/create makes ONE new item.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import traceback
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

from app.channels.base import RozetkaAdapter
from app.channels.export_listings import (
    finish_listing_error,
    finish_listing_ok,
    store_validation_issues,
    upsert_listing_pending,
)
from app.channels.export_settings import (
    apply_export_settings as apply_settings,
    load_export_settings,
)
from app.channels.mapping_resolver import ChannelMappingResolver
from app.core.db_connect import DB

logger = logging.getLogger("channels.export_run")

RUN_TYPE = "EXPORT"

STALE_RUN_MINUTES = int(os.getenv("EXPORT_STALE_MINUTES", "15"))
WRITE_EVERY = 0.7
MAX_LOGS = 300
MAX_RESULTS = 1000


def rozetka_stock_quantity(transformed: dict) -> int:
    """Rozetka stock_quantity from a transformed product.

    Business rule: in_stock → 10, out_of_stock → 0.  DC-Link API does not
    provide exact stock counts, so a fixed value is used for in-stock
    products (see ROZETKA_IN_STOCK_QUANTITY in payload.py).  Any existing
    positive stock_qty from a supplier that DOES provide exact quantities
    is preserved.
    """
    from app.channels.rozetka.payload import ROZETKA_IN_STOCK_QUANTITY

    stock_status = (transformed.get("stock_status") or "").strip()
    if stock_status == "in_stock":
        existing = int(transformed.get("stock_qty") or 0)
        return existing if existing > 0 else ROZETKA_IN_STOCK_QUANTITY
    return int(transformed.get("stock_qty") or 0)


class ExportRunBusy(Exception):
    """An export run is already active for this channel."""


class ExportSelectionEmpty(Exception):
    """The selection resolved to zero products."""


def apply_product_result(progress: dict, status: str) -> str:
    """Accumulate one product outcome into the run progress; returns the
    log word (uk).

    Counters: created / updated / unchanged / not_exported (validation
    skips) / failed.  `skipped` is kept as the legacy COMBINED counter
    (unchanged + not_exported) for the existing sync_runs.skipped_count
    column and list statistics.
    """
    if status == "created":
        progress["created"] += 1
        return "створено"
    if status == "updated":
        progress["updated"] += 1
        return "оновлено"
    if status == "unchanged":
        progress["unchanged"] += 1
        progress["skipped"] += 1
        return "без змін"
    if status == "skipped":
        progress["not_exported"] += 1
        progress["skipped"] += 1
        return "пропущено"
    progress["failed"] += 1
    progress["errors"] += 1
    return "ПОМИЛКА"


def final_run_status(cancelled: bool, failed: int, skipped: int) -> str:
    """Run-level status once the worker finished (or was interrupted).

    SUCCESS   — every selected product was exported (no validation skips,
                no failures); hash-identical 'unchanged' re-exports count
                as success;
    PARTIAL   — the worker completed normally but >=1 product was NOT
                exported (validation skip or per-product push failure);
    FAILED    — the worker itself crashed (set in run_export's except block;
                never returned here);
    CANCELLED — user requested cancellation (preserved existing semantics).
    """
    if cancelled:
        return "CANCELLED"
    return "SUCCEEDED" if failed == 0 and skipped == 0 else "PARTIAL"


def final_export_status(failed: int, not_exported: int) -> str:
    """Normal-completion variant used by the worker loop (never CANCELLED —
    cancellation is handled by the caller)."""
    return final_run_status(cancelled=False, failed=failed,
                            skipped=not_exported)


def compute_listing_hashes(resolver, product: dict, transformed: dict,
                           public_base_url) -> tuple[str, str]:
    """(content_hash, commercial_hash) for what WILL be sent.

    Content reuses validation.compute_content_hash; the commercial axis
    uses the SETTINGS-APPLIED price so a markup change alone triggers a
    price update on the next run.

    `stock_status` is part of the commercial hash so that a product
    flipping in_stock → out_of_stock (or back) changes the hash even when
    stock_qty stays 0 — this drives the Rozetka stock_quantity update
    (10 → 0 → 10) on subsequent exports.
    """
    from app.channels.validation import (
        _get_external_category_id,
        compute_content_hash,
    )

    ext_cat_id = _get_external_category_id(resolver, product)
    content_hash = compute_content_hash(product, resolver, ext_cat_id,
                                        public_base_url)
    commercial_raw = json.dumps({
        "price": transformed.get("export_price"),
        "stock_qty": transformed.get("stock_qty"),
        "stock_status": transformed.get("stock_status"),
        "currency": transformed.get("currency"),
    }, sort_keys=True, ensure_ascii=False, default=str)
    return content_hash, hashlib.sha256(commercial_raw.encode()).hexdigest()


def reconcile_stale_runs(cur) -> int:
    """Mark orphaned QUEUED/RUNNING export runs as PARTIAL (restart safety)."""
    cur.execute(
        f"""UPDATE sync_runs
            SET status='PARTIAL', finished_at=NOW(), updated_at=NOW(),
                heartbeat_at=NOW()
            WHERE run_type='{RUN_TYPE}'
              AND status IN ('QUEUED','RUNNING')
              AND (heartbeat_at IS NULL
                   OR heartbeat_at < NOW()
                      - interval '{STALE_RUN_MINUTES} minutes')
            RETURNING id""")
    return len(cur.fetchall())


def start_export_run(channel_id: int, product_ids: list[int],
                     public_base_url,
                     user_id: Optional[int] = None) -> int:
    """Create a QUEUED export run after reconciling stale ones.

    `product_ids` are resolved SERVER-SIDE by the API layer before this call.
    Raises ExportRunBusy when an export is already queued/running for the
    channel and ExportSelectionEmpty on an empty selection.
    """
    if not product_ids:
        raise ExportSelectionEmpty("Виберіть хоча б один товар для експорту")

    conn = psycopg2.connect(DB)
    conn.autocommit = True
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            reconcile_stale_runs(cur)
        except Exception:
            pass
        cur.execute(
            "SELECT count(*) AS c FROM sync_runs WHERE channel_id=%s"
            f" AND run_type='{RUN_TYPE}' AND status IN ('QUEUED','RUNNING')",
            (channel_id,),
        )
        if cur.fetchone()["c"]:
            raise ExportRunBusy(
                "Експорт на Rozetka вже виконується. Дочекайтесь завершення.")
        cur.execute(
            f"""INSERT INTO sync_runs
                (channel_id, run_type, status, total_count, processed_count,
                 progress_json, heartbeat_at, triggered_by_user_id,
                 started_at, created_at, updated_at)
                VALUES (%s, '{RUN_TYPE}', 'QUEUED', %s, 0, %s, NOW(), %s,
                        NOW(), NOW(), NOW())
                RETURNING id""",
            (channel_id, len(product_ids),
             json.dumps({"public_base_url": public_base_url,
                         "logs": [], "results": [], "errors": 0}),
             user_id),
        )
        run_id = cur.fetchone()["id"]
        cur.close()
        return run_id
    finally:
        conn.close()
def get_export_run_status(cur, channel_id: int, run_id: int) -> Optional[dict]:
    """UI-friendly status of one export run (polled by the frontend)."""
    cur.execute(
        f"SELECT * FROM sync_runs WHERE id=%s AND channel_id=%s"
        f" AND run_type='{RUN_TYPE}'",
        (run_id, channel_id),
    )
    run = cur.fetchone()
    if not run:
        return None

    progress: dict = {}
    if run.get("progress_json"):
        try:
            progress = json.loads(run["progress_json"]) or {}
        except (ValueError, TypeError):
            progress = {}
    if not isinstance(progress, dict):
        progress = {}

    results = progress.get("results") or []
    failed_results = [r for r in results if r.get("status") == "failed"]
    skipped_results = [r for r in results if r.get("status") == "skipped"]

    started_at = run.get("started_at")
    finished_at = run.get("finished_at")
    duration = None
    if started_at:
        delta = (finished_at or datetime.now()) - started_at
        duration = max(0, round(delta.total_seconds()))

    return {
        "run_id": run["id"],
        "status": run.get("status"),
        # existing SyncRunStatus values mapped onto UI states 1:1
        "ui_status": {
            "QUEUED": "queued", "RUNNING": "running",
            "SUCCEEDED": "completed", "PARTIAL": "completed_with_errors",
            "FAILED": "failed", "CANCELLED": "cancelled",
        }.get(run.get("status"), str(run.get("status")).lower()),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "progress": {
            "total": int(run.get("total_count") or 0),
            "processed": int(run.get("processed_count") or 0),
            "created": int(run.get("created_count") or 0),
            "updated": int(run.get("updated_count") or 0),
            "failed": int(run.get("failed_count") or 0),
            "skipped": int(run.get("skipped_count") or 0),
            # hash-identical re-exports (subset of skipped_count, kept
            # separate since the status fix; 0 on pre-fix runs)
            "unchanged": int(progress.get("unchanged") or 0),
            # validation-skip count (subset of skipped_count, kept
            # separate since the status fix; 0 on pre-fix runs)
            "not_exported": int(progress.get("not_exported") or 0),
        },
        "current_operation": progress.get("current_operation")
                             or run.get("current_stage"),
        "errors": [r.get("error") or "" for r in failed_results][:20],
        "skipped_sample": skipped_results[:5],
        "logs": (progress.get("logs") or [])[-50:],
    }


# ── per-product pipeline ─────────────────────────────────────────────────────

def _summarize_validation_issues(error_issues: list,
                                 external_category_id) -> dict:
    """Structured view of blocking validation issues for the history UI.

    Groups MISSING_ATTRIBUTE_MAPPING / MISSING_ATTRIBUTE_VALUE_MAPPING into
    actionable lists (attribute/value mapping navigation); everything else
    goes to `other`.  The raw `reason` string is kept alongside unchanged —
    this summary is additive, never a replacement.
    """
    from app.channels.validation import (
        ISSUE_MISSING_ATTRIBUTE_MAPPING,
        ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING,
    )
    missing_attrs: list[dict] = []
    missing_values: list[dict] = []
    other: list[dict] = []
    for issue in error_issues:
        code = issue.get("code")
        details = issue.get("details") or {}
        if code == ISSUE_MISSING_ATTRIBUTE_MAPPING:
            missing_attrs.append({
                "attribute_id": details.get("attribute_id"),
                "attribute_name": details.get("attribute_name"),
            })
        elif code == ISSUE_MISSING_ATTRIBUTE_VALUE_MAPPING:
            missing_values.append({
                "attribute_id": details.get("attribute_id"),
                "attribute_name": details.get("attribute_name"),
                "attribute_value_id": details.get("attribute_value_id"),
                "value_name": details.get("value_name"),
            })
        else:
            other.append({"code": code, "message": issue.get("message", "")})
    return {
        "total": len(error_issues),
        "missing_attribute_mappings": missing_attrs,
        "missing_value_mappings": missing_values,
        "other": other,
        "external_category_id": (str(external_category_id)
                                 if external_category_id else None),
    }


def _load_attr_specs(cur, channel_id: int, ext_cat_id,
                     external_attr_ids: list) -> dict:
    """{external_attribute_id: {name, type}} from the local taxonomy —
    required for the documented params.type of every characteristic."""
    if not external_attr_ids:
        return {}
    specs: dict = {}
    cur.execute(
        """SELECT external_id, name, param_type
           FROM channel_external_attributes
           WHERE channel_id=%s AND category_external_id=%s
             AND external_id = ANY(%s)""",
        (channel_id, str(ext_cat_id), [str(x) for x in external_attr_ids]),
    )
    for r in cur.fetchall():
        specs[str(r["external_id"])] = {"name": r["name"],
                                        "type": r["param_type"]}
    return specs


def build_payload_create(transformed: dict, attr_specs: dict) -> dict:
    """Wrapper around rozetka.payload.build_create_payload."""
    from app.channels.rozetka.payload import build_create_payload
    payload, _warnings = build_create_payload(transformed, attr_specs)
    return payload


def build_payload_update(refs: dict, transformed: dict, attr_specs: dict,
                         include_category: bool = False) -> dict:
    """One item for PUT /items-create/mass-update-basic-data."""
    from app.channels.rozetka.payload import build_basic_data_item
    item, _warnings = build_basic_data_item(
        {"item_id": refs.get("item_id"), "rz_item_id": refs.get("rz_item_id")},
        transformed, attr_specs, include_category=include_category)
    return item


def _validate_with_ctx(ctx: dict, product_id: int) -> dict:
    """validate_product on the caller's cursor with the shared settings."""
    from app.channels.validation import _validate
    return _validate(ctx["cur"], product_id, ctx["code"],
                     ctx["public_base_url"], export_settings=ctx["settings"])


def _process_product(ctx: dict, product_id: int) -> dict:
    """Full server-side pipeline for ONE product.  Never raises.

    Returns {product_id, sku, status, operation?, external_id?, error?}.
    Blocking validation failures -> 'skipped' with reasons; idempotent
    re-exports (hashes unchanged + external_id stored) -> 'unchanged'.
    """
    listing = upsert_listing_pending(ctx["cur"], ctx["channel_id"], product_id)

    validation = _validate_with_ctx(ctx, product_id)
    issues = validation.get("issues", [])
    error_issues = [i for i in issues if i.get("severity") == "error"]
    if not validation.get("ready"):
        store_validation_issues(ctx["cur"], listing["id"], issues)
        reason = "; ".join(i.get("message", "") for i in error_issues)[:500]
        # SKU/name/category come from the product data validation already
        # loaded — no second DB query for the same product.
        v_sku = validation.get("sku") or ""
        v_name = validation.get("name") or ""
        v_cat = validation.get("external_category_id")

        # If the product failed validation because it is HIDDEN/not published
        # AND it was previously exported to Rozetka, deactivate the remote
        # offer by zeroing its stock via the adapter's unpublish() method.
        if listing.get("external_id"):
            has_hidden_issue = any(
                i.get("code") == "PRODUCT_NOT_PUBLISHED" for i in error_issues
            )
            if has_hidden_issue:
                try:
                    ctx["adapter"].unpublish({
                        "sku": listing.get("sku") or "",
                        "external_ref": {
                            "rz_item_id": int(listing["external_id"])
                        } if listing["external_id"].isdigit() else {},
                        "external_id": listing.get("external_id"),
                        "price": 0,
                        "stock_quantity": 0,
                    })
                    finish_listing_ok(ctx["cur"], listing,
                                      listing.get("external_id"),
                                      "", "", None)
                except Exception as exc:
                    etype, _retryable = ctx["classify"](exc)
                    logger.warning(
                        "Unpublish failed for hidden product %s: %s %s",
                        product_id, etype, exc)
                    finish_listing_error(
                        ctx["cur"], listing["id"], etype, str(exc)[:2000])

        return {"product_id": product_id, "sku": v_sku, "name": v_name,
                "status": "skipped", "reason": reason,
                "issues": _summarize_validation_issues(error_issues, v_cat)}

    # Validation passed (ready=True). Clear any stale validation issues from
    # a previous failed export attempt so the UI/history does not show old
    # MISSING_REQUIRED_ATTR_MAPPING / other blocking errors that are no longer
    # relevant after Phase 37/39.
    store_validation_issues(ctx["cur"], listing["id"], [])

    product = ctx["load_product"](ctx["cur"], product_id)
    if product is None:
        finish_listing_error(ctx["cur"], listing["id"], "validation",
                             f"Товар {product_id} не знайдено")
        return {"product_id": product_id, "sku": "", "status": "skipped",
                "reason": "Товар не знайдено"}
    sku = product.get("sku") or ""

    from app.channels.validation import (
        _build_transform_payload,
        _get_external_category_id,
    )
    ext_cat_id = _get_external_category_id(ctx["resolver"], product)
    transformed = _build_transform_payload(product, ctx["resolver"],
                                           ext_cat_id, ctx["public_base_url"])
    apply_settings(transformed, ctx["settings"])

    # Apply Rozetka commission pricing — adjusts the export price upward
    # so that after Rozetka deducts its commission, the seller receives
    # the intended net price.  The commission is category-dependent and
    # supports parent-category inheritance (child categories without
    # explicit rules inherit from ancestors).
    pricing_resolver = ctx.get("pricing_resolver")
    if pricing_resolver and pricing_resolver.has_rules and ext_cat_id:
        brand = None
        if product.get("brand") and isinstance(product["brand"], dict):
            brand = product["brand"].get("name")
        export_price_uah = transformed.get("export_price") or 0
        # Convert UAH → kopecks for the resolver
        base_kopecks = int(round(export_price_uah * 100))
        commission_kopecks = pricing_resolver.calculate_export_price(
            str(ext_cat_id), base_kopecks, brand)
        if commission_kopecks is not None:
            # Convert back to UAH (major units) for the payload builder
            transformed["export_price"] = commission_kopecks / 100.0

    content_hash, commercial_hash = compute_listing_hashes(
        ctx["resolver"], product, transformed, ctx["public_base_url"])

    if (listing["content_hash"] == content_hash
            and listing["commercial_hash"] == commercial_hash
            and bool(listing["content_hash"])
            and bool(listing.get("external_id"))):
        finish_listing_ok(ctx["cur"], listing, listing.get("external_id"),
                          content_hash, commercial_hash, None)
        store_validation_issues(ctx["cur"], listing["id"], [])
        return {"product_id": product_id, "sku": sku, "status": "unchanged",
                "operation": "none"}

    return _resolve_and_push(ctx, listing, product_id, sku, ext_cat_id,
                             transformed, content_hash, commercial_hash)


def _resolve_and_push(ctx: dict, listing: dict, product_id: int, sku: str,
                      ext_cat_id, transformed: dict, content_hash: str,
                      commercial_hash: str) -> dict:
    """Resolve server-side ids, choose create/update, execute pushes."""
    adapter: RozetkaAdapter = ctx["adapter"]

    refs: dict = {}
    if listing.get("external_id"):
        try:
            refs = adapter.resolve_external_ref(
                {"external_id": listing.get("external_id")}) or {}
        except Exception as exc:
            logger.info("details lookup failed for product %s: %s",
                        product_id, exc)
            refs = {}

    adopted = False
    if not refs and sku:
        # Documented /goods/all?article= search adopts legacy items once;
        # found official ids are then kept server-side.
        found = adapter._client.find_item_by_article(sku)
        if found:
            refs = {"item_id": found.get("item_id"),
                    "rz_item_id": found.get("rz_item_id")}
            adopted = True

    operation = "update" if refs else "create"

    attr_ids = [str(a.get("external_attribute_id"))
                for a in transformed.get("attributes") or []
                if a.get("external_attribute_id")]
    attr_specs = _load_attr_specs(ctx["cur"], ctx["channel_id"],
                                  str(ext_cat_id), attr_ids)

    result: dict = {"product_id": product_id, "sku": sku}
    price = transformed.get("export_price")
    stock_qty = rozetka_stock_quantity(transformed)
    return _push_product_ops(ctx, adapter, operation, transformed,
                             attr_specs, refs, adopted, listing,
                             content_hash, commercial_hash, price,
                             stock_qty, sku, result)


def _push_product_ops(ctx: dict, adapter: RozetkaAdapter, operation: str,
                      transformed: dict, attr_specs: dict, refs: dict,
                      adopted: bool, listing: dict, content_hash: str,
                      commercial_hash: str, price, stock_qty: int,
                      sku: str, result: dict) -> dict:
    """Documented create / content / commercial operations; persists
    listing state.  Never raises — failure goes into `result`."""
    cur = ctx["cur"]
    created_now = False
    remote_status = None
    external_id = ""
    try:
        if operation == "create":
            payload = build_payload_create(transformed, attr_specs)
            pushed = adapter.push_product({
                "operation": "create", "sku": sku, "payload": payload,
            })
            item_id = int(pushed["external_id"])
            rz_item_id = None
            try:
                details = adapter._client.get_item_details(item_id=item_id)
            except Exception as exc:          # non-fatal best effort
                logger.info("details lookup after create failed: %s", exc)
                details = None
            if details and details.get("rz_item_id"):
                rz_item_id = int(details["rz_item_id"])
            refs = {"item_id": item_id, "rz_item_id": rz_item_id}
            external_id = str(rz_item_id) if rz_item_id else str(item_id)
            created_now = True
        else:
            include_category = refs.get("rz_item_id") is None
            payload = build_payload_update(refs, transformed, attr_specs,
                                           include_category)
            pushed = adapter.push_product({
                "operation": "update", "sku": sku, "payload": payload,
                "external_ref": {
                    "item_id": refs.get("item_id"),
                    "rz_item_id": refs.get("rz_item_id"),
                },
            })
            external_id = pushed["external_id"]
            created_now = adopted       # content refresh of a legacy item

        # Commercial state: a fresh CREATE already carries price &
        # stock_quantity in its documented body.  Updates (incl. adopted
        # items) sync commercial state explicitly because
        # mass-update-basic-data has no price fields.
        commercial_warning = None
        if not created_now:
            if refs.get("rz_item_id") is None:
                commercial_warning = ("Ціну/залишок не оновлено: товар ще не "
                                      "отримав rz_item_id від Rozetka")
                logger.info("%s sku=%s product_id=%s", commercial_warning,
                            sku, result["product_id"])
            else:
                adapter.update_price_stock({
                    "sku": sku,
                    "external_ref": {"rz_item_id": refs.get("rz_item_id")},
                    "price": float(price or 0),
                    "stock_quantity": stock_qty,
                })

        final_external = (str(refs.get("rz_item_id"))
                          if refs.get("rz_item_id") is not None
                          else str(refs.get("item_id") or external_id))
        finish_listing_ok(cur, listing, final_external, content_hash,
                          commercial_hash, remote_status)
        result.update({
            "status": "created" if created_now else "updated",
            "operation": operation,
            "external_id": final_external,
        })
        if commercial_warning:
            result["warning"] = commercial_warning
        return result
    except Exception as exc:
        etype, _retryable = ctx["classify"](exc)
        message = str(exc)[:2000]
        logger.warning("Export failed product=%s sku=%s op=%s type=%s: %s",
                       result["product_id"], sku, operation, etype, message)
        finish_listing_error(cur, listing["id"], etype, message)
        result.update({"status": "failed", "operation": operation,
                       "error_type": etype, "error": message})
        return result


# ── background entry point ───────────────────────────────────────────────────

def run_export(channel_id: int, channel_code: str, run_id: int,
               product_ids: list, public_base_url) -> dict:
    """Execute the export in the CURRENT thread (worker, never the loop).

    Persists live progress into sync_runs.  Per-product failures never stop
    the batch; fatal init errors (auth, settings) fail the whole run.
    """
    conn = psycopg2.connect(DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    progress: dict = {
        "total": len(product_ids), "processed": 0,
        "created": 0, "updated": 0, "failed": 0, "skipped": 0,
        "unchanged": 0, "not_exported": 0,
        "errors": 0, "current_operation": "Initializing...",
        "results": [], "logs": [],
    }

    def _log(level: str, message: str) -> None:
        progress["logs"].append({
            "t": round(time.time(), 2),
            "ts": datetime.now().strftime("%H:%M:%S"),
            "level": level, "message": message,
        })
        if len(progress["logs"]) > MAX_LOGS:
            del progress["logs"][: len(progress["logs"]) - MAX_LOGS]

    last_write = [0.0]

    def _flush(force: bool = False) -> None:
        now = time.time()
        if not force and (now - last_write[0]) < WRITE_EVERY:
            return
        last_write[0] = now
        try:
            cur.execute(
                """UPDATE sync_runs
                   SET progress_json=%s, current_stage=%s,
                       heartbeat_at=NOW(), total_count=%s,
                       processed_count=%s, created_count=%s,
                       updated_count=%s, failed_count=%s,
                       skipped_count=%s, updated_at=NOW()
                   WHERE id=%s""",
                (json.dumps(progress, ensure_ascii=False),
                 progress["current_operation"],
                 progress["total"], progress["processed"],
                 progress["created"], progress["updated"],
                 progress["failed"],
                 progress["skipped"], run_id),
            )
        except Exception:
            pass

    def _cancel_requested() -> bool:
        try:
            cur.execute(
                "SELECT cancel_requested FROM sync_runs WHERE id=%s",
                (run_id,))
            row = cur.fetchone()
            return bool(row and row.get("cancel_requested"))
        except Exception:
            return False

    cur.execute(
        f"""UPDATE sync_runs SET status='RUNNING', heartbeat_at=NOW(),
               updated_at=NOW() WHERE id=%s""",
        (run_id,),
    )
    _flush(force=True)
    _log("INFO", f"Експорт запущено: {len(product_ids)} товарів")

    final_status = "FAILED"
    try:
        # Fatal preparation phase — any failure here fails the whole run.
        settings = load_export_settings(cur, channel_id)
        resolver = ChannelMappingResolver(channel_id=channel_id,
                                          channel_code=channel_code)
        adapter = RozetkaAdapter()
        adapter._client._ensure_token()
        from app.channels.validation import (
            _load_product_data as load_product_data,
        )
        # Rozetka commission pricing resolver — loaded once, shared across
        # all products in this run.  Category inheritance is resolved
        # server-side, so child categories without explicit rules receive
        # their parent's commission rate.
        from app.services.rozetka_pricing import RozetkaPricingResolver
        pricing_resolver = RozetkaPricingResolver(cur, channel_id)

        ctx = {
            "channel_id": channel_id, "code": channel_code,
            "cur": cur, "resolver": resolver, "adapter": adapter,
            "settings": settings, "public_base_url": public_base_url,
            "load_product": load_product_data,
            "classify": adapter.classify_error,
            "pricing_resolver": pricing_resolver,
        }

        for idx, product_id in enumerate(product_ids, start=1):
            if _cancel_requested():
                _log("WARNING", "Отримано запит на скасування — зупиняємо")
                final_status = "CANCELLED"
                break
            result_row = _process_product(ctx, product_id)
            progress["processed"] += 1
            status = result_row.get("status")
            op_word = apply_product_result(progress, status)
            progress["current_operation"] = (
                f"{idx}/{progress['total']}: {op_word} "
                f"{result_row.get('sku') or '#' + str(product_id)}")
            if idx <= MAX_RESULTS:
                result_row["n"] = idx
                progress["results"].append(result_row)
            label = "ERROR" if status == "failed" else "INFO"
            detail = (f" — {result_row['error'][:200]}"
                      if status == "failed" and result_row.get("error") else "")
            _log(label, f"[{idx}/{progress['total']}] "
                        f"{result_row.get('sku') or product_id}: "
                        f"{op_word}{detail}")
            _flush()

        if final_status != "CANCELLED":
            final_status = final_export_status(
                failed=progress["failed"],
                not_exported=progress["not_exported"])
            progress["current_operation"] = (
                "Completed" if final_status == "SUCCEEDED"
                else "Completed with errors")
        _log("INFO" if final_status in ("SUCCEEDED", "CANCELLED")
             else "WARNING",
             f"Завершено: створено={progress['created']} "
             f"оновлено={progress['updated']} "
             f"без змін={progress['unchanged']} "
             f"не експортовано={progress['not_exported']} "
             f"помилок={progress['failed']}")

        cur.execute(
            """UPDATE sync_runs
               SET status=%s, finished_at=NOW(), heartbeat_at=NOW(),
                   updated_at=NOW(), created_count=%s, updated_count=%s,
                   failed_count=%s, skipped_count=%s, total_count=%s,
                   processed_count=%s, progress_json=%s, current_stage=%s
               WHERE id=%s""",
            (final_status,
             progress["created"], progress["updated"], progress["failed"],
             progress["skipped"],
             progress["total"], progress["processed"],
             json.dumps(progress, ensure_ascii=False),
             progress["current_operation"], run_id),
        )
        return {"success": True, "run_id": run_id, "status": final_status}
    except Exception as exc:
        tb_str = traceback.format_exception(type(exc), exc, exc.__traceback__)
        exc_type = type(exc).__name__
        exc_msg = str(exc)
        # Get the last product being processed, if available
        last_product_id = None
        last_sku = None
        if progress.get("results"):
            last = progress["results"][-1]
            last_product_id = last.get("product_id")
            last_sku = last.get("sku")

        progress["errors"] = int(progress.get("errors") or 0) + 1
        progress["current_operation"] = "Failed"
        progress["error_details"] = {
            "type": exc_type,
            "message": exc_msg,
            "last_product_id": last_product_id,
            "last_sku": last_sku,
        }
        _log("ERROR", f"Експорт завершився аварійно: {exc_type}: {exc_msg}")
        _flush(force=True)
        try:
            cur.execute(
                f"""UPDATE sync_runs SET status='FAILED', finished_at=NOW(),
                       heartbeat_at=NOW(), updated_at=NOW(),
                       failed_count=%s, progress_json=%s,
                       current_stage='Failed', processed_count=%s, skipped_count=%s
                   WHERE id=%s""",
                (progress["failed"],
                 json.dumps(progress, ensure_ascii=False),
                 progress.get("processed", 0),
                 progress.get("skipped", 0),
                 run_id),
            )
        except Exception:
            pass
        logger.exception("Export run %s failed fatally", run_id)
        return {"success": False, "status": "FAILED", "error": exc_msg,
                "error_type": exc_type, "error_details": progress["error_details"]}
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass