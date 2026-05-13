# Architecture

## Component overview

```
CLI (main.py)
    └─► AdvancedCrawler (advanced.py)   ← Day 7 integration
            ├─ AsyncCrawler  (client.py)      Day 1 + 3 crawl()
            ├─ HTMLParser    (parser.py)      Day 2
            ├─ CrawlerQueue  (queue.py)       Day 3
            ├─ SemaphoreManager (queue.py)    Day 3
            ├─ URLFilter     (queue.py)       Day 3
            ├─ RateLimiter   (rate_limiter.py) Day 4
            ├─ RobotsParser  (robots.py)      Day 4
            ├─ RetryStrategy (retry.py)       Day 5
            ├─ CircuitBreaker (retry.py)      Day 5
            ├─ DataStorage   (storage.py)     Day 6
            │     ├─ JSONStorage
            │     ├─ CSVStorage
            │     └─ SQLiteStorage
            ├─ CrawlerStats  (stats.py)       Day 7
            ├─ SitemapParser (sitemap.py)     Day 7
            └─ CrawlerConfig (config.py)      Day 7
```

## Data flow for a single URL

```
URL dequeued
    │
    ▼
CircuitBreaker.can_request?  ──No──► skip
    │ Yes
    ▼
RobotsParser.can_fetch?      ──No──► skip
    │ Yes
    ▼
RateLimiter.acquire()        ← token-bucket wait
    │
asyncio.sleep(crawl_delay)   ← Crawl-delay from robots.txt
    │
    ▼
RetryStrategy.execute_with_retry(fetch_with_meta)
    │ success              failure (permanent) → skip
    ▼                      failure (transient) → exponential backoff
HTMLParser.parse_html()
    │
    ▼
CrawlerStats.record_success()
CircuitBreaker.record_success()
    │
    ├─► enqueue discovered links (URLFilter)
    └─► DataStorage.save()
```

## Key patterns

| Pattern | Where |
|---------|-------|
| async/await + event loop | all modules |
| asyncio.Semaphore (global + per-domain) | queue.py, client.py |
| asyncio.create_task + wait(FIRST_COMPLETED) | advanced.py |
| Connection pooling (TCPConnector) | client.py |
| Token bucket rate limiting | rate_limiter.py |
| Exponential backoff with jitter | retry.py |
| Circuit breaker (CLOSED/OPEN/HALF_OPEN) | retry.py |
| Priority heap queue | queue.py |
| Async file I/O (aiofiles) | storage.py, stats.py |
| Async SQLite (aiosqlite) | storage.py |
