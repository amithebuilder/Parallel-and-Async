"""Day 1: Base async HTTP client for web crawling.
Day 2 adds: fetch_and_parse integrating HTMLParser.
Day 3 adds: crawl() — queue-based depth-limited crawl with visited/failed/processed sets.
"""

import asyncio
import heapq
import logging
import time
from typing import Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)


class AsyncCrawler:
    """Asynchronous HTTP client with concurrency control and connection pooling.

    Args:
        max_concurrent: Maximum number of simultaneous requests.
        timeout_connect: Connection timeout in seconds.
        timeout_read: Read timeout in seconds.
        timeout_total: Total request timeout in seconds.
        headers: Additional HTTP headers to send with each request.
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        timeout_connect: float = 10.0,
        timeout_read: float = 30.0,
        timeout_total: float = 60.0,
        headers: Optional[dict[str, str]] = None,
    ):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._timeout = aiohttp.ClientTimeout(
            connect=timeout_connect,
            sock_read=timeout_read,
            total=timeout_total,
        )
        self._headers = {
            "User-Agent": "AsyncCrawler/1.0",
            **(headers or {}),
        }
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Create or return the existing aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            self._connector = aiohttp.TCPConnector(
                limit=self.max_concurrent,
                limit_per_host=self.max_concurrent // 2 or 1,
                ttl_dns_cache=300,
            )
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=self._timeout,
                headers=self._headers,
            )
        return self._session

    async def fetch_url(self, url: str) -> str:
        """Fetch a single URL and return its text content.

        Raises:
            aiohttp.ClientError: On network errors.
            asyncio.TimeoutError: On timeout.
            aiohttp.ClientResponseError: On HTTP errors (4xx, 5xx).
        """
        session = await self._ensure_session()
        async with self._semaphore:
            logger.info("Fetching: %s", url)
            start = time.monotonic()
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    text = await response.text()
                    elapsed = time.monotonic() - start
                    logger.info(
                        "OK %s — %d, %.2fs, %d bytes",
                        url,
                        response.status,
                        elapsed,
                        len(text),
                    )
                    return text
            except aiohttp.ClientResponseError as exc:
                elapsed = time.monotonic() - start
                logger.warning(
                    "HTTP error %s — %d %s (%.2fs)",
                    url,
                    exc.status,
                    exc.message,
                    elapsed,
                )
                raise
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                logger.warning("Timeout %s (%.2fs)", url, elapsed)
                raise
            except aiohttp.ClientError as exc:
                elapsed = time.monotonic() - start
                logger.warning(
                    "Network error %s — %s: %s (%.2fs)",
                    url,
                    type(exc).__name__,
                    exc,
                    elapsed,
                )
                raise

    async def fetch_with_meta(self, url: str) -> tuple[str, int, str]:
        """Fetch a URL and return (html, status_code, content_type).

        Raises the same exceptions as :meth:`fetch_url`.
        """
        session = await self._ensure_session()
        async with self._semaphore:
            logger.info("Fetching (meta): %s", url)
            start = time.monotonic()
            try:
                async with session.get(url) as response:
                    response.raise_for_status()
                    text = await response.text()
                    elapsed = time.monotonic() - start
                    status = response.status
                    content_type = (
                        response.headers.get("Content-Type", "text/html")
                        .split(";")[0]
                        .strip()
                    )
                    logger.info(
                        "OK %s — %d, %.2fs, %d bytes",
                        url, status, elapsed, len(text),
                    )
                    return text, status, content_type
            except aiohttp.ClientResponseError as exc:
                elapsed = time.monotonic() - start
                logger.warning(
                    "HTTP error %s — %d %s (%.2fs)",
                    url, exc.status, exc.message, elapsed,
                )
                raise
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                logger.warning("Timeout %s (%.2fs)", url, elapsed)
                raise
            except aiohttp.ClientError as exc:
                elapsed = time.monotonic() - start
                logger.warning(
                    "Network error %s — %s: %s (%.2fs)",
                    url, type(exc).__name__, exc, elapsed,
                )
                raise

    async def fetch_urls(self, urls: list[str]) -> dict[str, str]:
        """Fetch multiple URLs in parallel, returning {url: text} for successful ones."""
        tasks = {url: asyncio.create_task(self.fetch_url(url)) for url in urls}
        results: dict[str, str] = {}
        for url, task in tasks.items():
            try:
                results[url] = await task
            except Exception as exc:
                logger.error("Failed %s — %s: %s", url, type(exc).__name__, exc)
        return results

    async def crawl(
        self,
        start_urls: list[str],
        max_pages: int = 50,
        max_depth: int = 2,
        same_domain_only: bool = True,
    ) -> list[dict]:
        """Queue-based breadth-first crawl (Day 3).

        Populates three public sets on the instance after crawling:
            visited_urls   — every URL that was enqueued
            failed_urls    — URLs where fetch or parse raised an exception
            processed_urls — URLs successfully fetched and parsed

        Args:
            start_urls:        Seed URLs to begin crawling from.
            max_pages:         Stop after this many successful pages.
            max_depth:         Maximum link depth from seed URLs.
            same_domain_only:  Only follow links on the same domain(s) as seeds.

        Returns:
            List of parsed page dicts (url, title, links, text, …).
        """
        # Import here to avoid circular imports at module level
        from crawler.parser import HTMLParser

        self.visited_urls: set[str] = set()
        self.failed_urls: set[str] = set()
        self.processed_urls: set[str] = set()

        allowed_domains: set[str] | None = (
            {urlparse(u).netloc for u in start_urls} if same_domain_only else None
        )
        parser = HTMLParser()
        results: list[dict] = []

        # Min-heap: (depth, counter, url) — depth first, counter breaks ties
        queue: list[tuple[int, int, str]] = []
        _counter = 0
        for url in start_urls:
            if url not in self.visited_urls:
                self.visited_urls.add(url)
                heapq.heappush(queue, (0, _counter, url))
                _counter += 1

        while queue and len(results) < max_pages:
            depth, _, url = heapq.heappop(queue)
            try:
                html = await self.fetch_url(url)
                data = await parser.parse_html(html, url)
                data["depth"] = depth
                results.append(data)
                self.processed_urls.add(url)

                if depth < max_depth:
                    for link in data.get("links", []):
                        if link in self.visited_urls:
                            continue
                        if allowed_domains is not None:
                            if urlparse(link).netloc not in allowed_domains:
                                continue
                        self.visited_urls.add(link)
                        heapq.heappush(queue, (depth + 1, _counter, link))
                        _counter += 1

            except Exception as exc:
                self.failed_urls.add(url)
                logger.warning("crawl: failed %s — %s", url, exc)

        return results

    async def fetch_and_parse(self, url: str) -> dict:
        """Fetch a URL and return structured parsed data (Day 2 integration).

        Returns dict with: url, title, text, links, metadata, images, headings,
        tables, lists. On fetch failure returns a dict with the error set.
        """
        # Import here to avoid circular imports at module level
        from crawler.parser import HTMLParser
        parser = HTMLParser()
        try:
            html = await self.fetch_url(url)
            return await parser.parse_html(html, url)
        except Exception as exc:
            logger.error("fetch_and_parse failed for %s: %s", url, exc)
            return {
                "url": url,
                "title": "",
                "text": "",
                "links": [],
                "metadata": {},
                "images": [],
                "headings": [],
                "tables": [],
                "lists": [],
                "error": str(exc),
            }

    async def close(self) -> None:
        """Close the HTTP session and connector."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        self._connector = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
