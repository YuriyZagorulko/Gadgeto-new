"""
Application configuration using Pydantic settings.
All sensitive values must come from environment variables.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # The shared root .env also carries frontend-only keys (NEXT_PUBLIC_*)
        # consumed by the Next.js builds.  They must not crash backend config
        # loading for host-side tooling (alembic, scripts).
        extra="ignore",
    )

    # Application
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(default="change-me-in-production")

    # Database
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://gadgeto:gadgeto@localhost:5432/gadgeto"
    )

    # CORS
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])

    # Frontend
    FRONTEND_URL: str = Field(default="http://localhost:3000")

    # LiqPay
    LIQPAY_PUBLIC_KEY: str = Field(default="")
    LIQPAY_PRIVATE_KEY: str = Field(default="")
    LIQPAY_TEST_MODE: bool = Field(default=True)
    LIQPAY_TEST_PUBLIC_KEY: str = Field(default="")
    LIQPAY_TEST_PRIVATE_KEY: str = Field(default="")

    # Nova Poshta
    NOVAPOSHTA_API_KEY: str = Field(default="")
    NOVAPOSHTA_API_URL: str = Field(
        default="https://api.novaposhta.ua/v2.0/json/"
    )

    # Email (Brevo)
    BREVO_API_KEY: str = Field(default="")
    BREVO_SENDER_EMAIL: str = Field(default="noreply@gadgeto.com.ua")
    BREVO_SENDER_NAME: str = Field(default="Gadgeto")
    SMTP_HOST: str = Field(default="")
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM: str = Field(default="noreply@gadgeto.com.ua")

    # Media
    MEDIA_DIR: str = Field(default="./media")
    MEDIA_BASE_URL: str = Field(default="/media")

    # Supplier credentials (never commit real values)
    SUPPLIER_ITLINK_USERNAME: str = Field(default="")
    SUPPLIER_ITLINK_PASSWORD: str = Field(default="")
    SUPPLIER_ITLINK_PRICE_ID: str = Field(default="")
    SUPPLIER_ITLINK_CUSTOMER_ID: str = Field(default="")
    SUPPLIER_DCLINK_LOGIN: str = Field(default="")
    SUPPLIER_DCLINK_PASSWORD: str = Field(default="")

    # Rozetka Marketplace API
    ROZETKA_API_URL: str = Field(default="https://api-seller.rozetka.com.ua")
    ROZETKA_SELLER_USERNAME: str = Field(default="")
    ROZETKA_SELLER_PASSWORD: str = Field(default="")

    # Supplier feeds (temporary working storage path)
    SUPPLIER_FEEDS_DIR: str = Field(default="/data/feeds")

    # ── Celery / Redis (catalog automation) ──────────────────────────────────
    # Broker/backend URLs. In docker-compose they point at the `redis` service.
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")
    # Lock/status inspection uses the same Redis instance.
    CATALOG_SYNC_REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ── Catalog automation (Celery Beat orchestrated) ────────────────────────
    # Master switch. Beat always fires the scheduled task; the task itself
    # checks this flag (env default, overridable at runtime via the `settings`
    # DB table through the admin "Автоматизація" enable/disable API).
    CATALOG_SYNC_ENABLED: bool = Field(default=False)
    # Beat cadence: run the full catalog sync every N hours (crontab hour=*/N).
    CATALOG_SYNC_INTERVAL_HOURS: int = Field(default=4, ge=1)
    # Anchor hour (0-23) for the cadence. anchor=2, interval=4 → 02/06/10/14/18/22.
    CATALOG_SYNC_ANCHOR_HOUR: int = Field(default=0, ge=0, le=23)
    # Distributed lock TTL (seconds) — must comfortably exceed the longest
    # realistic sync so overlapping runs are blocked, not the lock.
    CATALOG_SYNC_LOCK_TIMEOUT: int = Field(default=6 * 3600, ge=60)
    # Max automatic retries for transient supplier/export failures.
    CATALOG_SYNC_MAX_RETRIES: int = Field(default=3, ge=0)
    # Base countdown (seconds) for exponential backoff: 60, 120, 240, ...
    CATALOG_SYNC_RETRY_BACKOFF: int = Field(default=60, ge=1)
    # Optional public base URL baked into exported image URLs. When empty the
    # existing manual-export behaviour is preserved (URLs passed through).
    CATALOG_SYNC_PUBLIC_BASE_URL: str = Field(default="")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
