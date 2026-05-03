"""Day 6 demo: Saving crawl results to JSON, CSV, and SQLite."""

import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.client import AsyncCrawler
from crawler.parser import HTMLParser
from crawler.storage import JSONStorage, CSVStorage, SQLiteStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

URLS = [
    "https://example.com",
    "https://httpbin.org/html",
    "https://httpbin.org/get",
]


async def main():
    parser = HTMLParser()

    # Fetch pages
    async with AsyncCrawler(max_concurrent=5) as crawler:
        pages = await crawler.fetch_urls(URLS)

    parsed = []
    for url, html in pages.items():
        data = await parser.parse_html(html, url)
        data["status_code"] = 200
        data["content_type"] = "text/html"
        parsed.append(data)

    # JSON storage
    print("\n=== JSON Storage ===")
    async with JSONStorage("demo_results.jsonl") as js:
        await js.save_many(parsed)
        print(f"  Saved {js.count} records to demo_results.jsonl")
        await js.export_all("demo_results_pretty.json")
        print(f"  Exported formatted JSON to demo_results_pretty.json")

    # CSV storage
    print("\n=== CSV Storage ===")
    async with CSVStorage("demo_results.csv") as cs:
        await cs.save_many(parsed)
        print(f"  Saved {cs.count} records to demo_results.csv")

    # SQLite storage
    print("\n=== SQLite Storage ===")
    async with SQLiteStorage("demo_results.db") as db:
        await db.save_many(parsed)
        print(f"  Saved {db.count} records to demo_results.db")

    # Verify SQLite data
    import aiosqlite
    async with aiosqlite.connect("demo_results.db") as conn:
        async with conn.execute("SELECT url, title FROM pages") as cur:
            rows = await cur.fetchall()
            print(f"\n  SQLite contents ({len(rows)} rows):")
            for url, title in rows:
                print(f"    {url} — {title}")


if __name__ == "__main__":
    asyncio.run(main())
