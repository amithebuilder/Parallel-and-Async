"""Tests for Day 4: RateLimiter and RobotsParser."""

import asyncio
import time

import pytest
from crawler.rate_limiter import RateLimiter
from crawler.robots import RobotsParser


@pytest.mark.asyncio
async def test_rate_limiter_enforces_delay():
    limiter = RateLimiter(requests_per_second=2.0, per_domain=True, min_delay=0.0)
    url = "https://example.com/1"

    start = time.monotonic()
    await limiter.acquire(url)
    await limiter.acquire(url)  # should wait ~0.5s
    elapsed = time.monotonic() - start

    assert elapsed >= 0.4  # at least ~0.5s for 2 req/s


@pytest.mark.asyncio
async def test_rate_limiter_different_domains():
    limiter = RateLimiter(requests_per_second=1.0, per_domain=True)

    start = time.monotonic()
    await limiter.acquire("https://a.com/1")
    await limiter.acquire("https://b.com/1")  # different domain, no wait
    elapsed = time.monotonic() - start

    assert elapsed < 0.5  # should be nearly instant


@pytest.mark.asyncio
async def test_rate_limiter_global_mode():
    limiter = RateLimiter(requests_per_second=2.0, per_domain=False)

    start = time.monotonic()
    await limiter.acquire("https://a.com/1")
    await limiter.acquire("https://b.com/1")  # global, should wait
    elapsed = time.monotonic() - start

    assert elapsed >= 0.4


@pytest.mark.asyncio
async def test_rate_limiter_stats():
    limiter = RateLimiter(requests_per_second=10.0, per_domain=True)
    await limiter.acquire("https://a.com/1")
    await limiter.acquire("https://a.com/2")
    stats = limiter.get_stats()
    assert "total_waits" in stats
    assert "avg_wait_time" in stats


def test_robots_parser_path_matching():
    assert RobotsParser._path_matches("/admin/", "/admin/")
    assert RobotsParser._path_matches("/admin/page", "/admin/")
    assert not RobotsParser._path_matches("/about", "/admin/")
    assert RobotsParser._path_matches("/search.html", "/*.html$")


@pytest.mark.asyncio
async def test_robots_can_fetch_no_rules():
    robots = RobotsParser(user_agent="TestBot")
    # Without fetching, everything should be allowed
    assert robots.can_fetch("https://example.com/anything")


@pytest.mark.asyncio
async def test_robots_fetch_and_check():
    robots = RobotsParser(user_agent="*")
    await robots.fetch_robots("https://example.com")
    # example.com has no robots.txt restrictions typically
    assert robots.can_fetch("https://example.com/")
