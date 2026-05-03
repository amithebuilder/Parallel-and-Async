"""Day 5: Error classification, retry strategy with exponential backoff, circuit breaker."""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine

import aiohttp

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Error hierarchy
# ------------------------------------------------------------------

class CrawlerError(Exception):
    """Base exception for the crawler."""


class TransientError(CrawlerError):
    """Temporary error — worth retrying (timeouts, 503, 429)."""


class PermanentError(CrawlerError):
    """Permanent error — do not retry (404, 403)."""


class NetworkError(CrawlerError):
    """Network-level error — worth retrying (DNS, connection refused)."""


class ParseError(CrawlerError):
    """Error during HTML/data parsing."""


# ------------------------------------------------------------------
# Error classifier
# ------------------------------------------------------------------

def classify_error(exc: Exception) -> CrawlerError:
    """Wrap a raw exception into the appropriate CrawlerError subclass."""
    if isinstance(exc, CrawlerError):
        return exc
    if isinstance(exc, asyncio.TimeoutError):
        return TransientError(f"Timeout: {exc}")
    if isinstance(exc, aiohttp.ClientResponseError):
        status = exc.status
        if status == 429:
            return TransientError(f"429 Too Many Requests")
        if status in (502, 503, 504):
            return TransientError(f"HTTP {status}")
        if status == 500:
            return TransientError(f"HTTP 500 Server Error")
        # 4xx family (except 429) — permanent
        return PermanentError(f"HTTP {status} {exc.message}")
    if isinstance(exc, aiohttp.ClientError):
        return NetworkError(str(exc))
    return CrawlerError(str(exc))


# ------------------------------------------------------------------
# Retry strategy
# ------------------------------------------------------------------

class RetryStrategy:
    """Execute coroutines with retries, exponential backoff, and detailed logging.

    Args:
        max_retries: Maximum retry attempts.
        backoff_factor: Multiplier for exponential delay.
        initial_delay: Delay before first retry.
        max_delay: Cap on the backoff delay.
        retry_on: Error types that trigger a retry.
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        retry_on: tuple[type[CrawlerError], ...] | None = None,
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.retry_on = retry_on or (TransientError, NetworkError)

        # Statistics
        self._stats: dict[str, int] = defaultdict(int)
        self._successful_retries = 0
        self._total_retry_time = 0.0

    async def execute_with_retry(
        self,
        coro_factory: Callable[..., Coroutine],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Call *coro_factory(*args, **kwargs)* with automatic retries.

        Returns the coroutine result on success.
        Raises the classified CrawlerError on final failure.
        """
        last_error: CrawlerError | None = None

        for attempt in range(1 + self.max_retries):
            try:
                result = await coro_factory(*args, **kwargs)
                if attempt > 0:
                    self._successful_retries += 1
                    logger.info("Retry succeeded on attempt %d", attempt + 1)
                return result
            except Exception as raw_exc:
                classified = classify_error(raw_exc)
                last_error = classified
                error_type = type(classified).__name__
                self._stats[error_type] += 1

                if not isinstance(classified, self.retry_on):
                    logger.warning(
                        "Non-retryable %s (attempt %d/%d): %s",
                        error_type,
                        attempt + 1,
                        1 + self.max_retries,
                        classified,
                    )
                    raise classified from raw_exc

                if attempt < self.max_retries:
                    delay = min(
                        self.initial_delay * (self.backoff_factor ** attempt),
                        self.max_delay,
                    )
                    logger.warning(
                        "%s (attempt %d/%d) — retrying in %.1fs: %s",
                        error_type,
                        attempt + 1,
                        1 + self.max_retries,
                        delay,
                        classified,
                    )
                    self._total_retry_time += delay
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "%s — all %d attempts exhausted: %s",
                        error_type,
                        1 + self.max_retries,
                        classified,
                    )

        raise last_error  # type: ignore[misc]

    def get_stats(self) -> dict:
        return {
            "errors_by_type": dict(self._stats),
            "successful_retries": self._successful_retries,
            "total_retry_wait_sec": round(self._total_retry_time, 2),
        }


# ------------------------------------------------------------------
# Simple circuit breaker
# ------------------------------------------------------------------

class CircuitBreaker:
    """Per-domain circuit breaker.

    Opens (blocks requests) when a domain produces *threshold* errors
    within *window* seconds. Stays open for *recovery_time* seconds,
    then half-opens to let a single probe through.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, threshold: int = 5, window: float = 60.0, recovery_time: float = 30.0):
        self.threshold = threshold
        self.window = window
        self.recovery_time = recovery_time
        self._errors: dict[str, list[float]] = defaultdict(list)
        self._state: dict[str, str] = {}
        self._opened_at: dict[str, float] = {}

    def _prune(self, domain: str) -> None:
        cutoff = time.monotonic() - self.window
        self._errors[domain] = [t for t in self._errors[domain] if t > cutoff]

    def record_error(self, domain: str) -> None:
        now = time.monotonic()
        self._errors[domain].append(now)
        self._prune(domain)
        if len(self._errors[domain]) >= self.threshold:
            self._state[domain] = self.OPEN
            self._opened_at[domain] = now
            logger.warning("Circuit OPEN for %s", domain)

    def record_success(self, domain: str) -> None:
        state = self._state.get(domain, self.CLOSED)
        if state == self.HALF_OPEN:
            self._state[domain] = self.CLOSED
            self._errors[domain].clear()
            logger.info("Circuit CLOSED for %s (probe succeeded)", domain)

    def can_request(self, domain: str) -> bool:
        state = self._state.get(domain, self.CLOSED)
        if state == self.CLOSED:
            return True
        if state == self.OPEN:
            elapsed = time.monotonic() - self._opened_at.get(domain, 0)
            if elapsed >= self.recovery_time:
                self._state[domain] = self.HALF_OPEN
                logger.info("Circuit HALF-OPEN for %s (allowing probe)", domain)
                return True
            return False
        # HALF_OPEN — allow one probe
        return True

    def get_state(self, domain: str) -> str:
        return self._state.get(domain, self.CLOSED)
