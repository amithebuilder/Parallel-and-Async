"""Day 2 demo: HTML parsing and data extraction."""

import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.client import AsyncCrawler
from crawler.parser import HTMLParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

URLS = [
    "https://example.com",
    "https://httpbin.org/html",
    "https://en.wikipedia.org/wiki/Web_crawler",
]


async def main():
    parser = HTMLParser()
    async with AsyncCrawler(max_concurrent=5) as crawler:
        pages = await crawler.fetch_urls(URLS)

    print(f"\nParsed {len(pages)} pages:\n")
    all_results = []
    for url, html in pages.items():
        data = await parser.parse_html(html, url)
        summary = {
            "url": data["url"],
            "title": data["title"],
            "text_length": len(data["text"]),
            "links_count": len(data["links"]),
            "images_count": len(data["images"]),
            "headings": [h["text"][:60] for h in data["headings"][:5]],
        }
        all_results.append(summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print()

    # Save results
    with open("day2_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("Results saved to day2_results.json")


if __name__ == "__main__":
    asyncio.run(main())
