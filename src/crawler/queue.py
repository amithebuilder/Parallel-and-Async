"""Day 3: Crawler queue, concurrency management, URL filtering."""

import asyncio
import heapq
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Queue item
# ------------------------------------------------------------------

@dataclass(order=True)
class _QueueItem:
    priority: int
    insertion_order: int
    url: str = field(compare=False)
    depth: int = field(compare=False)


# ------------------------------------------------------------------
# CrawlerQueue
# ------------------------------------------------------------------

class CrawlerQueue:
    """Priority queue for URLs with depth tracking and deduplication.

    Lower priority numbers are processed first.
    """

    def __init__(self):
        self._heap: list[_QueueItem] = []
        self._counter = 0
        self._pending: set[str] = set()
        self._processed: set[str] = set()
        self._failed: dict[str, str] = {}
        self._depth_map: dict[str, int] = {}  # url -> depth

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def processed_count(self) -> int:
        return len(self._processed)

    @property
    def failed_count(self) -> int:
        return len(self._failed)

    def add_url(self, url: str, priority: int = 0, depth: int = 0) -> bool:
        """Add a URL to the queue. Returns False if already seen."""
        if url in self._pending or url in self._processed or url in self._failed:
            return False
        self._pending.add(url)
        self._depth_map[url] = depth
        item = _QueueItem(
            priority=priority,
            insertion_order=self._counter,
            url=url,
            depth=depth,
        )
        self._counter += 1
        heapq.heappush(self._heap, item)
        return True

    async def get_next(self) -> str | None:
        """Pop and return the next URL to process, or None if the queue is empty."""
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.url in self._pending:
                return item.url
        return None

    def get_depth(self, url: str) -> int:
        """Return the crawl depth recorded for *url* (0 if not tracked)."""
        return self._depth_map.get(url, 0)

    def mark_processed(self, url: str) -> None:
        self._pending.discard(url)
        self._processed.add(url)

    def mark_failed(self, url: str, error: str) -> None:
        self._pending.discard(url)
        self._failed[url] = error

    def is_seen(self, url: str) -> bool:
        return url in self._pending or url in self._processed or url in self._failed

    def get_stats(self) -> dict:
        return {
            "pending": self.pending_count,
            "processed": self.processed_count,
            "failed": self.failed_count,
            "total_seen": self.pending_count + self.processed_count + self.failed_count,
        }


# ------------------------------------------------------------------
# Semaphore manager (per-domain + global)
# ------------------------------------------------------------------

class SemaphoreManager:
    """Per-domain and global concurrency control."""

    def __init__(self, global_limit: int = 10, per_domain_limit: int = 3):
        self._global = asyncio.Semaphore(global_limit)
        self._per_domain_limit = per_domain_limit
        self._domain_semaphores: dict[str, asyncio.Semaphore] = {}
        self._active: int = 0

    def _get_domain_sem(self, domain: str) -> asyncio.Semaphore:
        if domain not in self._domain_semaphores:
            self._domain_semaphores[domain] = asyncio.Semaphore(self._per_domain_limit)
        return self._domain_semaphores[domain]

    async def acquire(self, url: str) -> None:
        domain = urlparse(url).netloc
        await self._global.acquire()
        await self._get_domain_sem(domain).acquire()
        self._active += 1

    def release(self, url: str) -> None:
        domain = urlparse(url).netloc
        self._get_domain_sem(domain).release()
        self._global.release()
        self._active -= 1

    @property
    def active_count(self) -> int:
        return self._active


# ------------------------------------------------------------------
# URL filter
# ------------------------------------------------------------------

class URLFilter:
    """Filter URLs by domain, depth, and regex patterns."""

    def __init__(
        self,
        same_domain_only: bool = False,
        allowed_domains: set[str] | None = None,
        max_depth: int = 10,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        self.same_domain_only = same_domain_only
        self.allowed_domains: set[str] = allowed_domains or set()
        self.max_depth = max_depth
        self._include_re = [re.compile(p) for p in (include_patterns or [])]
        self._exclude_re = [re.compile(p) for p in (exclude_patterns or [])]

    def accept(self, url: str, depth: int) -> bool:
        if depth > self.max_depth:
            return False
        parsed = urlparse(url)
        domain = parsed.netloc
        if self.same_domain_only and self.allowed_domains and domain not in self.allowed_domains:
            return False
        if self._exclude_re and any(r.search(url) for r in self._exclude_re):
            return False
        if self._include_re and not any(r.search(url) for r in self._include_re):
            return False
        return True


# ------------------------------------------------------------------
# Progress tracker
# ------------------------------------------------------------------

class ProgressTracker:
    """Track crawling progress and print real-time stats."""

    def __init__(self):
        self._start_time = time.monotonic()
        self._pages_done = 0
        self._errors = 0

    def record_success(self) -> None:
        self._pages_done += 1

    def record_error(self) -> None:
        self._errors += 1

    def get_stats(self) -> dict:
        elapsed = time.monotonic() - self._start_time
        speed = self._pages_done / elapsed if elapsed > 0 else 0.0
        return {
            "pages_done": self._pages_done,
            "errors": self._errors,
            "elapsed_sec": round(elapsed, 2),
            "pages_per_sec": round(speed, 2),
        }

    def log_progress(self, queue_pending: int = 0) -> None:
        s = self.get_stats()
        logger.info(
            "Progress: done=%d  errors=%d  pending=%d  speed=%.1f p/s  elapsed=%.1fs",
            s["pages_done"],
            s["errors"],
            queue_pending,
            s["pages_per_sec"],
            s["elapsed_sec"],
        )
