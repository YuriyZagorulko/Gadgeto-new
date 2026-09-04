"""
LiqPay payment integration.
"""

import hashlib
import json
from typing import Optional
from base64 import b64encode

import aiohttp

from app.core.config import settings


class LiqPayClient:
    """LiqPay API client."""

    def __init__(self):
        self.public_key = (
            settings.LIQPAY_TEST_PUBLIC_KEY
            if settings.LIQPAY_TEST_MODE
            else settings.LIQPAY_PUBLIC_KEY
        )
        self.private_key = (
            settings.LIQPAY_TEST_PRIVATE_KEY
            if settings.LIQPAY_TEST_MODE
            else settings.LIQPAY_PRIVATE_KEY
        )

    def _to_base64(self, data: dict) -> str:
        """Base64-encode JSON payload (LiqPay data field)."""
        raw = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return b64encode(raw.encode('utf-8')).decode('ascii')

    def _sign(self, base64_data: str) -> str:
        """Build LiqPay signature: base64(sha1(private_key + data + private_key))."""
        str_to_sign = self.private_key + base64_data + self.private_key
        return b64encode(
            hashlib.sha1(str_to_sign.encode('utf-8')).digest()
        ).decode('ascii')

    async def create_payment(
        self,
        order_id: str,
        amount: int,
        currency: str = "UAH",
        description: str = "Order payment",
        result_url: Optional[str] = None,
        server_url: Optional[str] = None,
    ) -> dict:
        """
        Create a payment request.

        Args:
            order_id: Order ID in your system
            amount: Amount in kopecks
            currency: Currency code
            description: Payment description
            result_url: URL to redirect after payment
            server_url: URL for server-to-server callback

        Returns:
            LiqPay payment data
        """
        data = {
            "public_key": self.public_key,
            "action": "pay",
            "amount": amount,
            "currency": currency,
            "description": description,
            "order_id": order_id,
            "version": "3",
        }

        if result_url:
            data["result_url"] = result_url

        if server_url:
            data["server_url"] = server_url

        data_b64 = self._to_base64(data)
        payload = {
            "data": data_b64,
            "signature": self._sign(data_b64),
        }

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(
                "https://www.liqpay.ua/api/3/checkout",
                json=payload,
            ) as response:
                result = await response.json()
                return result

    def verify_callback(self, data_b64: str, signature: str) -> bool:
        """Verify LiqPay callback signature."""
        return signature == self._sign(data_b64)

    async def get_payment_status(self, order_id: str) -> dict:
        """Get payment status."""
        data = {
            "public_key": self.public_key,
            "action": "status",
            "order_id": order_id,
            "version": "3",
        }
        data_b64 = self._to_base64(data)
        payload = {
            "data": data_b64,
            "signature": self._sign(data_b64),
        }

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(
                "https://www.liqpay.ua/api/3/request",
                json=payload,
            ) as response:
                result = await response.json()
                return result
