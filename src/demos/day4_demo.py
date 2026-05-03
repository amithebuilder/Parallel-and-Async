"""Day 4 demo: Rate limiting and robots.txt."""

import asyncio
import logging
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.client import AsyncCrawler
from crawler.rate_limiter import RateLimiter
from crawler.robots import RobotsParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def demo_rate_limiter():
    print("\n=== Rate Limiter Demo ===")
    limiter = RateLimiter(requests_per_second=2.0, per_domain=True, min_delay=0.3, jitter=0.1)

    urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/html",
        "https://httpbin.org/status/200",
        "https://example.com",
        "https://example.com/page1",
    ]

    async with AsyncCrawler(max_concurrent=5) as crawler:
        start = time.monotonic()
        for url in urls:
            wait = await limiter.acquire(url)
            try:
                await crawler.fetch_url(url)
                print(f"  OK {url} (waited {wait:.2f}s)")
            except Exception as exc:
                print(f"  FAIL {url}: {exc}")
        elapsed = time.monotonic() - start

    print(f"Rate limiter stats: {limiter.get_stats()}")
    print(f"Total time: {elapsed:.2f}s\n")


async def demo_robots():
    print("=== Robots.txt Demo ===")
    robots = RobotsParser(user_agent="AsyncCrawler/1.0")

    test_sites = [
        "https://www.google.com",
        "https://example.com",
    ]

    for base_url in test_sites:
        rules = await robots.fetch_robots(base_url)
        print(f"\n  {base_url}/robots.txt:")
        print(f"    Disallow: {rules.get('disallow', [])[:5]}")
        print(f"    Crawl-delay: {rules.get('crawl_delay')}")

        # Test some paths
        test_paths = ["/", "/search", "/admin", "/api"]
        for path in test_paths:
            url = f"{base_url}{path}"
            allowed = robots.can_fetch(url)
            print(f"    {url} — {'allowed' if allowed else 'BLOCKED'}")

    print(f"\n  Total blocked: {robots.blocked_count}")


async def main():
    await demo_rate_limiter()
    await demo_robots()


if __name__ == "__main__":
    asyncio.run(main())
