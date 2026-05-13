"""Day 2 demo: HTMLParser — extract links, metadata, headings."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.client import AsyncCrawler
from crawler.parser import HTMLParser


async def main():
    async with AsyncCrawler(timeout_total=15) as crawler:
        html = await crawler.fetch_url("https://example.com")

    parser = HTMLParser()
    data = await parser.parse_html(html, "https://example.com")

    print(f"URL:      {data['url']}")
    print(f"Title:    {data['title']}")
    print(f"Links:    {len(data['links'])}")
    print(f"Headings: {data['headings']}")
    print(f"Text preview: {data['text'][:120]!r}")


if __name__ == "__main__":
    asyncio.run(main())
