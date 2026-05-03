"""Day 7: Crawler statistics collection and HTML report export."""

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

import aiofiles

logger = logging.getLogger(__name__)


class CrawlerStats:
    """Collect and aggregate crawling statistics."""

    def __init__(self):
        self._start_time: float | None = None
        self._end_time: float | None = None
        self.total_pages = 0
        self.successful = 0
        self.failed = 0
        self.status_codes: Counter = Counter()
        self.domains: Counter = Counter()
        self.errors_by_type: Counter = Counter()
        self.bytes_downloaded = 0
        self._page_times: list[float] = []

    def start(self) -> None:
        self._start_time = time.monotonic()

    def stop(self) -> None:
        self._end_time = time.monotonic()

    @property
    def elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        end = self._end_time or time.monotonic()
        return end - self._start_time

    @property
    def pages_per_sec(self) -> float:
        e = self.elapsed
        return self.total_pages / e if e > 0 else 0.0

    def record_success(self, url: str, status_code: int, size: int, duration: float) -> None:
        self.total_pages += 1
        self.successful += 1
        self.status_codes[status_code] += 1
        from urllib.parse import urlparse
        self.domains[urlparse(url).netloc] += 1
        self.bytes_downloaded += size
        self._page_times.append(duration)

    def record_failure(self, url: str, error_type: str) -> None:
        self.total_pages += 1
        self.failed += 1
        self.errors_by_type[error_type] += 1
        from urllib.parse import urlparse
        self.domains[urlparse(url).netloc] += 1

    def summary(self) -> dict:
        avg_time = (
            sum(self._page_times) / len(self._page_times) if self._page_times else 0.0
        )
        return {
            "total_pages": self.total_pages,
            "successful": self.successful,
            "failed": self.failed,
            "elapsed_sec": round(self.elapsed, 2),
            "pages_per_sec": round(self.pages_per_sec, 2),
            "bytes_downloaded": self.bytes_downloaded,
            "avg_page_time_sec": round(avg_time, 3),
            "status_codes": dict(self.status_codes.most_common()),
            "top_domains": dict(self.domains.most_common(20)),
            "errors_by_type": dict(self.errors_by_type.most_common()),
        }

    async def export_to_json(self, filepath: str) -> None:
        data = self.summary()
        data["exported_at"] = datetime.now(timezone.utc).isoformat()
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        logger.info("Stats exported to %s", filepath)

    async def export_to_html_report(self, filepath: str) -> None:
        s = self.summary()

        status_rows = "\n".join(
            f"<tr><td>{code}</td><td>{cnt}</td></tr>"
            for code, cnt in sorted(s["status_codes"].items())
        )
        domain_rows = "\n".join(
            f"<tr><td>{d}</td><td>{cnt}</td></tr>"
            for d, cnt in s["top_domains"].items()
        )
        error_rows = "\n".join(
            f"<tr><td>{t}</td><td>{cnt}</td></tr>"
            for t, cnt in s["errors_by_type"].items()
        )

        html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Crawler Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f5f5f5; }}
  h1 {{ color: #333; }}
  .card {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin: 1rem 0;
           box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
  .metric {{ text-align: center; }}
  .metric .value {{ font-size: 2rem; font-weight: bold; color: #2563eb; }}
  .metric .label {{ color: #666; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .5rem; border-bottom: 1px solid #eee; }}
  th {{ background: #f0f0f0; }}
</style>
</head>
<body>
<h1>Async Crawler Report</h1>
<div class="card grid">
  <div class="metric"><div class="value">{s['total_pages']}</div><div class="label">Total pages</div></div>
  <div class="metric"><div class="value">{s['successful']}</div><div class="label">Successful</div></div>
  <div class="metric"><div class="value">{s['failed']}</div><div class="label">Failed</div></div>
  <div class="metric"><div class="value">{s['pages_per_sec']}</div><div class="label">Pages/sec</div></div>
  <div class="metric"><div class="value">{s['elapsed_sec']}s</div><div class="label">Elapsed</div></div>
  <div class="metric"><div class="value">{s['bytes_downloaded']:,}</div><div class="label">Bytes</div></div>
</div>

<div class="card">
<h2>Status codes</h2>
<table><tr><th>Code</th><th>Count</th></tr>
{status_rows}
</table></div>

<div class="card">
<h2>Top domains</h2>
<table><tr><th>Domain</th><th>Pages</th></tr>
{domain_rows}
</table></div>

<div class="card">
<h2>Errors</h2>
<table><tr><th>Type</th><th>Count</th></tr>
{error_rows}
</table></div>

<p style="color:#999;font-size:.85rem;">Generated {datetime.now(timezone.utc).isoformat()}</p>
</body></html>"""

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(html)
        logger.info("HTML report exported to %s", filepath)
