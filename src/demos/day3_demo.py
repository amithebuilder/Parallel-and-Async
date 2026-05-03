"""Day 3 demo: Queue, concurrency, depth-limited crawl."""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.client import AsyncCrawler
from crawler.parser import HTMLParser
from crawler.queue import CrawlerQueue, SemaphoreManager, URLFilter, ProgressTracker
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

START_URL = "https://example.com"
MAX_PAGES = 15
MAX_DEPTH = 2


async def main():
    queue = CrawlerQueue()
    semaphore = SemaphoreManager(global_limit=5, per_domain_limit=3)
    url_filter = URLFilter(
        same_domain_only=True,
        allowed_domains={urlparse(START_URL).netloc},
        max_depth=MAX_DEPTH,
    )
    progress = ProgressTracker()
    parser = HTMLParser()

    queue.add_url(START_URL, priority=0, depth=0)
    results = []

    async with AsyncCrawler(max_concurrent=5) as crawler:
        while queue.pending_count > 0 and len(results) < MAX_PAGES:
            item = await queue.get_next()
            if item is None:
                break
            url, depth = item

            await semaphore.acquire(url)
            try:
                html = await crawler.fetch_url(url)
                data = await parser.parse_html(html, url)
                queue.mark_processed(url)
                progress.record_success()
                results.append(data)

                # Enqueue discovered links
                for link in data.get("links", []):
                    if url_filter.accept(link, depth + 1):
                        queue.add_url(link, priority=depth + 1, depth=depth + 1)
            except Exception as exc:
                queue.mark_failed(url, str(exc))
                progress.record_error()
            finally:
                semaphore.release(url)

            progress.log_progress(queue.pending_count)

    print(f"\n{'='*50}")
    print(f"Crawled {len(results)} pages (max_depth={MAX_DEPTH})")
    print(f"Queue stats: {queue.get_stats()}")
    print(f"Progress: {progress.get_stats()}")
    for r in results:
        print(f"  {r['url']} — {r['title']}")


if __name__ == "__main__":
    asyncio.run(main())
