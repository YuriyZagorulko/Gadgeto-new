"""BRAIN (brain.com.ua) supplier importer.

Downloads the current catalog from the official BRAIN partner API,
parses it, and returns normalized products for persistence through the
shared import pipeline (ImportRunner / importer_service).

Reference: https://api.brain.com.ua/help

Key API facts (verified against the live API):
- Authentication: ``POST /auth`` with FORM fields ``login`` and
  ``password`` (MD5-hashed). Returns ``{"status": 1, "result": "<SID>"}``.
  The SID is passed as a URL path segment on every subsequent call.
- Rate limit: at most 3 requests per second (HTTP 429 / error_code 115).
- ``GET /categories/{SID}`` returns the full category tree with
  ``categoryID`` / ``parentID`` / ``realcat`` / ``name``. A category with
  ``realcat > 0`` is VIRTUAL and contains the products of the category
  referenced by ``realcat``.
- ``GET /products/{categoryID}/{SID}?limit=&offset=`` returns the products
  of the category AND all of its child categories as
  ``{"result": {"list": [...], "count": N}}``. ``limit`` max is 100
  (1000 with OWN_MODE; exceeding it yields error_code 20).
- ``stocks`` / ``stocks_expected`` / ``available`` are only returned for
  OWN_LOGISTICS_MODE accounts — their absence is handled gracefully.
- ``POST /products/content/{SID}`` (form field ``productIDs`` as a
  comma-separated list) returns base content (description, options,
  images, dimensions) for a batch of products.
- ``GET /vendors/{SID}`` returns vendor entries scoped per category
  (``vendorID`` is only unique within a category).

Memory safety: the importer never accumulates the full catalog. It walks
top-level categories one at a time, fetches product pages one at a time
and yields normalized products one at a time through a generator, exactly
like the IT-Link and DC-Link importers.

Secrets handling: the login, the password, the MD5 password hash and the
SID are NEVER written to logs, exceptions, or import reports.
"""

import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests

from app.imports.attribute_processor import (
    process_attribute,
    merge_attributes,
    ATTR_SKIP,
    ATTR_UNKNOWN_NAME,
    ATTR_UNKNOWN_VALUE,
)
from app.imports.category_utils import resolve_category_path
from app.imports.import_stats import ImportStats as SharedImportStats
from app.imports.pricing_service import calculate_price, calculate_old_price, find_markup_multiplier
from app.core.config import settings
from app.services.seo import generate_product_seo

SUPPLIER_CODE = "brain"
SKU_PREFIX = "BRA-"
DEFAULT_BASE_URL = "https://api.brain.com.ua"
DEFAULT_LANG = "ua"

# BRAIN allows at most 3 requests per second — keep a safe interval.
DEFAULT_REQUEST_INTERVAL_SECONDS = 0.35

# Retry policy for transient failures (network errors, 5xx, rate limits).
_MAX_ATTEMPTS = 6
_RETRY_BACKOFF_SECONDS = 1.0
_RATE_LIMIT_BACKOFF_SECONDS = 2.0

# Products per /products page. BRAIN: 100 for regular accounts, up to 1000
# with OWN_MODE. The client lowers this automatically on error_code 20.
DEFAULT_PAGE_LIMIT = 100

# Product IDs per /products/content batch request.
CONTENT_BATCH_SIZE = 100

# BRAIN API error codes (subset relevant to catalog import).
_ERR_LOGIN_REQUIRED = 1
_ERR_PASSWORD_REQUIRED = 2
_ERR_SID_INVALID = 4
_ERR_SID_EXPIRED = 5
_ERR_BAD_CREDENTIALS = 6
_ERR_USER_BLOCKED = 7
_ERR_LIMIT_EXCEEDED = 20
_ERR_TOO_MANY_REQUESTS = 115


def _resolve_credentials() -> Tuple[str, str]:
    """Resolve BRAIN credentials from configuration.

    Canonical names are ``SUPPLIER_BRAIN_LOGIN`` / ``SUPPLIER_BRAIN_PASSWORD``
    (same convention as the other suppliers). The legacy login name
    ``BRAIN_LOGIN`` is supported as a fallback so existing deployments keep
    working. The password is read from ``BRAIN_PASSWORD`` (or the canonical
    ``SUPPLIER_BRAIN_PASSWORD``).
    """
    login = (
        getattr(settings, "SUPPLIER_BRAIN_LOGIN", "")
        or getattr(settings, "BRAIN_LOGIN", "")
        or ""
    ).strip()
    password = (
        getattr(settings, "SUPPLIER_BRAIN_PASSWORD", "")
        or getattr(settings, "BRAIN_PASSWORD", "")
        or ""
    )
    return login, password


def _is_truthy_flag(value: Any) -> bool:
    """Interpret BRAIN boolean-ish flags (bool, 0/1 int, or "0"/"1" str)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return False


def _validate_attributes(raw_attributes, stats, sku, logger_prefix=""):
    """Check that no attribute name collides with protected core fields.
    Logs a warning and returns only safe attributes (non-core-field names)."""
    safe = []
    for attr_name, attr_value in raw_attributes:
        key = attr_name.strip().lower().replace(" ", "_").replace("-", "_")
        if key in PROTECTED_CORE_FIELDS:
            msg = f"Supplier attribute '{attr_name}' collides with protected core field — skipping"
            if stats is not None:
                stats.warnings.append(f"{logger_prefix} SKU {sku}: {msg}")
            else:
                import logging
                logging.getLogger(__name__).warning(f"{logger_prefix} SKU {sku}: {msg}")
        safe.append((attr_name, attr_value))
    return safe


@dataclass
class NormalizedProduct:
    supplier: str = SUPPLIER_CODE
    supplier_sku: str = ""
    sku: str = ""
    name: str = ""
    description: str = ""
    short_description: str = ""
    price: int = 0
    old_price: Optional[int] = None
    category_path: str = ""
    images: List[str] = field(default_factory=list)
    brand: str = ""
    in_stock: bool = True
    attributes: List[Tuple[str, str]] = field(default_factory=list)
    raw_attributes: List[Tuple[str, str]] = field(default_factory=list)
    seo_title: str = ""
    seo_description: str = ""
    focus_keyphrase: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImportStats(SharedImportStats):
    """BRAIN import statistics.

    Extends the shared ImportStats with an ``archived`` counter for products
    flagged ``is_archive`` by BRAIN (imported but forced out-of-stock).
    """

    archived: int = 0

    def to_summary_dict(self) -> dict:
        summary = super().to_summary_dict()
        summary["archived"] = self.archived
        return summary


class BrainClient:
    """Thin HTTP client for the BRAIN partner API.

    Responsibilities:
    - authentication (MD5-hashed password, form-encoded POST) and SID
      lifecycle, including automatic re-authentication when the SID
      expires (error codes 4/5);
    - rate limiting (BRAIN allows max 3 requests/second);
    - retry with exponential backoff for network errors, 5xx and 429;
    - response envelope handling (``{"status": 1, "result": ...}``).

    The login, password, MD5 hash and SID never appear in raised
    exception messages, so they can never leak into import logs.
    """

    def __init__(self, base_url: Optional[str] = None,
                 login: Optional[str] = None,
                 password: Optional[str] = None,
                 page_limit: Optional[int] = None,
                 request_interval: Optional[float] = None,
                 timeout: Optional[Tuple[float, float]] = None):
        self.base_url = (base_url or getattr(settings, "BRAIN_API_URL", "")
                         or DEFAULT_BASE_URL).rstrip("/")
        self._login = login
        self._password = password
        self._sid: Optional[str] = None
        self._reauth_count = 0
        limit = int(page_limit or getattr(settings, "BRAIN_PAGE_LIMIT", 0)
                    or DEFAULT_PAGE_LIMIT)
        self._page_limit = max(1, min(limit, 1000))
        self.request_interval = (DEFAULT_REQUEST_INTERVAL_SECONDS
                                 if request_interval is None
                                 else float(request_interval))
        self.timeout = timeout or (10, 90)
        self._last_request_ts = 0.0

    # ------------------------------------------------------------ properties
    @property
    def sid(self) -> Optional[str]:
        """Current session identifier (runtime secret — do not log)."""
        return self._sid

    @property
    def page_limit(self) -> int:
        """Current max products per page (lowered automatically on error 20)."""
        return self._page_limit

    # ------------------------------------------------------------- internals
    def _throttle(self) -> None:
        """Enforce the minimum interval between consecutive API requests."""
        if self.request_interval <= 0:
            return
        now = time.monotonic()
        wait = self.request_interval - (now - self._last_request_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def authenticate(self) -> str:
        """Authenticate and store a fresh SID. Returns the SID."""
        login = self._login
        password = self._password
        if login is None or password is None:
            resolved_login, resolved_password = _resolve_credentials()
            login = login if login is not None else resolved_login
            password = password if password is not None else resolved_password
        if not login or not password:
            raise BrainConfigError(
                "Не налаштовані облікові дані BRAIN. "
                "Встановіть SUPPLIER_BRAIN_LOGIN / SUPPLIER_BRAIN_PASSWORD."
            )
        password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
        self._throttle()
        try:
            resp = requests.post(
                f"{self.base_url}/auth",
                data={"login": login, "password": password_md5},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise BrainAPIError(
                f"Помилка мережі під час авторизації BRAIN: {type(exc).__name__}"
            ) from exc
        if resp.status_code >= 400:
            raise BrainAPIError(
                f"Помилка авторизації BRAIN: HTTP {resp.status_code}"
            )
        try:
            payload = resp.json()
        except ValueError as exc:
            raise BrainAPIError(
                "Невірний формат відповіді авторизації BRAIN (не JSON)"
            ) from exc
        if isinstance(payload, dict) and payload.get("status") == 1 and payload.get("result"):
            self._sid = str(payload["result"])
            self._reauth_count = 0
            return self._sid
        code = payload.get("error_code") if isinstance(payload, dict) else None
        if code in (_ERR_LOGIN_REQUIRED, _ERR_PASSWORD_REQUIRED,
                    _ERR_BAD_CREDENTIALS, _ERR_USER_BLOCKED):
            raise BrainAuthError(
                f"Помилка авторизації BRAIN: невірні облікові дані (код {code})"
            )
        raise BrainAPIError(
            f"Помилка авторизації BRAIN (код {code})", error_code=code
        )

    def _ensure_sid(self) -> str:
        if not self._sid:
            self.authenticate()
        return str(self._sid)

    def _request(self, method: str, path_label: str, path_template: str,
                 path_params: Optional[Dict[str, Any]] = None, *,
                 params: Optional[Dict[str, Any]] = None,
                 data: Optional[Dict[str, Any]] = None,
                 timeout: Optional[Tuple[float, float]] = None) -> Any:
        """Execute one API call and return the parsed ``result`` value.

        ``path_template`` may reference ``{sid}`` (and other parameters);
        it is re-rendered on every attempt so a SID refreshed by
        re-authentication is always used.  Never includes the SID in
        error messages.
        """
        self._ensure_sid()
        params_map = dict(path_params or {})
        attempt = 0
        reauthed_for_request = False
        while True:
            attempt += 1
            if attempt > _MAX_ATTEMPTS:
                raise BrainAPIError(
                    f"Перевищено кількість спроб запиту BRAIN ({path_label})"
                )
            url = self.base_url + path_template.format(
                sid=self._sid, **params_map
            )
            self._throttle()
            try:
                resp = requests.request(
                    method, url, params=params, data=data,
                    timeout=timeout or self.timeout,
                )
            except requests.RequestException as exc:
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue
                raise BrainAPIError(
                    f"Помилка мережі BRAIN ({path_label}): {type(exc).__name__}"
                ) from exc

            if resp.status_code == 429:
                # BRAIN rate limit (max 3 req/s) — wait and retry.
                time.sleep(_RATE_LIMIT_BACKOFF_SECONDS)
                continue
            if resp.status_code >= 500:
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))
                    continue
                raise BrainAPIError(
                    f"Помилка сервера BRAIN: HTTP {resp.status_code} ({path_label})"
                )
            if resp.status_code >= 400:
                raise BrainAPIError(
                    f"Помилка запиту BRAIN: HTTP {resp.status_code} ({path_label})"
                )
            try:
                payload = resp.json()
            except ValueError as exc:
                raise BrainAPIError(
                    f"Невірний формат відповіді BRAIN ({path_label}): не JSON"
                ) from exc
            if not isinstance(payload, dict):
                raise BrainAPIError(
                    f"Невірний формат відповіді BRAIN ({path_label})"
                )
            if payload.get("status") == 1:
                return payload.get("result")

            code = payload.get("error_code")
            message = str(payload.get("error_message") or "").strip()
            if (code in (_ERR_SID_INVALID, _ERR_SID_EXPIRED)
                    and not reauthed_for_request
                    and self._reauth_count < 5):
                # SID expired/faulty — re-authenticate once and retry the
                # request with the fresh SID.
                reauthed_for_request = True
                self._reauth_count += 1
                self.authenticate()
                continue
            if code == _ERR_TOO_MANY_REQUESTS:
                time.sleep(_RATE_LIMIT_BACKOFF_SECONDS)
                continue
            if code in (_ERR_BAD_CREDENTIALS, _ERR_USER_BLOCKED):
                raise BrainAuthError(
                    f"Помилка авторизації BRAIN (код {code})"
                )
            raise BrainAPIError(
                f"Помилка API BRAIN ({path_label}): код {code} {message}".rstrip(),
                error_code=code,
            )

    # ------------------------------------------------------------ public API
    def get_categories(self, lang: str = DEFAULT_LANG) -> List[dict]:
        """Full category tree (categoryID / parentID / realcat / name)."""
        result = self._request(
            "GET", "categories", "/categories/{sid}",
            params={"lang": lang},
        )
        return result if isinstance(result, list) else []

    def get_vendors(self, lang: str = DEFAULT_LANG) -> List[dict]:
        """Vendor list (entries are scoped per categoryID)."""
        result = self._request(
            "GET", "vendors", "/vendors/{sid}",
            params={"lang": lang},
        )
        return result if isinstance(result, list) else []

    def get_products_page(self, category_id: int, limit: Optional[int] = None,
                          offset: int = 0, lang: str = DEFAULT_LANG) -> Dict[str, Any]:
        """One page of products for a category (includes child categories).

        Returns ``{"list": [...], "count": N}`` where ``count`` is the
        number of products in the whole category subtree.
        """
        limit = int(limit or self._page_limit)
        try:
            result = self._request(
                "GET", "products", "/products/{category_id}/{sid}",
                path_params={"category_id": int(category_id)},
                params={"lang": lang, "limit": limit, "offset": int(offset)},
            )
        except BrainAPIError as exc:
            if (exc.error_code == _ERR_LIMIT_EXCEEDED
                    and limit > DEFAULT_PAGE_LIMIT):
                # Account without OWN_MODE — lower the page size once and retry.
                self._page_limit = DEFAULT_PAGE_LIMIT
                return self.get_products_page(
                    category_id, limit=DEFAULT_PAGE_LIMIT,
                    offset=offset, lang=lang,
                )
            raise
        if not isinstance(result, dict) or not isinstance(result.get("list"), list):
            raise BrainAPIError("Неочікуваний формат відповіді /products BRAIN")
        return result

    def get_products_content(self, product_ids: List[Any],
                             lang: str = DEFAULT_LANG,
                             batch_size: Optional[int] = None) -> List[dict]:
        """Base content (description, options, images) for product ID batches.

        ``POST /products/content/{SID}`` with ``productIDs`` as a
        comma-separated form field.  Requests are batched (default 100
        IDs per call) to keep responses safely sized.
        """
        batch = int(batch_size or CONTENT_BATCH_SIZE)
        ids = [str(pid) for pid in product_ids if pid is not None]
        results: List[dict] = []
        for i in range(0, len(ids), batch):
            chunk = ids[i:i + batch]
            result = self._request(
                "POST", "products/content", "/products/content/{sid}",
                data={"lang": lang, "productIDs": ",".join(chunk)},
            )
            if isinstance(result, dict):
                items = result.get("list") or []
            elif isinstance(result, list):
                items = result
            else:
                items = []
            results.extend(items)
        return results

    def get_product(self, product_id: int, lang: str = DEFAULT_LANG) -> dict:
        """Full information for a single product."""
        result = self._request(
            "GET", "product", "/product/{product_id}/{sid}",
            path_params={"product_id": int(product_id)},
            params={"lang": lang},
        )
        return result if isinstance(result, dict) else {}

    def get_product_options(self, product_id: int,
                            lang: str = DEFAULT_LANG) -> List[dict]:
        """All characteristics of a product (OptionID/OptionName/ValueID/ValueName)."""
        result = self._request(
            "GET", "product_options", "/product_options/{product_id}/{sid}",
            path_params={"product_id": int(product_id)},
            params={"lang": lang},
        )
        return result if isinstance(result, list) else []

    def get_product_pictures(self, product_id: int) -> List[dict]:
        """Image URL sets for a single product (priority-ordered)."""
        result = self._request(
            "GET", "product_pictures", "/product_pictures/{product_id}/{sid}",
            path_params={"product_id": int(product_id)},
        )
        return result if isinstance(result, list) else []

    def get_modified_products(self, modified_type: str = "",
                              modified_time: Optional[str] = None,
                              limit: int = 1000, offset: int = 0) -> dict:
        """IDs of products modified after ``modified_time`` (incremental sync)."""
        t = (modified_type or "").strip()
        params: Dict[str, Any] = {
            "limit": max(100, min(int(limit), 10000)),
            "offset": int(offset),
        }
        if modified_time:
            params["modified_time"] = modified_time
        if t:
            result = self._request(
                "GET", "modified_products",
                "/modified_products/{mtype}/{sid}",
                path_params={"mtype": t}, params=params,
            )
        else:
            result = self._request(
                "GET", "modified_products", "/modified_products/{sid}",
                params=params,
            )
        return result if isinstance(result, dict) else {}

    def logout(self) -> None:
        """Best-effort session teardown. Never raises, never logs the SID."""
        sid = self._sid
        self._sid = None
        if not sid:
            return
        try:
            self._throttle()
            requests.get(f"{self.base_url}/logout/{sid}", timeout=15)
        except requests.RequestException:
            pass


class BrainImporter:
    """BRAIN catalog importer.

    Usage (via the shared import pipeline)::

        importer = BrainImporter(category_map=db_category_map)
        stats = importer.run("full")   # stats.products is a generator

    The importer walks top-level BRAIN categories (each fetch covers the
    whole subtree, so top-level roots partition the catalog and products
    are never fetched twice), enriches each page through the batched
    /products/content endpoint and yields NormalizedProduct objects one
    at a time.
    """

    SKU_PREFIX = SKU_PREFIX
    SUPPLIER_CODE = SUPPLIER_CODE

    def __init__(self, feed_path: str = None, categories_path: str = None,
                 category_map: dict = None, client: Optional[BrainClient] = None,
                 resolver=None):
        self.feed_path = feed_path
        self.categories_path = categories_path
        self.stats = ImportStats()
        self.category_map = dict(category_map) if category_map else {}
        self.client = client
        self.resolver = resolver
        # categoryID -> category name
        self._cat_name_by_id: Dict[int, str] = {}
        # categoryID -> realcat reference (0 for real categories)
        self._realcat_by_id: Dict[int, int] = {}
        # Top-level categories whose subtree is fetched (the partition)
        self._roots: List[int] = []
        # (categoryID, vendorID) -> vendor name (BRAIN vendorIDs are per-category)
        self._vendor_by_cat_vendor: Dict[Tuple[str, str], str] = {}
        self._vendor_by_id: Dict[str, str] = {}
        # Internal category id cache (category_path -> id | None)
        self._internal_cat_ids: Dict[str, Optional[int]] = {}
        self._seen_skus: set = set()

    # ------------------------------------------------------------- auth/api
    def _get_client(self) -> BrainClient:
        if self.client is None:
            self.client = BrainClient()
        return self.client

    def _login(self) -> BrainClient:
        client = self._get_client()
        client.authenticate()
        return client

    # ----------------------------------------------------------- categories
    def _load_categories(self, client: BrainClient) -> List[dict]:
        categories = client.get_categories()
        self._cat_name_by_id = {}
        self._realcat_by_id = {}
        for cat in categories:
            cid = cat.get("categoryID")
            if cid is None:
                continue
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            self._cat_name_by_id[cid_int] = str(cat.get("name") or "").strip()
            try:
                realcat = int(cat.get("realcat") or 0)
            except (TypeError, ValueError):
                realcat = 0
            self._realcat_by_id[cid_int] = realcat
        return categories

    def _resolve_real_category(self, category_id: Optional[int]) -> Optional[int]:
        """Resolve a (possibly virtual) category to its real category.

        Virtual categories carry ``realcat > 0`` pointing at the real
        category whose products they contain. Chains and self-references
        are resolved safely with a cycle guard.
        """
        if category_id is None:
            return None
        cid = category_id
        seen = set()
        while cid in self._realcat_by_id and cid not in seen:
            seen.add(cid)
            realcat = self._realcat_by_id[cid]
            if not realcat or realcat == cid:
                return cid
            cid = realcat
        return cid if cid in self._realcat_by_id else None

    @staticmethod
    def select_fetch_roots(categories: List[dict]) -> List[int]:
        """Choose the categories whose subtrees cover the whole catalog.

        ``GET /products/{categoryID}`` returns products of the category AND
        all of its child categories, so fetching only top-level categories
        (``parentID == 1``) covers every product exactly once. Top-level
        VIRTUAL categories (``realcat > 0``) are skipped: their products are
        the products of the referenced real category, which is covered by
        its own top-level ancestor root.
        """
        roots: List[int] = []
        seen = set()
        for cat in categories:
            try:
                parent = int(cat.get("parentID") or 0)
            except (TypeError, ValueError):
                parent = 0
            if parent != 1:
                continue
            if int(cat.get("realcat") or 0) > 0:
                continue  # virtual top-level — covered by the real subtree
            cid = cat.get("categoryID")
            if cid is None:
                continue
            try:
                cid_int = int(cid)
            except (TypeError, ValueError):
                continue
            if cid_int not in seen:
                seen.add(cid_int)
                roots.append(cid_int)
        return sorted(roots)

    def _warn_uncovered_categories(self, categories: List[dict]) -> None:
        """Warn about categories outside every root subtree (orphans)."""
        known_ids = set(self._cat_name_by_id.keys())
        orphans = []
        for cat in categories:
            cid = cat.get("categoryID")
            if cid is None:
                continue
            try:
                parent = int(cat.get("parentID") or 0)
            except (TypeError, ValueError):
                parent = 0
            if parent == 1:
                continue
            if parent not in known_ids:
                orphans.append(str(cid))
        if orphans:
            self.stats.warnings.append(
                f"BRAIN містить {len(orphans)} категорій із неіснуючим "
                f"батьком (поза деревом імпорту): {', '.join(orphans[:10])}"
            )

    # -------------------------------------------------------------- vendors
    def _load_vendors(self, client: BrainClient) -> None:
        """Load the vendor list into lookup maps.

        BRAIN ``vendorID`` is only unique within a category, so the primary
        map is keyed by ``(categoryID, vendorID)`` with a best-effort
        fallback keyed by ``vendorID`` alone.
        """
        self._vendor_by_cat_vendor = {}
        self._vendor_by_id = {}
        try:
            vendors = client.get_vendors()
        except (BrainError, requests.RequestException) as exc:
            self.stats.warnings.append(
                f"Не вдалося завантажити виробників BRAIN: {exc}"
            )
            return
        for vendor in vendors:
            if not isinstance(vendor, dict):
                continue
            vid = vendor.get("vendorID")
            name = str(vendor.get("name") or "").strip()
            if vid is None or not name:
                continue
            vid = str(vid)
            cid = vendor.get("categoryID")
            if cid is not None:
                self._vendor_by_cat_vendor[(str(cid), vid)] = name
            self._vendor_by_id.setdefault(vid, name)

    def _vendor_name(self, item: dict) -> str:
        vid = item.get("vendorID")
        if vid is None:
            return ""
        vid = str(vid)
        cid = item.get("categoryID")
        if cid is not None:
            name = self._vendor_by_cat_vendor.get((str(cid), vid))
            if name:
                return name
        return self._vendor_by_id.get(vid, "")

    # ------------------------------------------------------------ discovery
    def download_feed(self) -> Dict[str, Any]:
        """Authenticate and prepare the import: categories, vendors, counts.

        Performs a lightweight discovery pass (one ``limit=1`` request per
        top-level root) so the import job gets an accurate total product
        count for progress reporting before streaming starts.
        """
        client = self._login()
        categories = self._load_categories(client)
        if not categories:
            raise BrainAPIError("BRAIN не повернув жодної категорії")
        self._roots = self.select_fetch_roots(categories)
        if not self._roots:
            raise BrainAPIError("BRAIN не повернув жодної реальної кореневої категорії")
        self._warn_uncovered_categories(categories)
        self._load_vendors(client)

        total = 0
        for root_id in self._roots:
            try:
                info = client.get_products_page(root_id, limit=1, offset=0)
                count = int(info.get("count") or 0)
            except (BrainError, requests.RequestException) as exc:
                self.stats.warnings.append(
                    f"Не вдалося визначити кількість товарів у категорії "
                    f"{root_id}: {exc}"
                )
                count = 0
            total += count

        self.stats.feed_count = total
        self.stats.total = total
        return {"categories": categories, "roots": list(self._roots), "total": total}

    # ------------------------------------------------------------ streaming
    def _enrich_batch(self, client: BrainClient, items: List[dict]) -> Dict[str, dict]:
        """Fetch base content for one page of products (batched request)."""
        ids = [it.get("productID") for it in items if it.get("productID") is not None]
        if not ids:
            return {}
        try:
            content_items = client.get_products_content(ids)
        except (BrainError, requests.RequestException) as exc:
            self.stats.warnings.append(
                f"Не вдалося отримати контент для {len(ids)} товарів: {exc}"
            )
            return {}
        by_id: Dict[str, dict] = {}
        for content in content_items:
            if isinstance(content, dict) and content.get("productID") is not None:
                by_id[str(content["productID"])] = content
        return by_id

    @staticmethod
    def _merge_item(base: dict, enriched_by_id: Dict[str, dict]) -> dict:
        content = enriched_by_id.get(str(base.get("productID")))
        if not content:
            return base
        merged = dict(base)
        for key in _CONTENT_MERGE_FIELDS:
            value = content.get(key)
            if value:
                merged[key] = value
        if not merged.get("name") and content.get("name"):
            merged["name"] = content.get("name")
        if not merged.get("brief_description") and content.get("brief_description"):
            merged["brief_description"] = content.get("brief_description")
        return merged

    def parse_products(self, feed_context: Optional[dict] = None) -> Iterator[NormalizedProduct]:
        """Stream the whole BRAIN catalog as normalized products.

        Yields one NormalizedProduct at a time — no full product list is
        retained in memory.  A failure on one category or one product is
        logged and does not abort the import.
        """
        client = self._get_client()
        try:
            for root_id in self._roots:
                try:
                    yield from self._import_root(client, root_id)
                except (BrainError, requests.RequestException) as exc:
                    # One failing category must not lose the whole import.
                    self.stats.errors.append({
                        "root_category": root_id,
                        "error": str(exc),
                    })
                    self.stats.warnings.append(
                        f"Категорію {root_id} пропущено через помилку API: {exc}"
                    )
                    continue
        finally:
            try:
                client.logout()
            except Exception:
                pass

    def _import_root(self, client: BrainClient,
                     root_id: int) -> Iterator[NormalizedProduct]:
        limit = client.page_limit
        offset = 0
        while True:
            page = client.get_products_page(root_id, limit=limit, offset=offset)
            items = page.get("list") or []
            if not items:
                break
            enriched = self._enrich_batch(client, items)
            for base in items:
                try:
                    product = self._normalize_item(self._merge_item(base, enriched))
                except Exception as exc:
                    # One malformed product never stops the import.
                    self.stats.failed += 1
                    self.stats.errors.append({
                        "sku": str(base.get("product_code") or base.get("productID") or ""),
                        "error": str(exc),
                    })
                    continue
                if product is not None:
                    yield product
            offset += len(items)
            if len(items) < limit:
                break

    # -------------------------------------------------------- normalization
    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _pick_price(self, item: dict, category_path: str = None) -> int:
        """Pick and calculate the final price in kopecks.

        Priority: price_uah (UAH) -> price (USD, converted via the
        configured rate) -> 0.  Uses the shared markup/pricing service
        scoped to the ``brain`` supplier code.
        """
        price_uah = self._safe_float(item.get("price_uah"))
        price_usd = self._safe_float(item.get("price"))
        return calculate_price(
            price_uah=price_uah if price_uah > 0 else None,
            price_usd=price_usd if price_uah <= 0 and price_usd > 0 else None,
            supplier_code=self.SUPPLIER_CODE,
            category_path=category_path,
        )

    def _pick_old_price(self, item: dict, category_path: str = None) -> Optional[int]:
        """Old/RRP price from recommendable_price (fallback retail_price_uah),
        passed through the same markup logic as the IT-Link RRP price."""
        base_uah = self._safe_float(item.get("price_uah"))
        base_usd = self._safe_float(item.get("price"))
        base = base_uah if base_uah > 0 else base_usd
        rrp = self._safe_float(item.get("recommendable_price"))
        if rrp <= 0:
            rrp = self._safe_float(item.get("retail_price_uah"))
        if rrp <= 0 or base <= 0:
            return None
        multiplier = find_markup_multiplier(
            base_price_uah=base,
            supplier_code=self.SUPPLIER_CODE,
            category_path=category_path,
        )
        return calculate_old_price(source_old_price_uah=rrp, markup=multiplier)

    @staticmethod
    def _stock_qty_positive(item: dict) -> bool:
        """True when any warehouse reports a positive quantity.

        ``available`` is {stockID: qty}; ``stocks`` is a list of warehouse
        IDs with any stock.  Only present for OWN_LOGISTICS_MODE accounts.
        """
        available = item.get("available")
        if isinstance(available, dict):
            for qty in available.values():
                try:
                    if float(qty) > 0:
                        return True
                except (TypeError, ValueError):
                    continue
        stocks = item.get("stocks")
        if isinstance(stocks, (list, tuple)):
            for stock_id in stocks:
                try:
                    if float(stock_id) > 0:
                        return True
                except (TypeError, ValueError):
                    continue
        return False

    def _detect_stock_state(self, item: dict) -> Tuple[bool, bool]:
        """Return ``(in_stock, archived)`` for a product.

        Stock fields are only returned for OWN_LOGISTICS_MODE accounts;
        when they are absent the product is treated as available and the
        archived flag drives visibility.  Archived products stay in the
        feed (so they are never hidden by reconciliation) but are forced
        out-of-stock — the established import lifecycle convention.
        """
        archived = _is_truthy_flag(item.get("is_archive"))
        in_stock = True
        if "stocks" in item or "available" in item:
            in_stock = self._stock_qty_positive(item)
        if archived:
            in_stock = False
            self.stats.archived += 1
        return in_stock, archived

    @staticmethod
    def _collect_images(item: dict) -> List[str]:
        """Collect image URLs: content pictures first, then the base list
        image as fallback.  Order preserved, duplicates removed; only ONE
        base image is used to avoid the same picture at several sizes."""
        urls: List[str] = []
        content_images = item.get("images")
        if isinstance(content_images, list):
            for img in content_images:
                if isinstance(img, dict):
                    url = str(
                        img.get("full_image") or img.get("large_image")
                        or img.get("medium_image") or img.get("small_image") or ""
                    ).strip()
                else:
                    url = str(img).strip()
                if url and url not in urls:
                    urls.append(url)
        if not urls:
            for key in ("full_image", "large_image", "medium_image"):
                url = str(item.get(key) or "").strip()
                if url:
                    urls.append(url)
                    break
        return urls

    @staticmethod
    def _extract_raw_attributes(item: dict) -> List[Tuple[str, str]]:
        """Options from the content endpoint as (name, value) pairs."""
        pairs: List[Tuple[str, str]] = []
        options = item.get("options")
        if not isinstance(options, list):
            return pairs
        for opt in options:
            if not isinstance(opt, dict):
                continue
            name = str(opt.get("OptionName") or opt.get("name") or "").strip()
            value = str(opt.get("ValueName") or opt.get("value") or "").strip()
            if name and value:
                pairs.append((name, value))
        return pairs

    @staticmethod
    def _extract_raw_attributes_with_ids(item: dict) -> List[Tuple[str, str, str, str]]:
        """Options from the content endpoint as (name, value, option_id, value_id).

        Brain identity per taxonomy V2: OptionID = attribute identity,
        ValueID = value identity. FilterID is NEVER attribute identity and
        is deliberately ignored here.
        """
        result: List[Tuple[str, str, str, str]] = []
        options = item.get("options")
        if not isinstance(options, list):
            return result
        for opt in options:
            if not isinstance(opt, dict):
                continue
            name = str(opt.get("OptionName") or opt.get("name") or "").strip()
            value = str(opt.get("ValueName") or opt.get("value") or "").strip()
            opt_id = str(opt.get("OptionID") or opt.get("option_id") or "").strip()
            val_id = str(opt.get("ValueID") or opt.get("value_id") or "").strip()
            if name and value:
                result.append((name, value, opt_id, val_id))
        return result

    def _process_attributes(self, raw_attrs, sku: str = "",
                            category_id: Optional[int] = None) -> List[Tuple[str, str]]:
        processed = []
        for item in raw_attrs:
            # Support both 4-tuples (name, value, opt_id, val_id) and 2-tuples (name, value)
            if isinstance(item, tuple) and len(item) >= 4:
                attr_name, attr_value, attr_ext_id, val_ext_id = item[:4]
            else:
                attr_name, attr_value = item
                attr_ext_id = val_ext_id = None
            result = process_attribute(
                attr_name, attr_value,
                category_id=category_id,
                supplier_attr_external_id=attr_ext_id or None,
                supplier_value_external_id=val_ext_id or None,
            )
            if isinstance(result, tuple) and len(result) == 2:
                processed.append(result)
            elif result == ATTR_SKIP:
                pass
            elif result == ATTR_UNKNOWN_NAME:
                self.stats.record_unknown_attribute(attr_name, sku=sku)
            elif result == ATTR_UNKNOWN_VALUE:
                self.stats.record_unknown_attribute_value(attr_name, attr_value, sku=sku)
        return processed

    def _internal_category_id(self, category_path: str) -> Optional[int]:
        """Cached internal category lookup for category-scoped mappings."""
        if not category_path:
            return None
        if category_path in self._internal_cat_ids:
            return self._internal_cat_ids[category_path]
        cid: Optional[int] = None
        try:
            from app.core.db_connect import managed_cursor
            with managed_cursor() as cur:
                cur.execute("SELECT id FROM categories WHERE name = %s", (category_path,))
                row = cur.fetchone()
                cid = row[0] if row else None
        except Exception:
            cid = None
        self._internal_cat_ids[category_path] = cid
        return cid

    def _normalize_item(self, item: dict) -> Optional[NormalizedProduct]:
        """Normalize one merged BRAIN product into the internal schema.

        Returns None when the product must be skipped (missing SKU/name or
        unmapped category) — those are tracked in stats, not errors.
        """
        product_code = str(item.get("product_code") or "").strip()
        articul = str(item.get("articul") or "").strip()
        supplier_sku = product_code or articul
        if not supplier_sku:
            self.stats.empty_skus += 1
            return None
        sku = self.SKU_PREFIX + supplier_sku

        if sku in self._seen_skus:
            self.stats.duplicate_skus += 1
            return None
        self._seen_skus.add(sku)

        name = str(item.get("name") or "").strip()
        if not name:
            self.stats.skipped += 1
            self.stats.warnings.append(f"BRAIN SKU {sku}: порожня назва товару — пропущено")
            return None

        # Resolve category BEFORE price calculation (established convention).
        # Unmapped categories are skipped, not failed.
        # V2 precedence: VIRTUAL resolves locally through realcat first;
        # then ID-first resolver (supplier_id=3 + external_id, never name);
        # unmapped/EXCLUDE -> record + skip (never silently import).
        raw_cat_id = item.get("categoryID")
        try:
            raw_cat_int = int(raw_cat_id) if raw_cat_id is not None else None
        except (TypeError, ValueError):
            raw_cat_int = None
        real_id = self._resolve_real_category(raw_cat_int)
        cat_name = self._cat_name_by_id.get(real_id, "") if real_id is not None else ""

        # ID-first category resolution: use the resolver if available and it has
        # ID-based mappings.  Falls back to the name-based category_map during
        # the transition period (before ID mappings are populated).
        category_path = None
        resolver = getattr(self, "resolver", None)
        if resolver is not None and real_id is not None:
            try:
                category_path = resolver.resolve_category(external_id=str(real_id))
            except Exception:
                category_path = None
        if category_path is None and cat_name:
            try:
                category_path = resolve_category_path(cat_name, self.category_map, sku=sku)
            except (ValueError, KeyError):
                category_path = None
        if category_path is None:
            self.stats.record_unmapped_category(
                name=cat_name,
                supplier_category_id=str(raw_cat_id) if raw_cat_id is not None else None,
                sku=sku,
            )
            self.stats.skipped += 1
            return None

        price = self._pick_price(item, category_path=category_path)
        old_price = self._pick_old_price(item, category_path=category_path)

        in_stock, _archived = self._detect_stock_state(item)
        brand = self._vendor_name(item)

        images = self._collect_images(item)

        raw_attrs_all = self._extract_raw_attributes_with_ids(item)
        raw_attributes = [(n, v) for n, v, _, _ in raw_attrs_all]
        raw_attributes = _validate_attributes(raw_attributes, self.stats, sku, "BRAIN")
        processed_attrs = self._process_attributes(
            raw_attrs_all, sku=sku,
            category_id=self._internal_category_id(category_path),
        )
        merged_attrs = merge_attributes(processed_attrs)
        merged_list = list(merged_attrs.items())

        seo = generate_product_seo({"Name": name, "Regular price": price, "Brand": brand})

        self.stats.processed += 1
        return NormalizedProduct(
            supplier_sku=supplier_sku,
            sku=sku,
            name=name,
            description=str(item.get("description") or ""),
            short_description=str(item.get("brief_description") or ""),
            price=price,
            old_price=old_price,
            category_path=category_path,
            images=images,
            brand=brand,
            in_stock=in_stock,
            attributes=merged_list,
            raw_attributes=raw_attributes,
            seo_title=seo.get("seo_title", ""),
            seo_description=seo.get("meta_description", ""),
            focus_keyphrase=seo.get("focus_keyphrase", ""),
        )

    # ------------------------------------------------------------------ sync dictionaries
    def sync_dictionaries(self, import_type: str = "full") -> dict:
        """Synchronize the Brain taxonomy mirror + final mappings (idempotent).

        Downloads the category tree (categoryID/parentID/realcat/name),
        mirrors it into supplier_categories (supplier_id=3) preserving
        external_id/parent/realcat, then seeds ONLY the four FINAL approved
        category mappings (1366->126, 1402->60, 1209/1487->NEW media).
        Attribute sync uses OptionID=attr / ValueID=value (FilterID ignored).
        Best-effort: missing credentials/API failure -> zeros, never raises.
        """
        from app.imports import brain_taxonomy as _bt
        stats = {"categories_synced": 0, "attributes_synced": 0, "values_synced": 0}
        try:
            client = self._get_client()
        except Exception:
            return stats
        try:
            categories = client.get_categories()
        except Exception:
            return stats
        try:
            import psycopg2
            import psycopg2.extras
            from app.core.db_connect import DB as _DB
            conn = psycopg2.connect(_DB)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                tax = _bt.sync_brain_taxonomy(categories or [], cur)
                stats["categories_synced"] = int(
                    tax.get("categories_synced", 0) + tax.get("updated", 0)
                )
                _bt.ensure_final_mappings(cur)
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return {"categories_synced": 0, "attributes_synced": 0, "values_synced": 0}
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            return {"categories_synced": 0, "attributes_synced": 0, "values_synced": 0}
        # Attribute/value dictionary sync is intentionally out of scope for
        # the final-4 stage: attributes resolve at import time via OptionID.
        return stats

    # ------------------------------------------------------------------ run
    def run(self, import_type: str = "full") -> ImportStats:
        """Download the catalog structure and start the streaming parser.

        ``import_type`` is accepted for pipeline compatibility (IT-Link and
        DC-Link ignore it the same way); the BRAIN integration always
        streams the full catalog.
        """
        context = self.download_feed()
        # Store the generator — the caller (importer_service) will iterate it
        # product-by-product, so only one page of products is in memory at a time.
        self.stats.products = self.parse_products(context)
        return self.stats














# Content fields merged from the /products/content response into the base
# product dict from the /products list response.
_CONTENT_MERGE_FIELDS = (
    "description", "options", "images", "model", "EAN",
    "width", "height", "depth", "koduktved",
)

# Core product fields that must NEVER be overwritten by supplier attributes
PROTECTED_CORE_FIELDS = frozenset({
    "name", "sku", "supplier_sku", "slug", "brand", "brand_id",
    "price", "old_price", "sale_price", "cost", "purchase_cost",
    "stock_qty", "stock_quantity", "stock_status",
    "barcode", "ean", "supplier_id", "category", "category_id",
    "category_path", "images", "description", "short_description",
    "seo_title", "seo_description", "focus_keyphrase",
    "manufacturer", "vendor", "model", "articul", "article",
    "available", "in_stock", "currency", "weight", "dimensions",
})


class BrainError(RuntimeError):
    """Base class for BRAIN integration errors."""


class BrainConfigError(BrainError):
    """BRAIN credentials are missing / incomplete."""


class BrainAuthError(BrainError):
    """Authentication failed (bad credentials or blocked user)."""


class BrainAPIError(BrainError):
    """BRAIN API returned an error or an unusable response."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code
