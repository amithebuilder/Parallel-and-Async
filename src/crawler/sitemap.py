"""Day 7: Sitemap.xml parser."""

import logging
from urllib.parse import urljoin
from xml.etree import ElementTree

import aiohttp

logger = logging.getLogger(__name__)

# Common XML namespaces in sitemaps
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class SitemapParser:
    """Fetch and parse sitemap.xml files, including sitemap indexes."""

    def __init__(self, session: aiohttp.ClientSession | None = None):
        self._session = session

    async def fetch_sitemap(self, sitemap_url: str) -> list[str]:
        """Fetch sitemap(s) recursively and return all page URLs found."""
        urls: list[str] = []
        await self._process_sitemap(sitemap_url, urls, depth=0)
        logger.info("Sitemap: found %d URLs from %s", len(urls), sitemap_url)
        return urls

    async def _process_sitemap(self, url: str, urls: list[str], depth: int) -> None:
        if depth > 5:
            logger.warning("Sitemap recursion limit reached at %s", url)
            return

        xml_text = await self._fetch(url)
        if xml_text is None:
            return

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            logger.warning("Sitemap parse error for %s: %s", url, exc)
            return

        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag == "sitemapindex":
            # Sitemap index — recurse into child sitemaps
            for sitemap_el in root.findall("sm:sitemap/sm:loc", _NS):
                if sitemap_el.text:
                    await self._process_sitemap(sitemap_el.text.strip(), urls, depth + 1)
            # Also try without namespace
            for sitemap_el in root.findall("sitemap/loc"):
                if sitemap_el.text:
                    await self._process_sitemap(sitemap_el.text.strip(), urls, depth + 1)
        else:
            # Regular sitemap — collect <url><loc> entries
            for loc in root.findall("sm:url/sm:loc", _NS):
                if loc.text:
                    urls.append(loc.text.strip())
            for loc in root.findall("url/loc"):
                if loc.text:
                    urls.append(loc.text.strip())

    async def _fetch(self, url: str) -> str | None:
        session = self._session or aiohttp.ClientSession()
        own_session = self._session is None
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning("Sitemap fetch %s returned %d", url, resp.status)
                return None
        except Exception as exc:
            logger.warning("Sitemap fetch error for %s: %s", url, exc)
            return None
        finally:
            if own_session:
                await session.close()
