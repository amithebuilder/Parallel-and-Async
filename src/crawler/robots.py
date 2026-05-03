"""Day 4: robots.txt parser and enforcement."""

import asyncio
import logging
import re
from urllib.parse import urlparse, urljoin

import aiohttp

logger = logging.getLogger(__name__)


class RobotsParser:
    """Fetch, cache, and enforce robots.txt rules.

    Supports User-agent, Disallow, Allow, and Crawl-delay directives.
    """

    def __init__(self, user_agent: str = "*", session: aiohttp.ClientSession | None = None):
        self._user_agent = user_agent
        self._session = session
        self._cache: dict[str, dict] = {}  # domain -> parsed rules
        self._blocked_count = 0

    # ------------------------------------------------------------------
    # Fetch & parse
    # ------------------------------------------------------------------

    async def fetch_robots(self, base_url: str) -> dict:
        """Fetch and parse robots.txt for the given URL's domain."""
        parsed = urlparse(base_url)
        domain = parsed.netloc
        if domain in self._cache:
            return self._cache[domain]

        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        rules: dict = {"disallow": [], "allow": [], "crawl_delay": None}

        try:
            session = self._session or aiohttp.ClientSession()
            own_session = self._session is None
            try:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        rules = self._parse_robots_text(text)
                        logger.info("Loaded robots.txt for %s", domain)
                    else:
                        logger.info("No robots.txt for %s (status %d) — allowing all", domain, resp.status)
            finally:
                if own_session:
                    await session.close()
        except Exception as exc:
            logger.warning("Failed to fetch robots.txt for %s: %s", domain, exc)

        self._cache[domain] = rules
        return rules

    def _parse_robots_text(self, text: str) -> dict:
        """Parse robots.txt content into structured rules."""
        rules: dict = {"disallow": [], "allow": [], "crawl_delay": None}
        current_agents: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                current_agents.append(value)
            elif self._agent_matches(current_agents):
                if key == "disallow" and value:
                    rules["disallow"].append(value)
                elif key == "allow" and value:
                    rules["allow"].append(value)
                elif key == "crawl-delay":
                    try:
                        rules["crawl_delay"] = float(value)
                    except ValueError:
                        pass
                # Reset agents for next block
            if key != "user-agent":
                current_agents = []

        return rules

    def _agent_matches(self, agents: list[str]) -> bool:
        if not agents:
            return False
        ua_lower = self._user_agent.lower()
        for agent in agents:
            a = agent.strip().lower()
            if a == "*" or a in ua_lower or ua_lower in a:
                return True
        return False

    # ------------------------------------------------------------------
    # Check permission
    # ------------------------------------------------------------------

    def can_fetch(self, url: str) -> bool:
        """Check whether *url* is allowed according to cached robots.txt rules."""
        domain = urlparse(url).netloc
        rules = self._cache.get(domain)
        if rules is None:
            return True  # not fetched yet — allow

        path = urlparse(url).path or "/"

        # Allow rules take precedence over Disallow for the same specificity,
        # but a simple implementation: check allows first (more specific wins).
        for pattern in rules["allow"]:
            if self._path_matches(path, pattern):
                return True
        for pattern in rules["disallow"]:
            if self._path_matches(path, pattern):
                self._blocked_count += 1
                logger.debug("Blocked by robots.txt: %s", url)
                return False
        return True

    def get_crawl_delay(self, url: str) -> float:
        """Return Crawl-delay for the domain of *url*, or 0.0."""
        domain = urlparse(url).netloc
        rules = self._cache.get(domain, {})
        return rules.get("crawl_delay") or 0.0

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _path_matches(path: str, pattern: str) -> bool:
        """Simple robots.txt pattern matching (prefix + optional * and $)."""
        if pattern.endswith("$"):
            regex = re.escape(pattern[:-1]).replace(r"\*", ".*") + "$"
        else:
            regex = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.match(regex, path))
