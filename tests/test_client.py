"""Tests for Day 1: AsyncCrawler."""

import asyncio
import time

import pytest
import pytest_asyncio

from crawler.client import AsyncCrawler


@pytest.fixture
def crawler():
    return AsyncCrawler(max_concurrent=5, timeout_total=10.0)


@pytest.mark.asyncio
async def test_fetch_valid_url(crawler):
    html = await crawler.fetch_url("https://example.com")
    assert "Example Domain" in html
    await crawler.close()


@pytest.mark.asyncio
async def test_fetch_urls_parallel(crawler):
    urls = ["https://example.com", "https://httpbin.org/get"]
    results = await crawler.fetch_urls(urls)
    assert len(results) >= 1
    await crawler.close()


@pytest.mark.asyncio
async def test_fetch_nonexistent_url(crawler):
    results = await crawler.fetch_urls(["https://httpbin.org/status/404"])
    assert len(results) == 0
    await crawler.close()


@pytest.mark.asyncio
async def test_fetch_timeout():
    crawler = AsyncCrawler(max_concurrent=1, timeout_total=2.0)
    results = await crawler.fetch_urls(["https://httpbin.org/delay/5"])
    assert len(results) == 0
    await crawler.close()


@pytest.mark.asyncio
async def test_parallel_faster_than_sequential():
    """Verify parallel fetch is faster using a mocked fetch_url that sleeps 1s."""
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
    crawler_seq = AsyncCrawler(max_concurrent=10)
    crawler_seq.fetch_url = fake_fetch  # type: ignore[method-assign]
    start = time.monotonic()
    t_seq = 0.0
    for url in urls:
        s = time.monotonic()
        await crawler_seq.fetch_url(url)
        t_seq += time.monotonic() - s

    assert len(results) == len(urls)
    # Parallel ~0.5s, sequential ~2s — parallel must be noticeably faster
    assert t_par < t_seq * 0.6, (
        f"Parallel ({t_par:.2f}s) should be much faster than sequential ({t_seq:.2f}s)"
    )


@pytest.mark.asyncio
async def test_context_manager():
    async with AsyncCrawler(max_concurrent=5) as crawler:
        html = await crawler.fetch_url("https://example.com")
        assert len(html) > 0
