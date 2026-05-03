"""Day 2: HTML parsing and structured data extraction."""

import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HTMLParser:
    """Parse HTML content and extract structured data."""

    def __init__(self, parser_backend: str = "lxml"):
        self._backend = parser_backend

    def _make_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, self._backend)

    # ------------------------------------------------------------------
    # Core extraction methods
    # ------------------------------------------------------------------

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract all <a href> links, converting relative to absolute URLs."""
        links: list[str] = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme in ("http", "https"):
                # Remove fragment
                clean = parsed._replace(fragment="").geturl()
                links.append(clean)
        return links

    def extract_text(self, soup: BeautifulSoup, selector: str | None = None) -> str:
        """Extract visible text, optionally scoped by a CSS selector."""
        target = soup.select_one(selector) if selector else soup
        if target is None:
            return ""
        return target.get_text(separator="\n", strip=True)

    def extract_metadata(self, soup: BeautifulSoup) -> dict:
        """Extract page title, description, and keywords from <head>."""
        meta: dict = {}
        title_tag = soup.find("title")
        meta["title"] = title_tag.get_text(strip=True) if title_tag else ""

        desc_tag = soup.find("meta", attrs={"name": "description"})
        meta["description"] = desc_tag["content"].strip() if desc_tag and desc_tag.get("content") else ""

        kw_tag = soup.find("meta", attrs={"name": "keywords"})
        meta["keywords"] = kw_tag["content"].strip() if kw_tag and kw_tag.get("content") else ""

        return meta

    def extract_images(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """Extract all <img> tags with src and alt attributes."""
        images: list[dict] = []
        for img in soup.find_all("img", src=True):
            images.append({
                "src": urljoin(base_url, img["src"]),
                "alt": img.get("alt", ""),
            })
        return images

    def extract_headings(self, soup: BeautifulSoup) -> list[dict]:
        """Extract all heading tags (h1-h6)."""
        headings: list[dict] = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            headings.append({
                "level": int(tag.name[1]),
                "text": tag.get_text(strip=True),
            })
        return headings

    def extract_tables(self, soup: BeautifulSoup) -> list[list[list[str]]]:
        """Extract all <table> data as list of tables, each a list of rows."""
        tables: list[list[list[str]]] = []
        for table in soup.find_all("table"):
            rows: list[list[str]] = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return tables

    def extract_lists(self, soup: BeautifulSoup) -> list[dict]:
        """Extract all <ul>/<ol> lists."""
        lists: list[dict] = []
        for tag in soup.find_all(["ul", "ol"]):
            items = [li.get_text(strip=True) for li in tag.find_all("li", recursive=False)]
            if items:
                lists.append({"type": tag.name, "items": items})
        return lists

    # ------------------------------------------------------------------
    # High-level parse
    # ------------------------------------------------------------------

    async def parse_html(self, html: str, url: str) -> dict:
        """Parse an HTML page and return structured data.

        Returns dict with keys: url, title, text, links, metadata, images,
        headings, tables, lists.
        """
        try:
            soup = self._make_soup(html)
        except Exception as exc:
            logger.warning("Parse error for %s: %s", url, exc)
            return {
                "url": url,
                "title": "",
                "text": "",
                "links": [],
                "metadata": {},
                "images": [],
                "headings": [],
                "tables": [],
                "lists": [],
                "parse_error": str(exc),
            }

        metadata = self.extract_metadata(soup)
        return {
            "url": url,
            "title": metadata["title"],
            "text": self.extract_text(soup),
            "links": self.extract_links(soup, url),
            "metadata": metadata,
            "images": self.extract_images(soup, url),
            "headings": self.extract_headings(soup),
            "tables": self.extract_tables(soup),
            "lists": self.extract_lists(soup),
        }
