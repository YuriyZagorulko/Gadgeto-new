"""Rozetka taxonomy synchronization service.

Fetches the Rozetka marketplace category, attribute, and value dictionaries
from the official Seller API and persists them into the local
channel_external_* tables.

Documented endpoints:
  GET /market-categories/search  — category tree with pagination
  GET /v1/market-categories/category-options  — attributes + values for a category

Authentication: Bearer token obtained from POST /sites.
"""

import json
import random
import time
from datetime import datetime
from typing import Any, Callable, Optional

import httpx
import psycopg2
import psycopg2.extras

from app.channels.rozetka.client import (
    ROZETKA_API_URL,
    RozetkaAuthClient,
    RozetkaAuthError,
)
from app.core.db_connect import DB


class RozetkaTaxonomyError(Exception):
    """Raised when taxonomy fetch/refresh fails."""


class RozetkaTaxonomyService:
    """Fetches Rozetka taxonomy (categories, attributes, values) and persists
    them into the local channel_external_* tables."""

    PAGE_SIZE = 100
    MAX_RETRIES = 4
    BASE_RETRY_DELAY = 1.0  # seconds
    RATE_LIMIT_DELAY = 0.25  # seconds between category-option API calls
    VALUE_BATCH_SIZE = 500   # rows per batch INSERT

    def __init__(self, http_client: Optional[httpx.Client] = None):
        self._http_client = http_client or httpx.Client(timeout=60.0)
        self._base_url = ROZETKA_API_URL
        self._auth_client: Optional[RozetkaAuthClient] = None

    def refresh(self, channel_id: int, channel_code: str = "rozetka",
                progress_cb: Optional[Callable] = None) -> dict:
        """Fetch the full Rozetka taxonomy and store it locally.

        Optional `progress_cb(stage, processed, total, message)` is invoked to
        report operational progress (used by the background taxonomy runner).
        Returns a stats dict with counts of created/updated records.
        """
        if progress_cb:
            progress_cb("init", 0, 0, "Taxonomy refresh started")

        self._auth_client = RozetkaAuthClient()
        token, headers = self._authenticate()

        start = time.time()
        stats = {
            "categories_created": 0, "categories_updated": 0,
            "attributes_created": 0, "attributes_updated": 0,
            "attributes_required": 0,
            "values_created": 0, "values_updated": 0,
            "errors": 0, "duration_seconds": 0.0,
        }
        if progress_cb:
            progress_cb("auth", 1, 1, "Authentication successful")

        conn = psycopg2.connect(DB)
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        now = datetime.utcnow()

        try:
            cat_stats = self._fetch_categories(channel_id, headers, cur, now,
                                               progress_cb=progress_cb)
            conn.commit()
            stats["categories_created"] = cat_stats["created"]
            stats["categories_updated"] = cat_stats["updated"]
            if progress_cb:
                progress_cb("categories",
                            cat_stats["total"], cat_stats["total"],
                            f"Categories completed: {cat_stats['total']}")

            cur.execute(
                "SELECT external_id FROM channel_external_categories WHERE channel_id = %s",
                (channel_id,),
            )
            category_ids = [row["external_id"] for row in cur.fetchall()]

            total_cats = len(category_ids)
            for idx, ext_cat_id in enumerate(category_ids, start=1):
                if progress_cb:
                    progress_cb("attributes", idx - 1, total_cats,
                                f'Fetching attributes for category "{ext_cat_id}"')
                try:
                    attr_stats = self._fetch_attributes_for_category(
                        channel_id, ext_cat_id, headers, cur, now,
                    )
                    conn.commit()
                    stats["attributes_created"] += attr_stats["attributes_created"]
                    stats["attributes_updated"] += attr_stats["attributes_updated"]
                    stats["attributes_required"] += attr_stats["attributes_required"]
                    stats["values_created"] += attr_stats["values_created"]
                    stats["values_updated"] += attr_stats["values_updated"]
                    if progress_cb:
                        progress_cb(
                            "attributes", idx, total_cats,
                            f"Category {ext_cat_id}: "
                            f"{attr_stats['attributes_created'] + attr_stats['attributes_updated']} attributes, "
                            f"{attr_stats['values_created'] + attr_stats['values_updated']} values",
                        )
                except Exception as exc:
                    conn.rollback()
                    stats["errors"] += 1
                    if progress_cb:
                        progress_cb("attributes", idx, total_cats,
                                    f'Category {ext_cat_id} FAILED: {exc}')

                time.sleep(self.RATE_LIMIT_DELAY)
        finally:
            cur.close()
            conn.close()

        stats["duration_seconds"] = round(time.time() - start, 2)
        return stats

    def _authenticate(self) -> tuple:
        try:
            result = self._auth_client.authenticate()
        except RozetkaAuthError as e:
            raise RozetkaTaxonomyError(f"Authentication failed: {e}") from e
        token = result.access_token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        return token, headers

    def _reauthenticate(self) -> tuple:
        self._auth_client = RozetkaAuthClient()
        return self._authenticate()

    # ── Categories ──────────────────────────────────────────────────────────

    def _fetch_categories(self, channel_id: int, headers: dict, cur, now: datetime,
                          progress_cb: Optional[Callable] = None) -> dict:
        created = 0
        updated = 0
        processed = 0
        page = 1
        total_pages = 1

        while page <= total_pages:
            url = f"{self._base_url}/market-categories/search"
            params = {"page": page, "pageSizeLimit": self.PAGE_SIZE}

            resp = self._api_get_with_retry(url, headers, params)
            data = self._parse_response(resp)

            categories = []
            if isinstance(data, dict):
                content = data.get("content") or {}
                categories = content.get("marketCategorys") or []
                meta = content.get("_meta") or {}
                total_pages = meta.get("pageCount", 1) or 1
            elif isinstance(data, list):
                categories = data

            for cat in categories:
                if not isinstance(cat, dict):
                    continue
                ext_id = str(cat.get("category_id") or cat.get("id"))
                if not ext_id:
                    continue
                parent_id = cat.get("parent_id")
                parent_str = str(parent_id) if parent_id is not None else None
                name = (cat.get("name") or "").strip()
                if not name:
                    continue

                raw_json = json.dumps(cat, ensure_ascii=False, default=str)
                cur.execute(
                    """INSERT INTO channel_external_categories
                       (channel_id, external_id, parent_external_id, name,
                        raw_json, fetched_at, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                       ON CONFLICT (channel_id, external_id)
                       DO UPDATE SET name = EXCLUDED.name,
                           parent_external_id = EXCLUDED.parent_external_id,
                           raw_json = EXCLUDED.raw_json,
                           fetched_at = EXCLUDED.fetched_at,
                           updated_at = NOW()
                       RETURNING (xmax = 0) AS inserted""",
                    (channel_id, ext_id, parent_str, name, raw_json, now),
                )
                row = cur.fetchone()
                if row and row.get("inserted"):
                    created += 1
                else:
                    updated += 1
                processed += 1

            if progress_cb:
                total = total_pages * self.PAGE_SIZE
                progress_cb("categories", processed, total,
                            f"Categories: {processed} / {total}")
            page += 1

        return {"created": created, "updated": updated, "total": total_pages * self.PAGE_SIZE}

    # ── Attributes + Values ─────────────────────────────────────────────────

    def _fetch_attributes_for_category(
        self, channel_id: int, ext_cat_id: str, headers: dict, cur, now: datetime,
    ) -> dict:
        """Fetch attributes and their values for a single category.

        Deduplicates attribute UPSERTS, then batch-inserts values.
        """
        stats = {
            "attributes_created": 0, "attributes_updated": 0,
            "attributes_required": 0,
            "values_created": 0, "values_updated": 0,
        }

        url = f"{self._base_url}/v1/market-categories/category-options"
        params = {"category_id": int(ext_cat_id)}

        resp = self._api_get_with_retry(url, headers, params)
        data = self._parse_response(resp)

        all_rows: list[dict] = []
        if isinstance(data, list):
            all_rows = data
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    all_rows = v
                    break

        if not all_rows:
            return stats

        # Deduplicate attribute upserts
        seen_attrs: set[str] = set()
        for attr in all_rows:
            if not isinstance(attr, dict):
                continue
            attr_id = str(attr.get("id") or "")
            if not attr_id or attr_id in seen_attrs:
                continue
            seen_attrs.add(attr_id)

            attr_name = attr.get("name") or ""
            attr_type = attr.get("attr_type") or ""
            unit = attr.get("unit") or ""
            # Rozetka's only requiredness signal in the category-options payload
            # is `filter_type`: "main" = "в основному наборі" (the mandatory prim
            # ary set of characteristics).  Nothing else (our attributes, product
            # data, mapping counts) may influence this — the channel taxonomy is
            # the single source of truth for requiredness.
            filter_type = (attr.get("filter_type") or "").strip().lower()
            is_required = 1 if filter_type == "main" else 0
            raw_json = json.dumps(attr, ensure_ascii=False, default=str)

            cur.execute(
                """INSERT INTO channel_external_attributes
                   (channel_id, category_external_id, external_id, name,
                    param_type, unit, is_required, raw_json, fetched_at,
                    created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                   ON CONFLICT (channel_id, category_external_id, external_id)
                   DO UPDATE SET name = EXCLUDED.name,
                       param_type = EXCLUDED.param_type,
                       unit = EXCLUDED.unit,
                       is_required = EXCLUDED.is_required,
                       raw_json = EXCLUDED.raw_json,
                       fetched_at = EXCLUDED.fetched_at,
                       updated_at = NOW()
                   RETURNING (xmax = 0) AS inserted""",
                (channel_id, ext_cat_id, attr_id, attr_name,
                 attr_type, unit, is_required, raw_json, now),
            )
            row = cur.fetchone()
            if row and row.get("inserted"):
                stats["attributes_created"] += 1
            else:
                stats["attributes_updated"] += 1
            if is_required:
                stats["attributes_required"] += 1

        # Collect all value rows, deduplicate by (attr_id, value)
        value_rows: list[tuple] = []
        seen_values: set[tuple] = set()
        for attr in all_rows:
            if not isinstance(attr, dict):
                continue
            attr_id = str(attr.get("id") or "")
            if not attr_id:
                continue
            value_id = attr.get("value_id")
            value_name = attr.get("value_name")
            if value_id is not None and value_name is not None:
                vid = str(value_id)
                if isinstance(value_name, str):
                    vname = value_name.strip()
                elif isinstance(value_name, (dict, list)):
                    vname = json.dumps(value_name, ensure_ascii=False)
                else:
                    vname = str(value_name)
                if not vname:
                    continue
                # Dedup key
                dedup_key = (attr_id, vname)
                if dedup_key in seen_values:
                    continue
                seen_values.add(dedup_key)

                raw_json = json.dumps(
                    {"value_id": value_id, "value_name": value_name},
                    ensure_ascii=False, default=str,
                )
                value_rows.append((channel_id, attr_id, vid, vname, raw_json, now))

        # Batch upsert values
        if value_rows:
            for i in range(0, len(value_rows), self.VALUE_BATCH_SIZE):
                batch = value_rows[i:i + self.VALUE_BATCH_SIZE]
                psycopg2.extras.execute_values(
                    cur,
                    """INSERT INTO channel_external_values
                       (channel_id, attribute_external_id, external_id, value,
                        raw_json, fetched_at, created_at, updated_at)
                       VALUES %s
                       ON CONFLICT (channel_id, attribute_external_id, value)
                       DO UPDATE SET external_id = EXCLUDED.external_id,
                           raw_json = EXCLUDED.raw_json,
                           fetched_at = EXCLUDED.fetched_at,
                           updated_at = NOW()
                       RETURNING (xmax = 0) AS inserted""",
                    batch,
                    template="(%s, %s, %s, %s, %s, %s, NOW(), NOW())",
                    fetch=True,
                )
                for row in cur.fetchall():
                    if row and row.get("inserted"):
                        stats["values_created"] += 1
                    else:
                        stats["values_updated"] += 1

        return stats

    def _upsert_value(self, channel_id: int, attr_ext_id: str,
                      value_id: Any, value_name: Any, cur, now: datetime) -> dict:
        """Single-row value upsert (backward compat)."""
        vid = str(value_id)
        if isinstance(value_name, str):
            vname = value_name.strip()
        elif isinstance(value_name, (dict, list)):
            vname = json.dumps(value_name, ensure_ascii=False)
        else:
            vname = str(value_name)
        if not vname:
            return {"created": 0, "updated": 0}

        raw_json = json.dumps({"value_id": value_id, "value_name": value_name},
                              ensure_ascii=False, default=str)
        cur.execute(
            """INSERT INTO channel_external_values
               (channel_id, attribute_external_id, external_id, value,
                raw_json, fetched_at, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
               ON CONFLICT (channel_id, attribute_external_id, value)
               DO UPDATE SET external_id = EXCLUDED.external_id,
                   raw_json = EXCLUDED.raw_json,
                   fetched_at = EXCLUDED.fetched_at,
                   updated_at = NOW()
               RETURNING (xmax = 0) AS inserted""",
            (channel_id, attr_ext_id, vid, vname, raw_json, now),
        )
        row = cur.fetchone()
        ins = row and row.get("inserted")
        return {"created": 1 if ins else 0, "updated": 0 if ins else 1}

    # ── HTTP helpers ────────────────────────────────────────────────────

    def _api_get_with_retry(self, url: str, headers: dict, params: dict) -> dict:
        last_exc: Optional[Exception] = None
        _headers = dict(headers)
        reauthenticated = False

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self._http_client.get(url, headers=_headers, params=params)
                response.raise_for_status()
                resp_json = response.json()
                # Envelope-level auth error → re-authenticate & retry once
                if isinstance(resp_json, dict) and not resp_json.get("success"):
                    errs = resp_json.get("errors")
                    if isinstance(errs, dict):
                        code = errs.get("code")
                        if not reauthenticated and code in (6001, 5401):
                            reauthenticated = True
                            try:
                                _, fresh_headers = self._reauthenticate()
                                _headers = dict(fresh_headers)
                                response = self._http_client.get(url, headers=_headers, params=params)
                                response.raise_for_status()
                                return response.json()
                            except Exception as auth_exc:
                                last_exc = RozetkaTaxonomyError(
                                    f"Re-authentication failed, aborting: {auth_exc}"
                                )
                                break
                return resp_json
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 401 and attempt == 1:
                    try:
                        _, fresh_headers = self._reauthenticate()
                        _headers = dict(fresh_headers)
                        response = self._http_client.get(url, headers=_headers, params=params)
                        response.raise_for_status()
                        return response.json()
                    except Exception as auth_exc:
                        last_exc = RozetkaTaxonomyError(
                            f"Re-authentication failed, aborting: {auth_exc}"
                        )
                        break
                elif status == 429:
                    delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    last_exc = RozetkaTaxonomyError(f"Rate limited (429) after {attempt} attempt(s)")
                    continue
                elif status >= 500:
                    delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    last_exc = RozetkaTaxonomyError(f"HTTP {status} after {attempt} attempt(s)")
                    continue
                else:
                    last_exc = RozetkaTaxonomyError(f"HTTP {status}: {e.response.text[:300]}")
                    break
            except httpx.TimeoutException as e:
                delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(delay)
                last_exc = RozetkaTaxonomyError(f"Request timed out (attempt {attempt}): {url}")
                continue
            except httpx.RequestError as e:
                delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(delay)
                last_exc = RozetkaTaxonomyError(f"Network error (attempt {attempt}): {url} - {e}")
                continue
            except ValueError as e:
                last_exc = RozetkaTaxonomyError(f"Invalid JSON response: {e}")
                break

        raise last_exc or RozetkaTaxonomyError(f"Request failed after {self.MAX_RETRIES} retries: {url}")

    def _parse_response(self, resp_data: dict) -> Any:
        if not isinstance(resp_data, dict):
            return resp_data
        if not resp_data.get("success"):
            errors = resp_data.get("errors", "unknown error")
            raise RozetkaTaxonomyError(f"API returned error: {errors}")
        content = resp_data.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass
        return content
