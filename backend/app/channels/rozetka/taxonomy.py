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
import time
from datetime import datetime
from typing import Any, Optional

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

    def __init__(self, http_client: Optional[httpx.Client] = None):
        self._http_client = http_client or httpx.Client(timeout=30.0)
        self._base_url = ROZETKA_API_URL

    def refresh(self, channel_id: int, channel_code: str = "rozetka") -> dict:
        """Fetch the full Rozetka taxonomy and store it locally.

        Returns a stats dict with counts of created/updated records.
        """
        auth = RozetkaAuthClient()
        try:
            result = auth.authenticate()
        except RozetkaAuthError as e:
            raise RozetkaTaxonomyError(f"Authentication failed: {e}") from e

        token = result.access_token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        start = time.time()
        stats = {
            "categories_created": 0, "categories_updated": 0,
            "attributes_created": 0, "attributes_updated": 0,
            "values_created": 0, "values_updated": 0,
            "errors": 0, "duration_seconds": 0.0,
        }

        conn = psycopg2.connect(DB)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        now = datetime.utcnow()

        try:
            cat_stats = self._fetch_categories(channel_id, headers, cur, now)
            stats["categories_created"] = cat_stats["created"]
            stats["categories_updated"] = cat_stats["updated"]

            cur.execute(
                "SELECT external_id FROM channel_external_categories WHERE channel_id = %s",
                (channel_id,),
            )
            category_ids = [row["external_id"] for row in cur.fetchall()]

            for ext_cat_id in category_ids:
                try:
                    attr_stats = self._fetch_attributes_for_category(
                        channel_id, ext_cat_id, headers, cur, now,
                    )
                    for k in attr_stats:
                        stats[k] += attr_stats[k]
                except Exception:
                    stats["errors"] += 1
        finally:
            cur.close()
            conn.close()

        stats["duration_seconds"] = round(time.time() - start, 2)
        return stats

    # ── Categories ──────────────────────────────────────────────────────────

    def _fetch_categories(self, channel_id: int, headers: dict, cur, now: datetime) -> dict:
        """Fetch all active categories with pagination and upsert into DB."""
        created = 0
        updated = 0
        page = 1
        total_pages = 1

        while page <= total_pages:
            url = f"{self._base_url}/market-categories/search"
            params = {"page": page, "pageSizeLimit": self.PAGE_SIZE}

            resp = self._api_get(url, headers, params)
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
                # The API uses `category_id` as the identifier field
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

            page += 1

        return {"created": created, "updated": updated}

    # ── Attributes + Values ─────────────────────────────────────────────────

    def _fetch_attributes_for_category(
        self, channel_id: int, ext_cat_id: str, headers: dict, cur, now: datetime,
    ) -> dict:
        """Fetch attributes and their values for a single category."""
        stats = {
            "attributes_created": 0, "attributes_updated": 0,
            "values_created": 0, "values_updated": 0,
        }

        url = f"{self._base_url}/v1/market-categories/category-options"
        params = {"category_id": int(ext_cat_id)}

        resp = self._api_get(url, headers, params)
        data = self._parse_response(resp)

        attributes = []
        if isinstance(data, list):
            attributes = data
        elif isinstance(data, dict):
            content = data
            if isinstance(content, list):
                attributes = content
            else:
                for v in content.values():
                    if isinstance(v, list):
                        attributes = v
                        break

        for attr in attributes:
            if not isinstance(attr, dict):
                continue
            attr_id = str(attr.get("id"))
            if not attr_id:
                continue

            attr_name = attr.get("name") or ""
            attr_type = attr.get("attr_type") or ""
            unit = attr.get("unit") or ""
            raw_json = json.dumps(attr, ensure_ascii=False, default=str)

            cur.execute(
                """INSERT INTO channel_external_attributes
                   (channel_id, category_external_id, external_id, name,
                    param_type, unit, is_required, raw_json, fetched_at,
                    created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s, NOW(), NOW())
                   ON CONFLICT (channel_id, category_external_id, external_id)
                   DO UPDATE SET name = EXCLUDED.name,
                       param_type = EXCLUDED.param_type,
                       unit = EXCLUDED.unit,
                       raw_json = EXCLUDED.raw_json,
                       fetched_at = EXCLUDED.fetched_at,
                       updated_at = NOW()
                   RETURNING (xmax = 0) AS inserted""",
                (channel_id, ext_cat_id, attr_id, attr_name,
                 attr_type, unit, raw_json, now),
            )
            row = cur.fetchone()
            if row and row.get("inserted"):
                stats["attributes_created"] += 1
            else:
                stats["attributes_updated"] += 1

            # The API includes value_id/value_name on the attribute object
            value_id = attr.get("value_id")
            value_name = attr.get("value_name")
            if value_id is not None and value_name is not None:
                vs = self._upsert_value(channel_id, attr_id, value_id, value_name, cur, now)
                stats["values_created"] += vs["created"]
                stats["values_updated"] += vs["updated"]

        return stats

    def _upsert_value(self, channel_id: int, attr_ext_id: str,
                      value_id: Any, value_name: Any, cur, now: datetime) -> dict:
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

    def _api_get(self, url: str, headers: dict, params: dict) -> dict:
        try:
            response = self._http_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise RozetkaTaxonomyError(f"Request timed out: {url} - {e}") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise RozetkaTaxonomyError(
                    "Authentication expired or invalid. Re-authenticate and retry."
                ) from e
            raise RozetkaTaxonomyError(
                f"HTTP {e.response.status_code}: {e.response.text[:300]}"
            ) from e
        except httpx.RequestError as e:
            raise RozetkaTaxonomyError(f"Network error: {url} - {e}") from e
        except ValueError as e:
            raise RozetkaTaxonomyError(f"Invalid JSON response: {e}") from e

    def _parse_response(self, resp_data: dict) -> Any:
        """Extract the content from the standard Rozetka API envelope.

        The API sometimes returns content as a JSON string (not a parsed object),
        so we parse it if needed.
        """
        if not isinstance(resp_data, dict):
            return resp_data
        if not resp_data.get("success"):
            errors = resp_data.get("errors", "unknown error")
            raise RozetkaTaxonomyError(f"API returned error: {errors}")
        content = resp_data.get("content")
        # The API may return content as a JSON string needing parsing
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass
        return content