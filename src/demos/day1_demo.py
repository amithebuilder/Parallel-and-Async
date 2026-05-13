"""Day 1 demo: AsyncCrawler — parallel vs sequential fetch."""

import asyncio
import sys
import time
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.client import AsyncCrawler

URLS = [
    "https://example.com",
    "https://example.org",
    "https://iana.org",
]


async def main():
    async with AsyncCrawler(max_concurrent=10, timeout_total=15) as crawler:
        # --- Parallel ---
        t0 = time.monotonic()
        results = await crawler.fetch_urls(URLS)
        t_par = time.monotonic() - t0
        print(f"Parallel: {len(results)}/{len(URLS)} pages in {t_par:.2f}s")

        # --- Sequential ---
        t0 = time.monotonic()
        seq_count = 0
        for url in URLS:
            try:
                await crawler.fetch_url(url)
                seq_count += 1
            except Exception:
                pass
        t_seq = time.monotonic() - t0
        print(f"Sequential: {seq_count}/{len(URLS)} pages in {t_seq:.2f}s")
        print(f"Speedup: {t_seq / t_par:.1f}x")


if __name__ == "__main__":
    asyncio.run(main())
