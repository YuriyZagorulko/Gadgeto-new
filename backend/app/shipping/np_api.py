"""Nova Poshta API integration (public delivery reference data).

Exposes city / warehouse / street lookups for the storefront checkout:
  GET /api/v1/shipping/cities?page=&limit=&search=
  GET /api/v1/shipping/branches?city_ref=&search=&page=
  GET /api/v1/shipping/streets?city_ref=&search=&page=   (courier delivery)

Both endpoints return `{"items": [...], "error": "<msg>"}`; `error` is an
empty string on success. No real Nova Poshta call happens without
NOVAPOSHTA_API_KEY (an error message is returned instead).
"""
from typing import List, Optional, Tuple

import httpx
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()

# NP caps: FindByString works from 1 char; Limit max 500 per docs.
_MAX_LIMIT = 500
_MAX_SEARCH_LEN = 100


async def np_request(model: str, method: str, **params) -> Tuple[List[dict], str]:
    """Call the Nova Poshta JSON API.

    Returns:
        (items, error) — `items` is the NP `data` list (possibly empty),
        `error` is "" on success or a human-readable message. A missing
        API key, network failure, or an NP-level error never raises; the
        caller just gets an empty item list plus the message.
    """
    if not settings.NOVAPOSHTA_API_KEY:
        return [], "Nova Poshta API key not configured"

    payload = {
        "apiKey": settings.NOVAPOSHTA_API_KEY,
        "modelName": model,
        "calledMethod": method,
        "methodProperties": params,
    }
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=10.0),
        ) as client:
            resp = await client.post(settings.NOVAPOSHTA_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return [], "Nova Poshta request timed out"
    except (httpx.HTTPError, ValueError) as exc:
        return [], f"Nova Poshta request failed: {exc}"

    if not data.get("success"):
        errors = data.get("errors") or []
        message = "; ".join(str(e) for e in errors) or "Nova Poshta returned an error"
        return [], message
    return data.get("data") or [], ""


@router.get("/shipping/cities")
async def get_cities(page: int = 1, limit: int = 50, search: str = ""):
    items, error = await np_request(
        "Address",
        "getCities",
        Page=str(max(1, page)),
        Limit=str(min(max(1, limit), _MAX_LIMIT)),
        FindByString=search.strip()[:_MAX_SEARCH_LEN],
    )
    return {
        "items": [{
            "ref": c.get("Ref", ""),
            "name": c.get("Description", ""),
            "area": c.get("AreaDescription", ""),
            "region": c.get("RegionDescription", ""),
        } for c in items],
        "error": error,
    }


@router.get("/shipping/branches")
async def get_branches(city_ref: str = "", search: str = "", page: int = 1,
                       limit: int = 50):
    if not city_ref.strip():
        return {"items": [], "error": ""}
    items, error = await np_request(
        "Address",
        "getWarehouses",
        CityRef=city_ref.strip()[:100],
        Page=str(max(1, page)),
        Limit=str(min(max(1, limit), _MAX_LIMIT)),
        FindByString=search.strip()[:_MAX_SEARCH_LEN],
    )
    return {
        "items": [{
            "ref": c.get("Ref", ""),
            "number": c.get("Number", ""),
            "address": c.get("Description", ""),
            "short_address": c.get("ShortAddress", ""),
            "phone": c.get("Phone", ""),
            "max_weight": c.get("TotalMaxWeightAllowed", ""),
        } for c in items],
        "error": error,
    }


@router.get("/shipping/streets")
async def get_streets(city_ref: str = "", search: str = "", page: int = 1,
                      limit: int = 50):
    """Street search within a city — used for NP courier delivery addresses."""
    if not city_ref.strip():
        return {"items": [], "error": ""}
    items, error = await np_request(
        "Address",
        "getStreet",
        CityRef=city_ref.strip()[:100],
        FindByString=search.strip()[:_MAX_SEARCH_LEN],
        Page=str(max(1, page)),
        Limit=str(min(max(1, limit), _MAX_LIMIT)),
    )
    return {
        "items": [{
            "ref": s.get("Ref", ""),
            "name": s.get("Description", ""),
            "street_type": s.get("StreetsType", ""),
        } for s in items],
        "error": error,
    }
