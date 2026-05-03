"""Day 1 demo: Basic async HTTP client — parallel vs sequential fetch."""

import asyncio
import logging
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.client import AsyncCrawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


URLS = [
    "https://example.com",
    "https://httpbin.org/delay/1",
    "https://httpbin.org/delay/2",
    "https://httpbin.org/get",
    "https://httpbin.org/html",
    "https://httpbin.org/status/200",
]


async def demo_parallel():
    print("\n=== Parallel fetch ===")
    async with AsyncCrawler(max_concurrent=5) as crawler:
        start = time.monotonic()
        results = await crawler.fetch_urls(URLS)
        elapsed = time.monotonic() - start
    print(f"Fetched {len(results)}/{len(URLS)} pages in {elapsed:.2f}s (parallel)")
    for url, html in results.items():
        print(f"  {url} — {len(html)} bytes")
    return elapsed


async def demo_sequential():
    print("\n=== Sequential fetch ===")
    async with AsyncCrawler(max_concurrent=1) as crawler:
        start = time.monotonic()
        results = {}
        for url in URLS:
            try:
                results[url] = await crawler.fetch_url(url)
            except Exception as exc:
                print(f"  FAIL {url}: {exc}")
        elapsed = time.monotonic() - start
    print(f"Fetched {len(results)}/{len(URLS)} pages in {elapsed:.2f}s (sequential)")
    return elapsed


async def demo_errors():
    print("\n=== Error handling ===")
    bad_urls = [
        "https://httpbin.org/status/404",
        "https://httpbin.org/status/500",
        "https://nonexistent.invalid/",
    ]
    async with AsyncCrawler(max_concurrent=5, timeout_total=5.0) as crawler:
        results = await crawler.fetch_urls(bad_urls)
    print(f"Successful: {len(results)}/{len(bad_urls)}")


async def main():
    t_par = await demo_parallel()
    t_seq = await demo_sequential()
    speedup = t_seq / t_par if t_par > 0 else 0
    print(f"\nSpeedup: {speedup:.1f}x faster with parallel fetch")
    await demo_errors()


if __name__ == "__main__":
    asyncio.run(main())
