"""Tests for Day 7: AdvancedCrawler integration — HTTP fully mocked."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from crawler.advanced import AdvancedCrawler
from crawler.client import AsyncCrawler
from crawler.config import CrawlerConfig
from crawler.storage import JSONStorage

# ---------------------------------------------------------------------------
# Shared HTML fixture — has title + one internal link
# ---------------------------------------------------------------------------
_HTML = (
    "<html><head><title>Test Page</title></head>"
    "<body><a href='/about'>About</a></body></html>"
)


def _patch_fetch():
    """Context manager: mock AsyncCrawler.fetch_with_meta → (html, 200, text/html)."""
    return patch.object(
        AsyncCrawler,
        "fetch_with_meta",
        new=AsyncMock(return_value=(_HTML, 200, "text/html")),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advanced_crawler_basic():
    with _patch_fetch():
        async with AdvancedCrawler(
            start_urls=["https://example.com"],
            max_pages=3,
            max_depth=1,
            max_concurrent=3,
            requests_per_second=100.0,
            respect_robots=False,
            same_domain_only=True,
        ) as crawler:
            results = await crawler.crawl()

    assert len(results) >= 1
    assert results[0]["url"] == "https://example.com"
    assert results[0]["title"] == "Test Page"

    stats = crawler.get_stats()
    assert stats["total_pages"] >= 1
    assert stats["successful"] >= 1


@pytest.mark.asyncio
async def test_advanced_crawler_with_storage(tmp_path):
    output = str(tmp_path / "results.jsonl")
    storage = JSONStorage(output)

    with _patch_fetch():
        async with AdvancedCrawler(
            start_urls=["https://example.com"],
            max_pages=2,
            max_depth=0,
            max_concurrent=2,
            requests_per_second=100.0,
            respect_robots=False,
            storage=storage,
        ) as crawler:
            results = await crawler.crawl()

    assert os.path.exists(output)
    with open(output, encoding="utf-8") as f:
        lines = [l for l in f.readlines() if l.strip()]
    assert len(lines) >= 1


@pytest.mark.asyncio
async def test_advanced_crawler_stats_export(tmp_path):
    with _patch_fetch():
        async with AdvancedCrawler(
            start_urls=["https://example.com"],
            max_pages=1,
            max_depth=0,
            max_concurrent=1,
            requests_per_second=100.0,
            respect_robots=False,
        ) as crawler:
            await crawler.crawl()
            json_path = str(tmp_path / "stats.json")
            html_path = str(tmp_path / "report.html")
            await crawler.export_to_json(json_path)
            await crawler.export_to_html_report(html_path)

    assert os.path.exists(json_path)
    assert os.path.exists(html_path)
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    assert "Crawler Report" in html
    assert "<svg" in html  # charts present


def test_config_from_dict():
    cfg = CrawlerConfig(
        start_urls=["https://example.com"],
        max_pages=10,
        max_depth=2,
    )
    assert cfg.start_urls == ["https://example.com"]
    assert cfg.max_pages == 10
    d = cfg.to_dict()
    assert d["max_depth"] == 2


def test_config_from_yaml(tmp_path):
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(
        "start_urls:\n  - https://example.com\nmax_pages: 5\nmax_depth: 1\n",
        encoding="utf-8",
    )
    cfg = CrawlerConfig.from_file(str(config_file))
    assert cfg.start_urls == ["https://example.com"]
    assert cfg.max_pages == 5
