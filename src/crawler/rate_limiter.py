"""Day 4: Rate limiting with per-domain control and jitter."""

import asyncio
import logging
import random
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket–style rate limiter with per-domain or global control.

    Args:
        requests_per_second: Maximum request rate.
        per_domain: If True, each domain has its own rate limit.
        min_delay: Minimum seconds between any two requests to the same target.
        jitter: Maximum random extra delay added to each wait.
    """

    def __init__(
        self,
        requests_per_second: float = 1.0,
        per_domain: bool = True,
        min_delay: float = 0.0,
        jitter: float = 0.0,
    ):
        self._interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.0
        self._per_domain = per_domain
        self._min_delay = min_delay
        self._jitter = jitter
        self._last_request: dict[str, float] = {}  # domain -> monotonic timestamp
        self._locks: dict[str, asyncio.Lock] = {}
        self._total_waits = 0
        self._total_wait_time = 0.0

    def _key(self, url: str) -> str:
        if self._per_domain:
            return urlparse(url).netloc
        return "__global__"

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def acquire(self, url: str) -> float:
        """Wait until a request to *url* is allowed. Returns actual wait time."""
        key = self._key(url)
        lock = self._get_lock(key)

        async with lock:
            now = time.monotonic()
            last = self._last_request.get(key, 0.0)
            required_gap = max(self._interval, self._min_delay)
            wait = max(0.0, last + required_gap - now)
            if self._jitter > 0:
                wait += random.uniform(0, self._jitter)
            if wait > 0:
                logger.debug("Rate limit: waiting %.2fs for %s", wait, key)
                await asyncio.sleep(wait)
                self._total_waits += 1
                self._total_wait_time += wait
            self._last_request[key] = time.monotonic()
            return wait

    def get_stats(self) -> dict:
        avg = self._total_wait_time / self._total_waits if self._total_waits else 0.0
        return {
            "total_waits": self._total_waits,
            "total_wait_time": round(self._total_wait_time, 2),
            "avg_wait_time": round(avg, 3),
        }
