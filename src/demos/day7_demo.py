"""Day 7 demo: AdvancedCrawler full integration."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.advanced import AdvancedCrawler


async def main():
    async with AdvancedCrawler(
        start_urls=["https://example.com"],
        max_pages=5,
        max_depth=1,
        max_concurrent=5,
        requests_per_second=3.0,
        respect_robots=True,
        same_domain_only=True,
    ) as crawler:
        results = await crawler.crawl()

    stats = crawler.get_stats()
    print(f"Pages crawled : {stats['total_pages']}")
    print(f"Successful    : {stats['successful']}")
    print(f"Failed        : {stats['failed']}")
    print(f"Pages/sec     : {stats['pages_per_sec']}")
    print(f"Status codes  : {stats['status_codes']}")
    for r in results:
        print(f"  {r['url']} — {r.get('title', '')!r}")


if __name__ == "__main__":
    asyncio.run(main())
