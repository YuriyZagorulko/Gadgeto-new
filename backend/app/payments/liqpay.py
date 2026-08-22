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

    def _sign(self, data: dict) -> str:
        """Sign request data."""
        str_to_sign = self.private_key + json.dumps(data, separators=(',', ':'))
        signature = b64encode(hashlib.sha1(str_to_sign.encode('utf-8')).digest()).decode('ascii')
        return signature

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

        data["signature"] = self._sign(data)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.liqpay.ua/api/3/checkout",
                json=data,
            ) as response:
                result = await response.json()
                return result

    async def verify_callback(self, data: dict, signature: str) -> bool:
        """Verify LiqPay callback signature."""
        expected_signature = self._sign(data)
        return signature == expected_signature

    async def get_payment_status(self, order_id: str) -> dict:
        """Get payment status."""
        data = {
            "public_key": self.public_key,
            "action": "status",
            "order_id": order_id,
            "version": "3",
        }
        data["signature"] = self._sign(data)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.liqpay.ua/api/3/request",
                json=data,
            ) as response:
                result = await response.json()
                return result
