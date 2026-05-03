"""Day 7 demo: Full integration — AdvancedCrawler with config, stats, reports."""

import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.advanced import AdvancedCrawler
from crawler.storage import JSONStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def demo_direct():
    """Run AdvancedCrawler with direct parameters."""
    print("\n=== AdvancedCrawler (direct) ===")
    storage = JSONStorage("day7_results.jsonl")

    async with AdvancedCrawler(
        start_urls=["https://example.com"],
        max_pages=10,
        max_depth=1,
        max_concurrent=5,
        requests_per_second=2.0,
        respect_robots=True,
        same_domain_only=True,
        min_delay=0.3,
        storage=storage,
    ) as crawler:
        results = await crawler.crawl()

        stats = crawler.get_stats()
        print(f"\n  Total pages:   {stats['total_pages']}")
        print(f"  Successful:    {stats['successful']}")
        print(f"  Failed:        {stats['failed']}")
        print(f"  Pages/sec:     {stats['pages_per_sec']}")
        print(f"  Elapsed:       {stats['elapsed_sec']}s")
        print(f"  Status codes:  {stats['status_codes']}")

        await crawler.export_to_json("day7_stats.json")
        await crawler.export_to_html_report("day7_report.html")
        print("\n  Exported: day7_stats.json, day7_report.html")

    return results


async def demo_from_config():
    """Run AdvancedCrawler from a YAML config file."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    if not os.path.exists(config_path):
        print("\n=== Skipping config demo (config.yaml not found) ===")
        return

    print("\n=== AdvancedCrawler (from config.yaml) ===")
    async with AdvancedCrawler.from_config(config_path) as crawler:
        results = await crawler.crawl()
        stats = crawler.get_stats()
        print(f"  Crawled {stats['total_pages']} pages in {stats['elapsed_sec']}s")


async def main():
    results = await demo_direct()
    print(f"\nCollected {len(results)} page records")
    for r in results[:5]:
        print(f"  {r['url']} — {r['title']}")

    await demo_from_config()


if __name__ == "__main__":
    asyncio.run(main())
