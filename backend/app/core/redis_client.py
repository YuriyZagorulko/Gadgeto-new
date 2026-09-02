"""Redis client for the catalog automation (lock + status inspection).

Only the Celery broker/distributed-lock Redis instance is used — do not
introduce a second Redis.
"""
from __future__ import annotations

from typing import Optional

import redis

from app.core.config import settings


def get_redis_client(url: Optional[str] = None) -> redis.Redis:
    """Return a cheap Redis client (connections are lazy).

    Brackets in sentinel-style URLs (redis://host:port/db) must stay quoted;
    a plain `redis://` URL works without any parsing.
    """
    target = (url or settings.CATALOG_SYNC_REDIS_URL or settings.CELERY_BROKER_URL)
    return redis.Redis.from_url(
        target,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )