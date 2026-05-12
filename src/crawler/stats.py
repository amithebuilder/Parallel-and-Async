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

    # ------------------------------------------------------------------
    # Internal chart helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _bar_chart_svg(data: dict, title: str, color: str = "#2563eb") -> str:
        """Return an inline SVG horizontal bar chart for *data* {label: value}."""
        if not data:
            return f"<p style='color:#999'>No data for {title}</p>"

        items = list(data.items())[:15]  # cap at 15 bars
        max_val = max(v for _, v in items) or 1
        bar_h, gap, left_w, right_w = 28, 6, 180, 60
        chart_w = 500
        chart_h = len(items) * (bar_h + gap) + 10

        bars = []
        for i, (label, val) in enumerate(items):
            y = i * (bar_h + gap)
            bar_w = int((val / max_val) * (chart_w - left_w - right_w))
            safe_label = str(label)[:28]
            bars.append(
                f'<text x="{left_w - 6}" y="{y + bar_h // 2 + 5}" '
                f'text-anchor="end" font-size="12" fill="#444">{safe_label}</text>'
                f'<rect x="{left_w}" y="{y}" width="{bar_w}" height="{bar_h}" '
                f'fill="{color}" rx="3"/>'
                f'<text x="{left_w + bar_w + 6}" y="{y + bar_h // 2 + 5}" '
                f'font-size="12" fill="#333">{val}</text>'
            )

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{chart_w}" height="{chart_h}" style="max-width:100%">'
            + "\n".join(bars)
            + "</svg>"
        )

    @staticmethod
    def _pie_chart_svg(data: dict, title: str) -> str:
        """Return an inline SVG donut/pie chart for *data* {label: value}."""
        if not data:
            return f"<p style='color:#999'>No data for {title}</p>"

        palette = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
                   "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4f46e5"]
        items = list(data.items())
        total = sum(v for _, v in items) or 1
        cx, cy, r, ir = 120, 120, 100, 55
        w, h = 380, 240

        def arc_path(start_angle: float, end_angle: float) -> str:
            import math
            x1 = cx + r * math.cos(start_angle)
            y1 = cy + r * math.sin(start_angle)
            x2 = cx + r * math.cos(end_angle)
            y2 = cy + r * math.sin(end_angle)
            xi1 = cx + ir * math.cos(start_angle)
            yi1 = cy + ir * math.sin(start_angle)
            xi2 = cx + ir * math.cos(end_angle)
            yi2 = cy + ir * math.sin(end_angle)
            large = 1 if (end_angle - start_angle) > 3.14159 else 0
            return (f"M {xi1:.1f} {yi1:.1f} L {x1:.1f} {y1:.1f} "
                    f"A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} "
                    f"L {xi2:.1f} {yi2:.1f} "
                    f"A {ir} {ir} 0 {large} 0 {xi1:.1f} {yi1:.1f} Z")

        import math
        angle = -math.pi / 2
        slices, legends = [], []
        for i, (label, val) in enumerate(items):
            sweep = 2 * math.pi * val / total
            color = palette[i % len(palette)]
            slices.append(
                f'<path d="{arc_path(angle, angle + sweep)}" fill="{color}"/>'
            )
            pct = round(100 * val / total, 1)
            safe_label = str(label)[:20]
            ly = 20 + i * 20
            legends.append(
                f'<rect x="250" y="{ly - 12}" width="14" height="14" fill="{color}" rx="2"/>'
                f'<text x="270" y="{ly}" font-size="12" fill="#444">'
                f'{safe_label} ({pct}%)</text>'
            )
            angle += sweep

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'style="max-width:100%">'
            + "\n".join(slices)
            + "\n".join(legends)
            + "</svg>"
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

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
        ) or "<tr><td colspan='2' style='color:#999'>No errors</td></tr>"

        # Charts
        status_pie = self._pie_chart_svg(s["status_codes"], "Status codes")
        domain_bar = self._bar_chart_svg(s["top_domains"], "Top domains", "#16a34a")
        error_bar  = self._bar_chart_svg(s["errors_by_type"], "Errors", "#dc2626")

        html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Crawler Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f5f5f5; }}
  h1 {{ color: #333; }}
  h2 {{ color: #444; margin-top: 0; }}
  .card {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin: 1rem 0;
           box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
  .metric {{ text-align: center; }}
  .metric .value {{ font-size: 2rem; font-weight: bold; color: #2563eb; }}
  .metric .label {{ color: #666; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
  th, td {{ text-align: left; padding: .5rem; border-bottom: 1px solid #eee; }}
  th {{ background: #f0f0f0; }}
  .chart-row {{ display: flex; flex-wrap: wrap; gap: 2rem; align-items: flex-start; }}
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
  <h2>Status codes distribution</h2>
  <div class="chart-row">
    {status_pie}
    <table style="max-width:220px">
      <tr><th>Code</th><th>Count</th></tr>
      {status_rows}
    </table>
  </div>
</div>

<div class="card">
  <h2>Top domains</h2>
  {domain_bar}
  <table><tr><th>Domain</th><th>Pages</th></tr>
  {domain_rows}
  </table>
</div>

<div class="card">
  <h2>Errors by type</h2>
  {error_bar}
  <table><tr><th>Type</th><th>Count</th></tr>
  {error_rows}
  </table>
</div>

<p style="color:#999;font-size:.85rem;">Generated {datetime.now(timezone.utc).isoformat()}</p>
</body></html>"""

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(html)
        logger.info("HTML report exported to %s", filepath)
