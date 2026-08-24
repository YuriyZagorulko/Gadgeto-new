"""
Configuration for the IT-Link price list downloader.
Uses Gadgeto-new settings from app.core.config.
"""

import os
import uuid
from pathlib import Path

from app.core.config import settings as core_settings


class Settings:
    """IT-Link downloader settings, adapted from Gadgeto-new config."""

    def __init__(self) -> None:
        self.username: str = core_settings.SUPPLIER_ITLINK_USERNAME
        self.password: str = core_settings.SUPPLIER_ITLINK_PASSWORD
        self.price_id: str = core_settings.SUPPLIER_ITLINK_PRICE_ID
        self.customer_id: str = core_settings.SUPPLIER_ITLINK_CUSTOMER_ID
        self.headless: bool = True
        # Unique run identifier so concurrent imports never clash
        self._run_id: str = uuid.uuid4().hex[:12]

    @property
    def base_url(self) -> str:
        return "https://it-link.ua"

    @property
    def price_url(self) -> str:
        return (
            f"https://it-link.ua/api/v1.0/price"
            f"?id={self.price_id}&cid={self.customer_id}"
        )

    @property
    def target_file_path(self) -> Path:
        """Path to save the downloaded XML (unique per run)."""
        feeds_dir = core_settings.SUPPLIER_FEEDS_DIR or "/data/feeds"
        return Path(feeds_dir) / "itlink" / f"itlink_{self._run_id}.yml"


settings = Settings()
