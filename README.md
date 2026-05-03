# Async Web Crawler

Высокопроизводительный асинхронный веб-краулер на Python (asyncio, aiohttp).
Финальный проект блока **«Параллельность и асинхронность»**.

## Структура проекта

```
parallelasync/
├── src/
│   ├── main.py              # CLI точка входа
│   ├── crawler/             # Основной пакет
│   │   ├── client.py        # День 1: AsyncCrawler
│   │   ├── parser.py        # День 2: HTMLParser
│   │   ├── queue.py         # День 3: CrawlerQueue, SemaphoreManager
│   │   ├── rate_limiter.py  # День 4: RateLimiter
│   │   ├── robots.py        # День 4: RobotsParser
│   │   ├── retry.py         # День 5: RetryStrategy, CircuitBreaker
│   │   ├── storage.py       # День 6: JSON / CSV / SQLite
│   │   ├── stats.py         # День 7: CrawlerStats + HTML-отчёт
│   │   ├── sitemap.py       # День 7: SitemapParser
│   │   ├── config.py        # День 7: CrawlerConfig (YAML/JSON)
│   │   └── advanced.py      # День 7: AdvancedCrawler (интеграция)
│   └── demos/               # Демо-скрипты (день 1–7)
├── tests/                   # Тесты (54 шт.)
├── docs/                    # Документация
│   └── architecture.md
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

### В коде

```python
import asyncio
from src.crawler.advanced import AdvancedCrawler
from src.crawler.storage import JSONStorage

async def main():
    async with AdvancedCrawler(
        start_urls=["https://example.com"],
        max_pages=50,
        max_depth=2,
        requests_per_second=2.0,
        storage=JSONStorage("results.jsonl"),
    ) as crawler:
        results = await crawler.crawl()

        stats = crawler.get_stats()
        print(f"Обработано: {stats['total_pages']} страниц")
        print(f"Успешно:    {stats['successful']}")
        print(f"Скорость:   {stats['pages_per_sec']} стр/сек")

        await crawler.export_to_html_report("report.html")

asyncio.run(main())
```

### Из config.yaml

```python
from src.crawler.advanced import AdvancedCrawler

async def main():
    async with AdvancedCrawler.from_config("config.yaml") as crawler:
        await crawler.crawl()

asyncio.run(main())
```

## Запуск тестов

```bash
python -m pytest tests/ -v
```

## Демо по дням

```bash
python src/demos/day1_demo.py   # Параллельный vs последовательный fetch
python src/demos/day2_demo.py   # HTML парсинг и извлечение данных
python src/demos/day3_demo.py   # Очередь и управление конкурентностью
python src/demos/day4_demo.py   # Rate limiting и robots.txt
python src/demos/day5_demo.py   # Автоматические повторы и circuit breaker
python src/demos/day6_demo.py   # Сохранение в JSON / CSV / SQLite
python src/demos/day7_demo.py   # Полная интеграция с отчётом
```

## Технологии

| Библиотека | Назначение |
|---|---|
| `asyncio` | Асинхронный event loop |
| `aiohttp` | Async HTTP-клиент, connection pooling |
| `aiofiles` | Async запись в файлы |
| `aiosqlite` | Async SQLite |
| `beautifulsoup4` + `lxml` | Парсинг HTML |
| `pyyaml` | Конфигурация |
| `pytest` + `pytest-asyncio` | Тестирование |

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
