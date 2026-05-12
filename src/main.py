"""CLI entry point for the async web crawler."""

import argparse
import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler

from crawler.advanced import AdvancedCrawler
from crawler.config import CrawlerConfig
from crawler.storage import JSONStorage, CSVStorage, SQLiteStorage


def setup_logging(level: str = "INFO", log_file: str = "") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        # Rotate at 10 MB, keep 5 backups
        handlers.append(
            RotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
        )
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Async web crawler with rate limiting, retries, and storage."
    )
    p.add_argument("--urls", nargs="+", help="Start URLs")
    p.add_argument("--config", help="Path to YAML/JSON config file")
    p.add_argument("--max-pages", type=int, default=100)
    p.add_argument("--max-depth", type=int, default=3)
    p.add_argument("--max-concurrent", type=int, default=10)
    p.add_argument("--rate-limit", type=float, default=2.0,
                   help="Requests per second")
    # BooleanOptionalAction gives --respect-robots / --no-respect-robots
    p.add_argument("--respect-robots", action=argparse.BooleanOptionalAction,
                   default=True, help="Respect robots.txt (default: on)")
    p.add_argument("--same-domain", action=argparse.BooleanOptionalAction,
                   default=True, help="Only crawl same domain (default: on)")
    p.add_argument("--user-agent", default="AsyncCrawler/1.0")
    p.add_argument("--output", help="JSON Lines output file")
    p.add_argument("--output-csv", help="CSV output file")
    p.add_argument("--output-sqlite", help="SQLite output file")
    p.add_argument("--report", help="HTML report output file")
    p.add_argument("--use-sitemap", action="store_true")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--log-file", default="")
    return p


async def run(args: argparse.Namespace) -> None:
    # Build from config file or CLI args
    if args.config:
        crawler = AdvancedCrawler.from_config(args.config)
        # args.urls (if provided) will override config start_urls via crawl(start_urls=)
    else:
        storages = []
        if args.output:
            storages.append(JSONStorage(args.output))
        if args.output_csv:
            storages.append(CSVStorage(args.output_csv))
        if args.output_sqlite:
            storages.append(SQLiteStorage(args.output_sqlite))

        from crawler.advanced import MultiStorage
        storage = (
            storages[0] if len(storages) == 1
            else (MultiStorage(storages) if storages else None)
        )

        crawler = AdvancedCrawler(
            start_urls=args.urls or [],
            max_pages=args.max_pages,
            max_depth=args.max_depth,
            max_concurrent=args.max_concurrent,
            requests_per_second=args.rate_limit,
            respect_robots=args.respect_robots,
            same_domain_only=args.same_domain,
            user_agent=args.user_agent,
            storage=storage,
            use_sitemap=args.use_sitemap,
        )

    async with crawler:
        results = await crawler.crawl(start_urls=args.urls)

        stats = crawler.get_stats()
        print(f"\n{'='*50}")
        print(f"Crawl complete!")
        print(f"  Total pages:   {stats['total_pages']}")
        print(f"  Successful:    {stats['successful']}")
        print(f"  Failed:        {stats['failed']}")
        print(f"  Pages/sec:     {stats['pages_per_sec']}")
        print(f"  Elapsed:       {stats['elapsed_sec']}s")
        print(f"{'='*50}")

        if args.report:
            await crawler.export_to_html_report(args.report)
            print(f"HTML report: {args.report}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.urls and not args.config:
        parser.error("Provide --urls or --config")

    # When using a config file, apply its log settings unless CLI flags override
    log_level = args.log_level
    log_file = args.log_file
    if args.config:
        try:
            cfg = CrawlerConfig.from_file(args.config)
            if log_level == "INFO":        # CLI default — prefer config value
                log_level = cfg.log_level
            if not log_file:               # CLI default — prefer config value
                log_file = cfg.log_file
        except Exception:
            pass  # bad config path handled later in run()

    setup_logging(log_level, log_file)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
