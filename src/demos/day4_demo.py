"""Day 4 demo: RateLimiter + RobotsParser."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.rate_limiter import RateLimiter
from crawler.robots import RobotsParser


async def main():
    # --- RateLimiter ---
    limiter = RateLimiter(requests_per_second=2.0, per_domain=True, min_delay=0.1)
    import time
    urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
    t0 = time.monotonic()
    for url in urls:
        await limiter.acquire(url)
        print(f"  acquired token for {url} at {time.monotonic()-t0:.2f}s")
    print(f"RateLimiter stats: {limiter.get_stats()}")

    # --- RobotsParser ---
    print()
    robots = RobotsParser(user_agent="AsyncCrawler/1.0")
    await robots.fetch_robots("https://example.com")
    print(f"can_fetch /     : {robots.can_fetch('https://example.com/')}")
    print(f"crawl_delay     : {robots.get_crawl_delay('https://example.com/')}s")


if __name__ == "__main__":
    asyncio.run(main())
