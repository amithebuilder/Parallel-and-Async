"""Tests for Day 1 & 3: AsyncCrawler — all HTTP mocked, no real network."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from crawler.client import AsyncCrawler

# ---------------------------------------------------------------------------
# Helper: build a fake aiohttp.ClientSession
# ---------------------------------------------------------------------------

def _mock_session(
    html: str = "<html><title>Example Domain</title><body>ok</body></html>",
    status: int = 200,
    content_type: str = "text/html",
    raise_exc: Exception | None = None,
):
    """Return a MagicMock that quacks like an aiohttp.ClientSession."""
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=html)
    resp.headers = {"Content-Type": f"{content_type}; charset=utf-8"}

    if raise_exc is not None:
        resp.raise_for_status = MagicMock(side_effect=raise_exc)
    elif status >= 400:
        exc = aiohttp.ClientResponseError(
            MagicMock(), (), status=status, message="Error"
        )
        resp.raise_for_status = MagicMock(side_effect=exc)
    else:
        resp.raise_for_status = MagicMock()

    # session.get(url) must work as an async context manager
    get_cm = MagicMock()
    get_cm.__aenter__ = AsyncMock(return_value=resp)
    get_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=get_cm)
    session.closed = False
    session.close = AsyncMock()
    return session


def _timeout_session():
    """Session whose get() raises TimeoutError on enter."""
    get_cm = MagicMock()
    get_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
    get_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=get_cm)
    session.closed = False
    session.close = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_valid_url():
    sess = _mock_session("<html><title>Example Domain</title></html>")
    with patch.object(AsyncCrawler, "_ensure_session", AsyncMock(return_value=sess)):
        crawler = AsyncCrawler(max_concurrent=5)
        html = await crawler.fetch_url("https://example.com")
        assert "Example Domain" in html
        await crawler.close()


@pytest.mark.asyncio
async def test_fetch_urls_parallel():
    sess = _mock_session("<html><body>page</body></html>")
    with patch.object(AsyncCrawler, "_ensure_session", AsyncMock(return_value=sess)):
        crawler = AsyncCrawler(max_concurrent=5)
        urls = ["https://example.com", "https://httpbin.org/get"]
        results = await crawler.fetch_urls(urls)
        assert len(results) >= 1
        await crawler.close()


@pytest.mark.asyncio
async def test_fetch_nonexistent_url():
    sess = _mock_session(status=404)
    with patch.object(AsyncCrawler, "_ensure_session", AsyncMock(return_value=sess)):
        crawler = AsyncCrawler(max_concurrent=5)
        results = await crawler.fetch_urls(["https://example.com/missing"])
        assert len(results) == 0
        await crawler.close()


@pytest.mark.asyncio
async def test_fetch_timeout():
    sess = _timeout_session()
    with patch.object(AsyncCrawler, "_ensure_session", AsyncMock(return_value=sess)):
        crawler = AsyncCrawler(max_concurrent=1)
        results = await crawler.fetch_urls(["https://example.com/slow"])
        assert len(results) == 0
        await crawler.close()


@pytest.mark.asyncio
async def test_parallel_faster_than_sequential():
    """Parallel fetch is faster — verified with a fake fetch_url that sleeps."""
    DELAY = 0.5
    urls = [f"https://fake.test/page{i}" for i in range(4)]

    async def fake_fetch(url: str) -> str:
        await asyncio.sleep(DELAY)
        return f"<html>{url}</html>"

    # Parallel
    crawler_par = AsyncCrawler(max_concurrent=10)
    crawler_par.fetch_url = fake_fetch  # type: ignore[method-assign]
    start = time.monotonic()
    results = await crawler_par.fetch_urls(urls)
    t_par = time.monotonic() - start
    await crawler_par.close()

    # Sequential
    t_seq = 0.0
    for url in urls:
        s = time.monotonic()
        await fake_fetch(url)
        t_seq += time.monotonic() - s

    assert len(results) == len(urls)
    assert t_par < t_seq * 0.6, (
        f"Parallel ({t_par:.2f}s) should be much faster than sequential ({t_seq:.2f}s)"
    )


@pytest.mark.asyncio
async def test_context_manager():
    sess = _mock_session("<html><body>context manager test</body></html>")
    with patch.object(AsyncCrawler, "_ensure_session", AsyncMock(return_value=sess)):
        async with AsyncCrawler(max_concurrent=5) as crawler:
            html = await crawler.fetch_url("https://example.com")
            assert len(html) > 0


# ---------------------------------------------------------------------------
# Day 3: crawl() method tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crawl_basic():
    """crawl() returns pages and populates visited/processed/failed sets."""
    html = (
        "<html><head><title>Home</title></head>"
        "<body><a href='/page2'>p2</a></body></html>"
    )
    urls_to_crawl = {"https://example.com", "https://example.com/page2"}

    call_count = 0

    async def fake_fetch(url: str) -> str:
        nonlocal call_count
        call_count += 1
        return html

    crawler = AsyncCrawler(max_concurrent=5)
    crawler.fetch_url = fake_fetch  # type: ignore[method-assign]

    results = await crawler.crawl(
        ["https://example.com"],
        max_pages=5,
        max_depth=1,
        same_domain_only=True,
    )
    await crawler.close()

    assert len(results) >= 1
    assert "https://example.com" in crawler.visited_urls
    assert "https://example.com" in crawler.processed_urls
    assert len(crawler.failed_urls) == 0


@pytest.mark.asyncio
async def test_crawl_respects_max_pages():
    async def fake_fetch(url: str) -> str:
        return "<html><head><title>T</title></head><body></body></html>"

    crawler = AsyncCrawler(max_concurrent=5)
    crawler.fetch_url = fake_fetch  # type: ignore[method-assign]

    results = await crawler.crawl(
        ["https://a.com", "https://a.com/1", "https://a.com/2",
         "https://a.com/3", "https://a.com/4"],
        max_pages=3,
        max_depth=0,
        same_domain_only=True,
    )
    await crawler.close()
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_crawl_records_failed():
    async def fake_fetch(url: str) -> str:
        raise aiohttp.ClientError("connection refused")

    crawler = AsyncCrawler(max_concurrent=5)
    crawler.fetch_url = fake_fetch  # type: ignore[method-assign]

    results = await crawler.crawl(
        ["https://broken.example.com"],
        max_pages=5,
        max_depth=0,
    )
    await crawler.close()
    assert len(results) == 0
    assert "https://broken.example.com" in crawler.failed_urls
