"""
Simple in-memory rate limiter for authentication endpoints.

In production with multiple workers/containers, replace this with
a Redis-based implementation.
"""
import time
import logging
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory sliding-window rate limiter.

    Uses client IP as the key. For production with multiple replicas,
    replace with Redis-backed implementation.
    """

    def __init__(self):
        # {key: [(timestamp, count), ...]}
        self._windows: dict[str, list[tuple[float, int]]] = defaultdict(list)

    def _get_key(self, request: Optional[Request], extra: str = "") -> str:
        """Generate a rate limit key from request IP and optional extra context."""
        ip = "unknown"
        if request:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
            else:
                ip = request.client.host if request.client else "unknown"
        return f"{ip}:{extra}"

    def check(
        self,
        key: str,
        max_requests: int = 5,
        window_seconds: int = 60,
        cooldown_seconds: Optional[int] = None,
    ) -> bool:
        """
        Check if a request should be allowed.

        Args:
            key: Rate limit key (usually IP + action).
            max_requests: Maximum requests allowed in the window.
            window_seconds: Time window in seconds.
            cooldown_seconds: If set, enforce a strict cooldown (only 1 request
                              allowed within this period). Overrides max_requests.

        Returns:
            True if allowed, raises HTTPException if blocked.
        """
        now = time.time()
        window = self._windows[key]

        # Clean old entries outside the window
        cutoff = now - max(window_seconds, cooldown_seconds or 0)
        self._windows[key] = [(t, c) for t, c in window if t > cutoff]

        if cooldown_seconds is not None:
            # Strict cooldown: only 1 request allowed in cooldown period
            recent = sum(c for t, c in self._windows[key] if t > now - cooldown_seconds)
            if recent >= 1:
                retry_after = int(cooldown_seconds - (now - self._windows[key][-1][0]))
                logger.warning("Rate limit hit for %s: cooldown %ds", key, retry_after)
                raise HTTPException(
                    status_code=429,
                    detail="Забагато запитів. Спробуйте пізніше.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )

        # Count total requests in the window
        total = sum(c for t, c in self._windows[key] if t > now - window_seconds)
        if total >= max_requests:
            logger.warning("Rate limit hit for %s: %d requests in %ds", key, total, window_seconds)
            raise HTTPException(
                status_code=429,
                detail="Забагато запитів. Спробуйте пізніше.",
                headers={"Retry-After": str(window_seconds)},
            )

        # Record this request
        self._windows[key].append((now, 1))
        return True

    def get_retry_after(self, key: str, cooldown_seconds: int) -> Optional[int]:
        """Get seconds until next allowed request, if currently rate-limited."""
        now = time.time()
        for t, _ in reversed(self._windows.get(key, [])):
            if t > now - cooldown_seconds:
                return int(cooldown_seconds - (now - t))
        return None


# Global rate limiter instance
rate_limiter = RateLimiter()
