"""Tests for Day 3: CrawlerQueue, SemaphoreManager, URLFilter."""

import asyncio
import pytest
from crawler.queue import CrawlerQueue, SemaphoreManager, URLFilter


@pytest.mark.asyncio
async def test_queue_basic():
    q = CrawlerQueue()
    assert q.add_url("https://a.com", priority=0, depth=0)
    assert q.add_url("https://b.com", priority=1, depth=1)
    assert q.pending_count == 2

    # First out should be highest priority (lowest number)
    url = await q.get_next()
    assert url == "https://a.com"
    assert q.get_depth("https://a.com") == 0

    url = await q.get_next()
    assert url == "https://b.com"
    assert q.get_depth("https://b.com") == 1

    assert await q.get_next() is None


@pytest.mark.asyncio
async def test_queue_no_duplicates():
    q = CrawlerQueue()
    assert q.add_url("https://a.com")
    assert not q.add_url("https://a.com")  # duplicate
    assert q.pending_count == 1


@pytest.mark.asyncio
async def test_queue_mark_processed():
    q = CrawlerQueue()
    q.add_url("https://a.com")
    q.mark_processed("https://a.com")
    assert q.processed_count == 1
    assert not q.add_url("https://a.com")  # already processed


@pytest.mark.asyncio
async def test_queue_mark_failed():
    q = CrawlerQueue()
    q.add_url("https://a.com")
    q.mark_failed("https://a.com", "404")
    assert q.failed_count == 1
    stats = q.get_stats()
    assert stats["failed"] == 1


@pytest.mark.asyncio
async def test_queue_priority_order():
    q = CrawlerQueue()
    q.add_url("https://low.com", priority=10, depth=0)
    q.add_url("https://high.com", priority=0, depth=0)
    q.add_url("https://mid.com", priority=5, depth=0)

    assert await q.get_next() == "https://high.com"
    assert await q.get_next() == "https://mid.com"
    assert await q.get_next() == "https://low.com"


def test_url_filter_depth():
    f = URLFilter(max_depth=2)
    assert f.accept("https://a.com", depth=2)
    assert not f.accept("https://a.com", depth=3)


def test_url_filter_same_domain():
    f = URLFilter(same_domain_only=True, allowed_domains={"example.com"})
    assert f.accept("https://example.com/page", depth=0)
    assert not f.accept("https://other.com/page", depth=0)


def test_url_filter_exclude_pattern():
    f = URLFilter(exclude_patterns=[r"\.pdf$", r"/admin/"])
    assert f.accept("https://a.com/page", depth=0)
    assert not f.accept("https://a.com/file.pdf", depth=0)
    assert not f.accept("https://a.com/admin/login", depth=0)


def test_url_filter_include_pattern():
    f = URLFilter(include_patterns=[r"/blog/"])
    assert f.accept("https://a.com/blog/post1", depth=0)
    assert not f.accept("https://a.com/about", depth=0)


@pytest.mark.asyncio
async def test_semaphore_manager():
    sem = SemaphoreManager(global_limit=2, per_domain_limit=1)
    await sem.acquire("https://a.com/1")
    assert sem.active_count == 1
    sem.release("https://a.com/1")
    assert sem.active_count == 0
