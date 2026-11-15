"""
Robots.txt parser and checker module.
Fetches, caches, and evaluates robots.txt compliance for crawler tasks.
"""

import logging
import sys
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
import urllib.robotparser

import httpx

logger = logging.getLogger("cli_agent.robots")


class RobotsChecker:
    """
    Manages fetching, caching, and evaluating robots.txt policies for hostnames.
    """

    def __init__(self, user_agent: str = "CLI-Agent-AI/1.0"):
        self.user_agent = user_agent
        # Cache mapping: hostname -> (RobotFileParser, crawl_delay_seconds)
        self._cache: Dict[str, Tuple[Optional[urllib.robotparser.RobotFileParser], Optional[float]]] = {}

    async def get_parser_for_url(
        self, url: str, client: httpx.AsyncClient, timeout: float = 10.0
    ) -> Tuple[Optional[urllib.robotparser.RobotFileParser], Optional[float]]:
        """
        Retrieves or fetches the RobotFileParser and crawl-delay for a given URL's origin.
        """
        parsed = urlparse(url)
        if not parsed.hostname or not parsed.scheme:
            return None, None

        host_key = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port and parsed.port not in (80, 443):
            host_key += f":{parsed.port}"

        if host_key in self._cache:
            return self._cache[host_key]

        robots_url = f"{host_key}/robots.txt"
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        crawl_delay: Optional[float] = None

        try:
            sys.stderr.write(f"[INFO] Fetching robots.txt: {robots_url}\n")
            sys.stderr.flush()
            response = await client.get(robots_url, timeout=timeout, follow_redirects=True)

            if response.status_code == 200:
                content = response.text
                parser.parse(content.splitlines())
                try:
                    crawl_delay = parser.crawl_delay(self.user_agent) or parser.crawl_delay("*")
                except Exception:
                    crawl_delay = None
            elif response.status_code in (401, 403):
                # Forbidden or unauthorized robots.txt implies restrictions
                sys.stderr.write(f"[WARN] robots.txt returned status {response.status_code}. Site may be restricted.\n")
                sys.stderr.flush()
                # Empty parser will disallow if rules cannot be verified, or allow only root
            elif response.status_code == 404:
                # 404 Not Found means no crawling restrictions exist
                parser = None
            else:
                parser = None

        except (httpx.TimeoutException, httpx.RequestError) as exc:
            sys.stderr.write(f"[WARN] Unable to reach robots.txt at {robots_url}: {str(exc)}. Proceeding cautiously.\n")
            sys.stderr.flush()
            parser = None
        except Exception as exc:
            sys.stderr.write(f"[WARN] Unexpected error fetching robots.txt: {str(exc)}\n")
            sys.stderr.flush()
            parser = None

        self._cache[host_key] = (parser, crawl_delay)
        return parser, crawl_delay

    async def is_allowed(
        self, url: str, client: httpx.AsyncClient, timeout: float = 10.0
    ) -> bool:
        """
        Checks whether the crawler is permitted to fetch the specified URL according to robots.txt.
        """
        parser, _ = await self.get_parser_for_url(url, client, timeout=timeout)
        if parser is None:
            # No robots.txt or 404 allows fetching
            return True

        # Check for specific user-agent first, then wildcard '*'
        can_fetch = parser.can_fetch(self.user_agent, url) or parser.can_fetch("*", url)
        return bool(can_fetch)

    def get_cached_delay(self, url: str) -> Optional[float]:
        """Returns cached crawl delay for URL hostname if available."""
        parsed = urlparse(url)
        if not parsed.hostname or not parsed.scheme:
            return None
        host_key = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port and parsed.port not in (80, 443):
            host_key += f":{parsed.port}"
        if host_key in self._cache:
            return self._cache[host_key][1]
        return None
