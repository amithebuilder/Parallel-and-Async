# Async Web Crawler

Высокопроизводительный асинхронный веб-краулер на Python (asyncio, aiohttp).
Финальный проект блока **«Параллельность и асинхронность»**.

## Структура проекта

```
parallelasync/
├── src/
│   ├── main.py              # CLI точка входа
│   ├── crawler/             # Основной пакет
│   │   ├── client.py        # День 1+3: AsyncCrawler + crawl()
│   │   ├── parser.py        # День 2: HTMLParser
│   │   ├── queue.py         # День 3: CrawlerQueue, SemaphoreManager
│   │   ├── rate_limiter.py  # День 4: RateLimiter
│   │   ├── robots.py        # День 4: RobotsParser
│   │   ├── retry.py         # День 5: RetryStrategy, CircuitBreaker
│   │   ├── storage.py       # День 6: JSON / CSV / SQLite
│   │   ├── stats.py         # День 7: CrawlerStats + HTML-отчёт + SVG-графики
│   │   ├── sitemap.py       # День 7: SitemapParser
│   │   ├── config.py        # День 7: CrawlerConfig (YAML/JSON)
│   │   └── advanced.py      # День 7: AdvancedCrawler (интеграция)
│   └── demos/               # Демо-скрипты (день 1–7)
│       ├── day1_demo.py     # Parallel vs sequential fetch
│       ├── day2_demo.py     # HTML parsing
│       ├── day3_demo.py     # Queue-based crawl
│       ├── day4_demo.py     # Rate limiter + robots
│       ├── day5_demo.py     # Retry + circuit breaker
│       ├── day6_demo.py     # Storage backends
│       └── day7_demo.py     # Full AdvancedCrawler
├── tests/                   # Тесты (57 шт., без реального интернета)
├── docs/
│   └── architecture.md      # Компонентная схема и data flow
├── config.yaml              # Пример конфигурации
├── requirements.txt
└── .gitignore
```

## Установка

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

## Использование

### CLI

```bash
# Базовый запуск
python src/main.py --urls https://example.com --max-pages 50

# С сохранением результатов
python src/main.py --urls https://example.com \
    --max-pages 100 --max-depth 2 \
    --output results.jsonl \
    --report report.html

# Из конфигурационного файла
python src/main.py --config config.yaml
```
## Возможности краулера

- Параллельная загрузка страниц (`asyncio.create_task`)
- Ограничение конкурентности (глобально и per-domain)
- Rate limiting с jitter
- Соблюдение `robots.txt`
- Автоматические повторы с exponential backoff
- Circuit breaker для нестабильных доменов
- Сохранение в JSON Lines, CSV, SQLite
- Поддержка `sitemap.xml`
- Конфигурация через YAML
- CLI интерфейс
- HTML-отчёт со статистикой