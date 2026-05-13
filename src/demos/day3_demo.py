"""Day 3 demo: crawl() — queue-based crawl with visited/failed/processed sets."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.client import AsyncCrawler


async def main():
    async with AsyncCrawler(max_concurrent=5, timeout_total=15) as crawler:
        results = await crawler.crawl(
            start_urls=["https://example.com"],
            max_pages=10,
            max_depth=1,
            same_domain_only=True,
        )

    print(f"Pages crawled : {len(results)}")
    print(f"Visited URLs  : {len(crawler.visited_urls)}")
    print(f"Processed URLs: {len(crawler.processed_urls)}")
    print(f"Failed URLs   : {len(crawler.failed_urls)}")
    for page in results[:3]:
        print(f"  [{page.get('depth', 0)}] {page['url']} — {page.get('title', '')!r}")


if __name__ == "__main__":
    asyncio.run(main())
