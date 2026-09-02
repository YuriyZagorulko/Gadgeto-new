"""Redis-backed distributed lock preventing overlapping catalog syncs.

The lock is acquired once per full catalog sync and released by the final
orchestration callback (or expires via TTL if a worker dies).  Only a single
Redis instance is used (the Celery broker instance).
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.core.redis_client import get_redis_client

logger = logging.getLogger("tasks.lock")

LOCK_KEY = "catalog_sync:lock"
LOCK_META_KEY = "catalog_sync:lock:meta"

_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class CatalogSyncLock:
    """SET NX EX lock with token-based compare-and-delete release."""

    def __init__(self, client=None):
        self._client = client

    def _redis(self):
        if self._client is None:
            self._client = get_redis_client()
        return self._client

    def acquire(self, token: str, timeout: int, run_id: Optional[int] = None) -> bool:
        r = self._redis()
        try:
            acquired = bool(r.set(LOCK_KEY, token, nx=True, ex=timeout))
        except Exception as exc:  # Redis down → fail closed, never risk overlap
            logger.error("Redis unavailable while acquiring catalog sync lock: %s", exc)
            return False
        if acquired:
            try:
                r.hset(LOCK_META_KEY, mapping={
                    "token": token,
                    "run_id": str(run_id or ""),
                })
                r.expire(LOCK_META_KEY, timeout)
            except Exception:
                pass
        return acquired

    def release(self, token: str) -> bool:
        r = self._redis()
        try:
            try:
                deleted = bool(r.eval(_RELEASE_LUA, 1, LOCK_KEY, token))
            except Exception:
                # Fallback when Lua EVAL is unavailable (fakeredis, some proxies)
                actual = r.get(LOCK_KEY)
                if actual == token:
                    deleted = bool(r.delete(LOCK_KEY))
                else:
                    deleted = False
        except Exception as exc:
            logger.warning("Could not release catalog sync lock: %s", exc)
            return False
        if deleted:
            try:
                r.delete(LOCK_META_KEY)
            except Exception:
                pass
        return deleted

    def peek(self) -> dict:
        """Inspect the lock without modifying it (used by the admin status API)."""
        r = self._redis()
        try:
            token = r.get(LOCK_KEY)
            ttl = r.ttl(LOCK_KEY)
            meta = r.hgetall(LOCK_META_KEY) or {}
        except Exception as exc:
            return {"locked": None, "available": False, "error": str(exc)}
        return {
            "locked": bool(token),
            "token": token,
            "ttl": int(ttl) if ttl is not None and ttl >= 0 else None,
            "run_id": meta.get("run_id") or None,
            "available": True,
        }


def new_lock_token() -> str:
    return uuid.uuid4().hex