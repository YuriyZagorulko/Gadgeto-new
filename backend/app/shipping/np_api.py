"""Nova Poshta API integration."""
import os, json, hashlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()
NP_API_KEY = os.getenv("NOVAPOSHTA_API_KEY", "")
NP_API_URL = "https://api.novaposhta.ua/v2.0/json/"

async def np_request(model: str, method: str, **params):
    import httpx
    if not NP_API_KEY:
        raise HTTPException(status_code=400, detail="Nova Poshta API key not configured")
    payload = {
        "apiKey": NP_API_KEY,
        "modelName": model,
        "calledMethod": method,
        "methodProperties": params,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(NP_API_URL, json=payload)
        data = resp.json()
    if not data.get("success"):
        return []
    return data.get("data", [])

@router.get("/shipping/cities")
async def get_cities(page: int = 1, limit: int = 50, search: str = ""):
    try:
        cities = await np_request("Address", "getCities", Page=str(page), Limit=str(limit), FindByString=search)
    except Exception as e:
        return {"items": [], "error": str(e)[:100]}
    return {"items": [{"ref": c["Ref"], "name": c["Description"]} for c in cities]}

@router.get("/shipping/branches")
async def get_branches(city_ref: str = "", search: str = "", page: int = 1):
    try:
        params = {"CityRef": city_ref, "Page": str(page), "Limit": "50"}
        if search: params["FindByString"] = search
        branches = await np_request("Address", "getWarehouses", **params)
    except Exception as e:
        return {"items": [], "error": str(e)[:100]}
    return {"items": [{
        "ref": c["Ref"], "number": c.get("Number", ""), "address": c.get("Description", ""),
        "short_address": c.get("ShortAddress", ""), "phone": c.get("Phone", ""),
        "max_weight": c.get("TotalMaxWeightAllowed", "")
    } for c in branches]}
