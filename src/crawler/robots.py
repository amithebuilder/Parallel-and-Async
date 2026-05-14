"""Day 4: robots.txt parser and enforcement."""

import logging
import re
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)


class RobotsParser:
    """Fetch, cache, and enforce robots.txt rules.

    Supports User-agent, Disallow, Allow, and Crawl-delay directives.
    Rules are parsed on demand per user-agent and cached for performance.
    """

    def __init__(self, user_agent: str = "*", session: aiohttp.ClientSession | None = None):
        self._user_agent = user_agent
        self._session = session
        # Raw robots.txt text per domain (domain -> text)
        self._raw_text: dict[str, str] = {}
        # Parsed rules cache: (domain, user_agent) -> rules dict
        self._rules_cache: dict[tuple[str, str], dict] = {}
        self._blocked_count = 0

    # ------------------------------------------------------------------
    # Fetch & parse
    # ------------------------------------------------------------------

    async def fetch_robots(self, base_url: str) -> dict:
        """Fetch and parse robots.txt for the given URL's domain.

        Results are cached; subsequent calls for the same domain are no-ops.
        Returns the parsed rules dict for the configured user-agent.
        """
        parsed = urlparse(base_url)
        domain = parsed.netloc
        cache_key = (domain, self._user_agent)
        if cache_key in self._rules_cache:
            return self._rules_cache[cache_key]

        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        raw_text = ""

        try:
            session = self._session or aiohttp.ClientSession()
            own_session = self._session is None
            try:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        raw_text = await resp.text()
                        logger.info("Loaded robots.txt for %s", domain)
                    else:
                        logger.info("No robots.txt for %s (status %d) — allowing all", domain, resp.status)
            finally:
                if own_session:
                    await session.close()
        except Exception as exc:
            logger.warning("Failed to fetch robots.txt for %s: %s", domain, exc)

        # Store raw text so we can re-parse for other user-agents on demand
        self._raw_text[domain] = raw_text
        rules = self._parse_robots_text_for(raw_text, self._user_agent) if raw_text else {
            "disallow": [], "allow": [], "crawl_delay": None
        }
        self._rules_cache[cache_key] = rules
        return rules

    # ------------------------------------------------------------------
    # Check permission
    # ------------------------------------------------------------------

    def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """Check whether *url* is allowed for *user_agent*.

        Args:
            url:        The URL to check.
            user_agent: The User-agent string to evaluate rules for.
                        Defaults to ``"*"`` (wildcard — matches any agent).
        """
        domain = urlparse(url).netloc
        rules = self._get_rules(domain, user_agent)
        if rules is None:
            return True  # robots.txt not fetched yet — allow

        path = urlparse(url).path or "/"

        # Allow rules checked before Disallow (more-specific allow wins)
        for pattern in rules["allow"]:
            if self._path_matches(path, pattern):
                return True
        for pattern in rules["disallow"]:
            if self._path_matches(path, pattern):
                self._blocked_count += 1
                logger.debug("Blocked by robots.txt: %s", url)
                return False
        return True

    def get_crawl_delay(self, url: str, user_agent: str = "*") -> float:
        """Return the Crawl-delay (seconds) for *url*'s domain and *user_agent*.

        Returns 0.0 if no Crawl-delay directive is set.
        """
        domain = urlparse(url).netloc
        rules = self._get_rules(domain, user_agent) or {}
        return rules.get("crawl_delay") or 0.0

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_rules(self, domain: str, user_agent: str) -> dict | None:
        """Return cached rules for (domain, user_agent), parsing on demand."""
        cache_key = (domain, user_agent)
        if cache_key in self._rules_cache:
            return self._rules_cache[cache_key]
        raw = self._raw_text.get(domain)
        if raw is None:
            return None  # robots.txt not fetched for this domain
        rules = self._parse_robots_text_for(raw, user_agent)
        self._rules_cache[cache_key] = rules
        return rules

    def _parse_robots_text_for(self, text: str, user_agent: str) -> dict:
        """Parse *text* into rules applicable to *user_agent*.

        Blank lines separate user-agent blocks; comments do not end a block.
        """
        rules: dict = {"disallow": [], "allow": [], "crawl_delay": None}
        current_agents: list[str] = []

        for raw_line in text.splitlines():
            stripped = raw_line.strip()

            # Blank line → end of current block
            if not stripped:
                current_agents = []
                continue

            # Comment-only line → skip without ending the current block
            if stripped.startswith("#"):
                continue

            line = stripped.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue

            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                current_agents.append(value)
            elif self._matches_agent(user_agent, current_agents):
                if key == "disallow" and value:
                    rules["disallow"].append(value)
                elif key == "allow" and value:
                    rules["allow"].append(value)
                elif key == "crawl-delay":
                    try:
                        rules["crawl_delay"] = float(value)
                    except ValueError:
                        pass

        return rules

    @staticmethod
    def _matches_agent(user_agent: str, agents: list[str]) -> bool:
        """Return True if *user_agent* matches any entry in *agents*."""
        if not agents:
            return False
        ua_lower = user_agent.lower()
        for agent in agents:
            a = agent.strip().lower()
            if a == "*" or a in ua_lower or ua_lower in a:
                return True
        return False

    @staticmethod
    def _path_matches(path: str, pattern: str) -> bool:
        """Simple robots.txt pattern matching (prefix + optional ``*`` and ``$``)."""
        if pattern.endswith("$"):
            regex = re.escape(pattern[:-1]).replace(r"\*", ".*") + "$"
        else:
            regex = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.match(regex, path))
