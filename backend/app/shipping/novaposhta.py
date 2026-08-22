"""
Nova Poshta shipping integration.
"""

import json
from typing import List, Optional, Dict
from functools import lru_cache

import aiohttp

from app.core.config import settings


class NovaPoshtaClient:
    """Nova Poshta API client."""

    def __init__(self):
        self.api_key = settings.NOVAPOSHTA_API_KEY
        self.api_url = settings.NOVAPOSHTA_API_URL
        self._city_cache: Optional[List[dict]] = None
        self._warehouse_cache: Dict[str, List[dict]] = {}

    async def _request(self, model: str, method: str, **params) -> dict:
        """Make API request to Nova Poshta."""
        if not self.api_key:
            raise ValueError("Nova Poshta API key not configured")

        payload = {
            "apiKey": self.api_key,
            "modelName": model,
            "calledMethod": method,
            "methodProperties": params,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.api_url,
                json=payload,
            ) as response:
                result = await response.json()
                return result

    async def get_cities(self) -> List[dict]:
        """Get list of all cities."""
        if self._city_cache is not None:
            return self._city_cache

        result = await self._request(
            "Address",
            "getCities",
            limit="500",
            page="1",
        )

        if result.get("success"):
            self._city_cache = result["data"]
            return self._city_cache

        return []

    async def get_warehouses(self, city_ref: str) -> List[dict]:
        """Get warehouses for a city."""
        if city_ref not in self._warehouse_cache:
            result = await self._request(
                "Address",
                "getWarehouses",
                cityRef=city_ref,
                limit="100",
            )

            if result.get("success"):
                self._warehouse_cache[city_ref] = result["data"]
            else:
                self._warehouse_cache[city_ref] = []

        return self._warehouse_cache.get(city_ref, [])

    async def get_warehouse_by_number(
        self,
        city_ref: str,
        warehouse_number: str,
    ) -> Optional[dict]:
        """Get warehouse by city and warehouse number."""
        warehouses = await self.get_warehouses(city_ref)
        for wh in warehouses:
            if wh.get("Number") == warehouse_number:
                return wh
        return None

    @staticmethod
    def parse_warehouse_address(address: str) -> dict:
        """
        Parse Nova Poshta warehouse address.
        Format: "Відділення №9 (до 30 кг на одне місце ): просп. Лесі Українки, 63А  Дніпро"
        """
        # Simplified parsing - in production, use more robust parsing
        parts = address.split("Відділення №")
        if len(parts) < 2:
            return {"number": "", "address": address, "city": ""}

        rest = parts[1]
        number_end = rest.find(" ")
        if number_end == -1:
            number_end = rest.find("(")
            if number_end == -1:
                number_end = len(rest)

        number = rest[:number_end].strip()

        return {
            "number": number,
            "address": address,
            "city": "",
        }
