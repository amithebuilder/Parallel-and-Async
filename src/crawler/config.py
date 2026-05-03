"""Day 7: YAML/JSON configuration support."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CrawlerConfig:
    """All configurable parameters for the AdvancedCrawler."""

    # URLs
    start_urls: list[str] = field(default_factory=list)

    # Crawl limits
    max_pages: int = 100
    max_depth: int = 3
    max_concurrent: int = 10
    per_domain_limit: int = 3

    # Timeouts
    timeout_connect: float = 10.0
    timeout_read: float = 30.0
    timeout_total: float = 60.0

    # Rate limiting
    requests_per_second: float = 2.0
    min_delay: float = 0.0
    jitter: float = 0.0

    # Politeness
    respect_robots: bool = True
    user_agent: str = "AsyncCrawler/1.0"

    # Retry
    max_retries: int = 3
    backoff_factor: float = 2.0

    # URL filtering
    same_domain_only: bool = True
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)

    # Storage
    output_json: str = ""
    output_csv: str = ""
    output_sqlite: str = ""

    # Logging
    log_file: str = ""
    log_level: str = "INFO"

    # Sitemap
    use_sitemap: bool = False

    @classmethod
    def from_file(cls, path: str) -> "CrawlerConfig":
        """Load config from a YAML or JSON file."""
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)
        logger.info("Loaded config from %s", path)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)
