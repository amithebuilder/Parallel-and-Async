"""Day 7: AdvancedCrawler — full integration of all components."""

import asyncio
import logging
import time
from urllib.parse import urlparse

import aiohttp

from crawler.client import AsyncCrawler
from crawler.config import CrawlerConfig
from crawler.parser import HTMLParser
from crawler.queue import CrawlerQueue, SemaphoreManager, URLFilter, ProgressTracker
from crawler.rate_limiter import RateLimiter
from crawler.retry import (
    RetryStrategy,
    CircuitBreaker,
    classify_error,
    PermanentError,
)
from crawler.robots import RobotsParser
from crawler.sitemap import SitemapParser
from crawler.stats import CrawlerStats
from crawler.storage import DataStorage, JSONStorage, CSVStorage, SQLiteStorage

logger = logging.getLogger(__name__)


class AdvancedCrawler:
    """Full-featured async web crawler integrating all Day 1–7 components.

    Can be constructed directly or via :meth:`from_config`.
    """

    def __init__(
        self,
        start_urls: list[str] | None = None,
        max_pages: int = 100,
        max_depth: int = 3,
        max_concurrent: int = 10,
        per_domain_limit: int = 3,
        requests_per_second: float = 2.0,
        min_delay: float = 0.0,
        jitter: float = 0.0,
        respect_robots: bool = True,
        user_agent: str = "AsyncCrawler/1.0",
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        same_domain_only: bool = True,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        storage: DataStorage | None = None,
        use_sitemap: bool = False,
        timeout_connect: float = 10.0,
        timeout_read: float = 30.0,
        timeout_total: float = 60.0,
    ):
        self._start_urls = start_urls or []
        self._max_pages = max_pages
        self._use_sitemap = use_sitemap

        # HTTP client
        self._client = AsyncCrawler(
            max_concurrent=max_concurrent,
            timeout_connect=timeout_connect,
            timeout_read=timeout_read,
            timeout_total=timeout_total,
            headers={"User-Agent": user_agent},
        )

        # Parser
        self._parser = HTMLParser()

        # Queue & concurrency
        self._queue = CrawlerQueue()
        self._semaphore = SemaphoreManager(
            global_limit=max_concurrent,
            per_domain_limit=per_domain_limit,
        )

        # URL filter
        allowed = {urlparse(u).netloc for u in self._start_urls} if same_domain_only else None
        self._url_filter = URLFilter(
            same_domain_only=same_domain_only,
            allowed_domains=allowed,
            max_depth=max_depth,
            include_patterns=include_patterns or [],
            exclude_patterns=exclude_patterns or [],
        )

        # Rate limiting
        self._rate_limiter = RateLimiter(
            requests_per_second=requests_per_second,
            per_domain=True,
            min_delay=min_delay,
            jitter=jitter,
        )

        # Robots.txt
        self._respect_robots = respect_robots
        self._user_agent = user_agent
        self._robots: RobotsParser | None = None  # created once we have a session

        # Retry & circuit breaker
        self._retry = RetryStrategy(
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )
        self._circuit = CircuitBreaker()

        # Storage
        self._storage = storage

        # Stats & progress
        self._stats = CrawlerStats()
        self._progress = ProgressTracker()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config_path: str) -> "AdvancedCrawler":
        cfg = CrawlerConfig.from_file(config_path)
        storages: list[DataStorage] = []
        if cfg.output_json:
            storages.append(JSONStorage(cfg.output_json))
        if cfg.output_csv:
            storages.append(CSVStorage(cfg.output_csv))
        if cfg.output_sqlite:
            storages.append(SQLiteStorage(cfg.output_sqlite))
        storage = storages[0] if len(storages) == 1 else (MultiStorage(storages) if storages else None)

        return cls(
            start_urls=cfg.start_urls,
            max_pages=cfg.max_pages,
            max_depth=cfg.max_depth,
            max_concurrent=cfg.max_concurrent,
            per_domain_limit=cfg.per_domain_limit,
            requests_per_second=cfg.requests_per_second,
            min_delay=cfg.min_delay,
            jitter=cfg.jitter,
            respect_robots=cfg.respect_robots,
            user_agent=cfg.user_agent,
            max_retries=cfg.max_retries,
            backoff_factor=cfg.backoff_factor,
            same_domain_only=cfg.same_domain_only,
            include_patterns=cfg.include_patterns,
            exclude_patterns=cfg.exclude_patterns,
            storage=storage,
            use_sitemap=cfg.use_sitemap,
            timeout_connect=cfg.timeout_connect,
            timeout_read=cfg.timeout_read,
            timeout_total=cfg.timeout_total,
        )

    # ------------------------------------------------------------------
    # Main crawl loop
    # ------------------------------------------------------------------

    async def crawl(
        self,
        start_urls: list[str] | None = None,
        max_pages: int | None = None,
    ) -> list[dict]:
        """Run the crawl and return all collected page data."""
        urls = start_urls or self._start_urls
        max_p = max_pages or self._max_pages
        if not urls:
            logger.error("No start URLs provided")
            return []

        # If same_domain_only and new start_urls, update filter
        if start_urls:
            for u in urls:
                self._url_filter.allowed_domains.add(urlparse(u).netloc)

        # Ensure HTTP session
        session = await self._client._ensure_session()
        self._robots = RobotsParser(user_agent=self._user_agent, session=session)

        # Optionally seed from sitemaps
        if self._use_sitemap:
            sitemap_parser = SitemapParser(session=session)
            for u in urls:
                base = f"{urlparse(u).scheme}://{urlparse(u).netloc}"
                sitemap_urls = await sitemap_parser.fetch_sitemap(f"{base}/sitemap.xml")
                for su in sitemap_urls:
                    self._queue.add_url(su, priority=1, depth=1)

        # Seed start URLs
        for u in urls:
            self._queue.add_url(u, priority=0, depth=0)

        # Pre-fetch robots.txt for start domains
        if self._respect_robots:
            domains_done: set[str] = set()
            for u in urls:
                d = urlparse(u).netloc
                if d not in domains_done:
                    await self._robots.fetch_robots(u)
                    domains_done.add(d)

        self._stats.start()
        results: list[dict] = []
        active_tasks: set[asyncio.Task] = set()
        pages_attempted = 0  # total URLs dequeued (success + failure)

        while self._queue.pending_count > 0 or active_tasks:
            # Launch new tasks until we hit max_p attempts
            while self._queue.pending_count > 0 and pages_attempted < max_p:
                item = await self._queue.get_next()
                if item is None:
                    break
                url, depth = item
                pages_attempted += 1
                task = asyncio.create_task(self._process_url(url, depth))
                active_tasks.add(task)

            if not active_tasks:
                break

            # Wait for at least one task to complete
            done, active_tasks = await asyncio.wait(
                active_tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                result = task.result()
                if result is not None:
                    results.append(result)

            # Periodic progress logging
            self._progress.log_progress(self._queue.pending_count)

        # Cancel remaining tasks (if any slipped in before limit check)
        for t in active_tasks:
            t.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)

        self._stats.stop()
        return results

    async def _process_url(self, url: str, depth: int) -> dict | None:
        """Fetch, parse, enqueue discovered links, and store one page."""
        domain = urlparse(url).netloc

        # Circuit breaker
        if not self._circuit.can_request(domain):
            logger.debug("Circuit open for %s, skipping %s", domain, url)
            self._queue.mark_failed(url, "circuit_open")
            self._stats.record_failure(url, "CircuitOpen")
            self._progress.record_error()
            return None

        # Robots check — fetch on first encounter of each domain (cached after that)
        if self._respect_robots and self._robots:
            await self._robots.fetch_robots(url)
            if not self._robots.can_fetch(url):
                logger.debug("Blocked by robots.txt: %s", url)
                self._queue.mark_failed(url, "robots_blocked")
                self._stats.record_failure(url, "RobotsBlocked")
                self._progress.record_error()
                return None

        # Rate limit (config-based)
        await self._rate_limiter.acquire(url)

        # Honour Crawl-delay from robots.txt (overrides rate limiter minimum)
        if self._respect_robots and self._robots:
            crawl_delay = self._robots.get_crawl_delay(url)
            if crawl_delay > 0:
                await asyncio.sleep(crawl_delay)

        # Semaphore
        await self._semaphore.acquire(url)
        start = time.monotonic()
        try:
            html, status_code, content_type = await self._retry.execute_with_retry(
                self._client.fetch_with_meta, url
            )
            data = await self._parser.parse_html(html, url)
            data["status_code"] = status_code
            data["content_type"] = content_type
            duration = time.monotonic() - start

            self._queue.mark_processed(url)
            self._stats.record_success(url, status_code, len(html), duration)
            self._progress.record_success()
            self._circuit.record_success(domain)

            # Enqueue discovered links
            for link in data.get("links", []):
                if self._url_filter.accept(link, depth + 1):
                    self._queue.add_url(link, priority=depth + 1, depth=depth + 1)

            # Persist
            if self._storage:
                await self._storage.save(data)

            return data

        except PermanentError as exc:
            duration = time.monotonic() - start
            self._queue.mark_failed(url, str(exc))
            self._stats.record_failure(url, type(exc).__name__)
            self._progress.record_error()
            return None

        except Exception as exc:
            duration = time.monotonic() - start
            classified = classify_error(exc)
            self._queue.mark_failed(url, str(classified))
            self._stats.record_failure(url, type(classified).__name__)
            self._progress.record_error()
            self._circuit.record_error(domain)
            return None

        finally:
            self._semaphore.release(url)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return self._stats.summary()

    async def export_to_json(self, filepath: str) -> None:
        await self._stats.export_to_json(filepath)

    async def export_to_html_report(self, filepath: str) -> None:
        await self._stats.export_to_html_report(filepath)

    async def close(self) -> None:
        if self._storage:
            await self._storage.close()
        await self._client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()


# ------------------------------------------------------------------
# Helper: fan out to multiple storages
# ------------------------------------------------------------------

class MultiStorage(DataStorage):
    """Delegate saves to multiple storage backends."""

    def __init__(self, backends: list[DataStorage]):
        self._backends = backends

    async def save(self, data: dict) -> None:
        for b in self._backends:
            await b.save(data)

    async def save_many(self, items: list[dict]) -> None:
        for b in self._backends:
            await b.save_many(items)

    async def close(self) -> None:
        for b in self._backends:
            await b.close()
