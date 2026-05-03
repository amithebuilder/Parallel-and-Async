# Архитектура проекта: Async Web Crawler

## Компоненты и слои

```
src/crawler/
├── client.py       День 1 — HTTP-клиент
├── parser.py       День 2 — HTML-парсер
├── queue.py        День 3 — очередь и конкурентность
├── rate_limiter.py День 4 — ограничение скорости
├── robots.py       День 4 — соблюдение robots.txt
├── retry.py        День 5 — повторы и circuit breaker
├── storage.py      День 6 — сохранение данных
├── stats.py        День 7 — статистика и отчёты
├── sitemap.py      День 7 — парсинг sitemap.xml
├── config.py       День 7 — конфигурация (YAML/JSON)
└── advanced.py     День 7 — финальная интеграция
```

## Поток данных

```
URL
 │
 ▼
CrawlerQueue (приоритет, дедупликация)
 │
 ▼
RobotsParser.can_fetch?  ──── нет ──→ skip
 │ да
 ▼
RateLimiter.acquire()  (ждём если слишком быстро)
 │
 ▼
SemaphoreManager.acquire()  (глобальный + per-domain лимит)
 │
 ▼
RetryStrategy → AsyncCrawler.fetch_url()
 │
 ├── ошибка → CircuitBreaker.record_error()
 │             CrawlerQueue.mark_failed()
 │
 └── успех → HTMLParser.parse_html()
               │
               ├── новые ссылки → URLFilter → CrawlerQueue.add_url()
               ├── DataStorage.save()
               └── CrawlerStats.record_success()
```

## Ключевые паттерны

| Паттерн | Где используется |
|---|---|
| `async/await` | Всё |
| `asyncio.Semaphore` | Ограничение параллелизма |
| `asyncio.create_task` | Параллельный запуск задач |
| `asyncio.wait(FIRST_COMPLETED)` | Главный цикл в AdvancedCrawler |
| Connection pooling | `aiohttp.TCPConnector` |
| Token bucket | `RateLimiter` |
| Exponential backoff | `RetryStrategy` |
| Circuit breaker | `CircuitBreaker` |
| Batch writes | `SQLiteStorage` |
