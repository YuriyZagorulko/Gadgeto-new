"""Rozetka Seller API product operations client (Phase 6.3).

ONLY endpoints from the official documentation
(https://api-seller.rozetka.com.ua/apidoc/) are used.

  POST /sites                              (authentication - see client.py)
  GET  /goods/all                          search own items (article filter)
  GET  /goods/details                      details by item_id / rz_item_id
  POST /items-create/create                create ONE product (JSON)
  PUT  /items-create/mass-update-basic-data update name/description/params/
  PUT  /items/mass-update                  batch price & stock update
  GET  /items-create/producers             producer dictionary lookup
  GET  /items/sell-statuses                documented sell-status values

Response envelope (documented):
    {"success": true,  "content": ...}
    {"success": false, "errors": [...]} | {"success": false, "errors": {...}}

NOT documented by Rozetka (therefore NOT invented):
  * rate limits        -> conservative pacing delay is applied instead
  * batch size limits  -> batches kept small by the caller
  * any product upsert -> create vs update decided server-side via listings
                          state + one-time /goods/all adoption lookup.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Optional

import httpx

from app.channels.rozetka.client import (
    ROZETKA_API_URL,
    RozetkaAuthClient,
    RozetkaAuthError,
)

logger = logging.getLogger("channels.rozetka.api")

# Documented error codes
CODE_SESSION_EXPIRED = 6001
CODE_INVALID_CREDENTIALS = 5401
CODE_ENTITY_NOT_FOUND = 1019
CODE_MODEL_NOT_FOUND = 1404


class RozetkaApiError(Exception):
    """An error talking to the Rozetka Seller API.

    Attributes:
        error_type: one of SyncJobErrorType values.
        retryable: whether a limited retry makes sense.
        status_code: HTTP status when available.
        api_code: Rozetka MarketException numeric code when available.
        payload: raw `errors` value from the envelope (never credentials).
    """

    def __init__(self, message: str, *, error_type: str = "validation",
                 retryable: bool = False, status_code: int | None = None,
                 api_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable
        self.status_code = status_code
        self.api_code = api_code
        self.payload = payload


class RozetkaMassUpdateError(RozetkaApiError):
    """Per-item failures reported by PUT /items/mass-update.

    The documented response keeps HTTP 200 with success=false and an `errors`
    object keyed by item_rz_id.
    """

    def __init__(self, errors_by_item: dict):
        self.errors_by_item = errors_by_item or {}
        summary = "; ".join(
            f"{k}: {_format_reasons(v)}"
            for k, v in list(self.errors_by_item.items())[:5]
        )
        super().__init__(
            f"Rozetka vidkhiv chastynu pozytsiy masovoho onovlennya: {summary}",
            error_type="validation", retryable=False,
            payload=self.errors_by_item,
        )


def _format_reasons(item_errors: Any) -> str:
    reasons = []
    if isinstance(item_errors, dict):
        reasons = item_errors.get("reason") or []
    elif isinstance(item_errors, list):
        reasons = item_errors
    parts = []
    for r in reasons if isinstance(reasons, list) else [reasons]:
        if isinstance(r, dict):
            val = r.get("value")
            text = ", ".join(val) if isinstance(val, list) else str(val)
            parts.append(f"[{r.get('id')}] {text}")
        else:
            parts.append(str(r))
    return " ".join(parts) if parts else json_or_str(item_errors)


def json_or_str(value: Any) -> str:
    try:
        import json
        return json.dumps(value, ensure_ascii=False)[:300]
    except Exception:
        return str(value)


def extract_api_code(errors: Any) -> Optional[int]:
    """Best-effort extraction of the documented numeric error code."""
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            code = first.get("code")
            if isinstance(code, int):
                return code
            try:
                return int(str(first.get("code")))
            except (TypeError, ValueError):
                return None
    if isinstance(errors, dict):
        code = errors.get("code")
        if isinstance(code, int):
            return code
    return None


def envelope_message(errors: Any, fallback: str) -> str:
    """Human-readable message out of the documented `errors` shapes."""
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            return str(first.get("message") or fallback)
    if isinstance(errors, dict) and isinstance(errors.get("message"), str):
        return errors["message"]
    return fallback


class RozetkaApiClient:
    """Authenticated client for the documented product-export endpoints.

    One client per export run.  The access token is obtained via
    RozetkaAuthClient (POST /sites) on first use, cached in memory for the
    lifetime of the client, and refreshed once when the API reports an
    expired session (documented code 6001 / HTTP 401).
    """

    DEFAULT_TIMEOUT = 60.0
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 0.75
    # No documented rate limits: keep a conservative pacing delay.
    WRITE_DELAY = 0.2

    def __init__(self, auth_client: Optional[RozetkaAuthClient] = None,
                 http_client: Optional[httpx.Client] = None,
                 max_retries: int | None = None):
        self._auth_client = auth_client or RozetkaAuthClient()
        self._http = http_client or httpx.Client(timeout=self.DEFAULT_TIMEOUT)
        self._max_retries = self.MAX_RETRIES if max_retries is None else max_retries
        self._token: Optional[str] = None
        self._owns_http = http_client is None

    def close(self) -> None:
        if self._owns_http:
            try:
                self._http.close()
            except Exception:
                pass

    # ----------------- authentication --------------------------------

    def _ensure_token(self) -> str:
        if not self._token:
            result = self._auth_client.authenticate()
            self._token = result.access_token
            logger.info("Rozetka authenticated (seller_id=%s market_id=%s)",
                        result.seller_id, result.market_id)
        return self._token

    def _refresh_token(self) -> str:
        """Documented token expiry handling: re-authenticate once."""
        logger.info("Rozetka token expired - re-authenticating")
        self._token = None
        return self._ensure_token()

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # - core request ------------------------------------------------------

    def _request(self, method: str, path: str, *, params: dict | None = None,
                 json_body: Any = None) -> Any:
        """Execute one documented API call with the documented envelope.

        Retries ONLY transient classes (timeout/network/429/5xx), at most
        MAX_RETRIES times with exponential backoff + jitter.  Permanent
        errors (validation/auth/invalid data) are raised immediately.
        """
        attempt = 0
        reauthenticated = False
        last_exc: RozetkaApiError | None = None
        while True:
            try:
                resp = self._http.request(
                    method, f"{ROZETKA_API_URL}{path}",
                    headers=self._headers(self._ensure_token()),
                    params=params, json=json_body,
                )
                if resp.status_code in (401, 5401) and not reauthenticated:
                    reauthenticated = True
                    self._refresh_token()
                    continue
                resp.raise_for_status()
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise RozetkaApiError(
                        f"Invalid JSON response for {method} {path}: {exc}",
                        error_type="server_5xx", retryable=True,
                        status_code=resp.status_code) from exc
                return self._check_envelope(method, path, resp.status_code, data)
            except httpx.TimeoutException as exc:
                last_exc = RozetkaApiError(
                    f"Timeout request {method} {path}: {exc}",
                    error_type="timeout", retryable=True)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429:
                    last_exc = RozetkaApiError(
                        f"Rate limit (HTTP 429) on {method} {path}",
                        error_type="rate_limit", retryable=True,
                        status_code=status)
                elif status >= 500:
                    last_exc = RozetkaApiError(
                        f"Server error (HTTP {status}) on {method} {path}",
                        error_type="server_5xx", retryable=True,
                        status_code=status)
                else:
                    raise RozetkaApiError(
                        f"HTTP {status} from Rozetka on {method} {path}: "
                        f"{exc.response.text[:300]}",
                        error_type="validation", retryable=False,
                        status_code=status) from exc
            except httpx.RequestError as exc:
                last_exc = RozetkaApiError(
                    f"Network error {method} {path}: {exc}",
                    error_type="network", retryable=True)

            if last_exc is None or not last_exc.retryable:
                raise last_exc  # type: ignore[misc]
            if attempt >= self._max_retries:
                raise last_exc
            attempt += 1
            delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
            delay += random.uniform(0, 0.3)
            logger.warning("Retry %d/%d after %.1fs for %s %s: %s",
                           attempt, self._max_retries, delay,
                           method, path, last_exc)
            time.sleep(delay)

    def _check_envelope(self, method: str, path: str, status_code: int,
                        data: Any) -> Any:
        if not isinstance(data, dict) or "success" not in data:
            raise RozetkaApiError(
                f"Invalid response format from Rozetka for {method} {path}",
                error_type="server_5xx", retryable=True,
                status_code=status_code)
        if data.get("success"):
            return data.get("content")

        errors = data.get("errors")
        api_code = extract_api_code(errors)
        message = envelope_message(errors, "Rozetka returned error without description")

        # Capture Rozetka's error details dict (e.g. field-level validation)
        details_payload = None
        desc_message = None
        if isinstance(errors, dict):
            details_payload = errors.get("details")
            desc_message = errors.get("description")
            if desc_message and message == "check_correctness_of_data":
                message = f"{desc_message} {json.dumps(details_payload, ensure_ascii=False)[:500]}" if details_payload else desc_message

        if api_code in (CODE_ENTITY_NOT_FOUND, CODE_MODEL_NOT_FOUND):
            raise RozetkaApiError(message, error_type="not_found",
                                  retryable=False, status_code=status_code,
                                  api_code=api_code, payload=errors)
        if api_code == CODE_SESSION_EXPIRED or api_code == CODE_INVALID_CREDENTIALS:
            raise RozetkaApiError(message, error_type="auth",
                                  retryable=False, status_code=status_code,
                                  api_code=api_code, payload=errors)
        raise RozetkaApiError(message, error_type="validation", retryable=False,
                              status_code=status_code, api_code=api_code,
                              payload=errors)

    def _write_delay(self) -> None:
        time.sleep(self.WRITE_DELAY)

    def _write_delay(self) -> None:
        time.sleep(self.WRITE_DELAY)

    # - documented endpoints ---------------------------------------------

    def search_items(self, article: str | None = None,
                     page: int | None = None,
                     page_size: int | None = None) -> list[dict]:
        """GET /goods/all -- own items by article, pagination."""
        params: dict[str, Any] = {}
        if article:
            params["article"] = article
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        content = self._request("GET", "/goods/all", params=params) or {}
        items = content.get("items") or []
        return [i for i in items if isinstance(i, dict)]

    def find_item_by_article(self, article: str) -> Optional[dict]:
        """Idempotency helper: first /goods/all row matching `article`."""
        rows = self.search_items(article=article, page=1, page_size=100)
        for row in rows:
            if (row.get("article") or "") == article:
                return row
        return None

    def get_item_details(self, item_id: int | None = None,
                         rz_item_id: int | None = None) -> Optional[dict]:
        """GET /goods/details?item_id=...|rz_item_id=..."""
        params: dict[str, Any] = {}
        if item_id is not None:
            params["item_id"] = item_id
        if rz_item_id is not None:
            params["rz_item_id"] = rz_item_id
        if not params:
            raise ValueError("get_item_details requires item_id or rz_item_id")
        try:
            content = self._request("GET", "/goods/details", params=params)
        except RozetkaApiError as exc:
            if exc.api_code in (CODE_ENTITY_NOT_FOUND, CODE_MODEL_NOT_FOUND):
                return None
            raise
        if isinstance(content, dict):
            item = content.get("item")
            if isinstance(item, list) and item:
                return item[0]
            if isinstance(item, dict):
                return item
        return None

    def create_item(self, payload: dict) -> dict:
        """POST /items-create/create -- create ONE product.

        Returns {"item_id": N, "sync_source_id": N}.
        """
        self._write_delay()
        content = self._request("POST", "/items-create/create", json_body=payload)
        item = (content or {}).get("item") if isinstance(content, dict) else {}
        if not isinstance(item, dict) or "item_id" not in item:
            raise RozetkaApiError(
                f"Rozetka did not return item_id after creation: "
                f"{json_or_str(content)}",
                error_type="invalid_data", retryable=False)
        return item
    def update_items_basic_data(self, items: list[dict]) -> dict:
        """PUT /items-create/mass-update-basic-data.

        Returns {"items_updated": N} on success.
        """
        self._write_delay()
        return self._request("PUT", "/items-create/mass-update-basic-data",
                             json_body={"items": items}) or {}

    def mass_update_price_stock(self, items: list[dict],
                                ignore_check: bool = False) -> dict:
        """PUT /items/mass-update -- batch price & stock.

        On partial validation failure the API answers HTTP 200 with
        success=false and an errors map keyed by item_rz_id; that becomes a
        RozetkaMassUpdateError carrying the map for per-item handling.
        """
        self._write_delay()
        body: dict[str, Any] = {
            "isIgnoreCheck": 1 if ignore_check else 0,
            "items": items,
        }
        try:
            resp = self._http.request(
                "PUT", f"{ROZETKA_API_URL}/items/mass-update",
                headers=self._headers(self._ensure_token()),
                json=body,
            )
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as exc:
                raise RozetkaApiError(
                    f"Invalid JSON from Rozetka on PUT /items/mass-update: {exc}",
                    error_type="server_5xx", retryable=True,
                    status_code=resp.status_code) from exc
            if isinstance(data, dict) and not data.get("success"):
                errs = data.get("errors")
                if isinstance(errs, dict) and errs:
                    raise RozetkaMassUpdateError(errs)
            return self._check_envelope("PUT", "/items/mass-update",
                                        resp.status_code, data) or {}
        except httpx.TimeoutException as exc:
            raise RozetkaApiError(f"Timeout PUT /items/mass-update: {exc}",
                                  error_type="timeout", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            etype = ("rate_limit" if status == 429
                     else "server_5xx" if status >= 500 else "validation")
            raise RozetkaApiError(
                f"HTTP {status} on PUT /items/mass-update",
                error_type=etype, retryable=(etype != "validation"),
                status_code=status) from exc

    def search_producers(self, title: str | None = None,
                         page_size: int = 50) -> list[dict]:
        """GET /items-create/producers -- producer dictionary lookup."""
        params: dict[str, Any] = {"pageSize": page_size}
        if title:
            params["title"] = title
        content = self._request("GET", "/items-create/producers", params=params) or {}
        return [p for p in (content.get("producers") or []) if isinstance(p, dict)]

    def get_sell_statuses(self) -> list[dict]:
        """GET /items/sell-statuses -- the documented status dictionary."""
        content = self._request("GET", "/items/sell-statuses") or {}
        return content.get("sellStatuses") or []