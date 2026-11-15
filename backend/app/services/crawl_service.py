"""
Asynchronous website crawling service.
Implements controlled breadth-first search (BFS) with strict security boundaries,
robots.txt enforcement, redirect revalidation, response size limits, and polite delays.
All diagnostics and progress logs are written strictly to sys.stderr.
"""

import asyncio
from collections import deque
import logging
import sys
import time
from typing import Deque, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from app.schemas.crawl_schema import CrawlError, CrawlResult, PageCrawlResult, WebsiteSummary
from app.security.robots_checker import RobotsChecker
from app.security.url_validator import URLSecurityValidator
from app.services.content_extractor import ContentExtractor

logger = logging.getLogger("cli_agent.crawler")

# Maximum permitted payload size per page (5 MB)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_USER_AGENT = "CLI-Agent-AI/1.0 (+https://github.com/buildsprint/cli-agent-ai)"


class CrawlService:
    """
    Executes controlled web crawling operations with anti-SSRF protections.
    """

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.user_agent = user_agent
        self.robots_checker = RobotsChecker(user_agent=user_agent)

    async def crawl(
        self,
        target_url: str,
        max_pages: int = 5,
        max_depth: int = 1,
        timeout: float = 15.0,
    ) -> CrawlResult:
        """
        Crawls target_url using BFS up to max_pages and max_depth.
        Returns a complete CrawlResult schema object.
        """
        start_time = time.perf_counter()

        # Enforce strict bounds on parameters
        max_pages = max(1, min(max_pages, 10))
        max_depth = max(0, min(max_depth, 2))

        sys.stderr.write(f"[INFO] Initializing crawl: target={target_url}, max_pages={max_pages}, max_depth={max_depth}, timeout={timeout}s\n")
        sys.stderr.flush()

        # Initial security validation of target URL
        is_valid, reason, normalized_target = URLSecurityValidator.validate_url(target_url)
        if not is_valid or not normalized_target:
            sys.stderr.write(f"[ERROR] Target URL rejected: {reason}\n")
            sys.stderr.flush()
            duration = round(time.perf_counter() - start_time, 2)
            return CrawlResult(
                success=False,
                status="failed",
                target_url=target_url,
                pages_crawled=0,
                pages_failed=1,
                execution_time_seconds=duration,
                website_summary=WebsiteSummary(),
                pages=[],
                errors=[CrawlError(url=target_url, error_type="SecurityValidationError", message=reason)],
            )

        visited: Set[str] = set()
        queue: Deque[Tuple[str, int]] = deque([(normalized_target, 0)])
        crawled_pages: List[PageCrawlResult] = []
        errors: List[CrawlError] = []

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        # Use an AsyncClient that does NOT automatically follow redirects
        # (Redirects are verified manually to prevent SSRF via open redirectors)
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=False) as client:
            while queue and len(crawled_pages) < max_pages:
                current_url, depth = queue.popleft()

                # Normalize URL representation for visited comparison
                norm_key = current_url.rstrip("/")
                if norm_key in visited:
                    continue
                visited.add(norm_key)

                # Check hostname boundary
                if not URLSecurityValidator.is_same_hostname(normalized_target, current_url):
                    sys.stderr.write(f"[DEBUG] Skipping off-host URL: {current_url}\n")
                    continue

                # Check robots.txt permissions
                allowed_by_robots = await self.robots_checker.is_allowed(current_url, client, timeout=timeout)
                if not allowed_by_robots:
                    sys.stderr.write(f"[WARN] robots.txt disallowed: {current_url}\n")
                    sys.stderr.flush()
                    errors.append(CrawlError(
                        url=current_url,
                        error_type="BlockedByRobots",
                        message="URL is disallowed by target website robots.txt rules."
                    ))
                    continue

                # Polite crawl delay
                delay = self.robots_checker.get_cached_delay(current_url) or 0.2
                if crawled_pages:
                    await asyncio.sleep(min(delay, 2.0))

                sys.stderr.write(f"[INFO] Fetching [{len(crawled_pages) + 1}/{max_pages}] (Depth {depth}): {current_url}\n")
                sys.stderr.flush()

                # Fetch and parse page
                page_result, error = await self._fetch_page(client, current_url, normalized_target, timeout)

                if error:
                    errors.append(error)
                elif page_result:
                    crawled_pages.append(page_result)

                    # Add internal links to queue if within max_depth
                    if depth < max_depth:
                        for link in page_result.internal_links:
                            link_norm = link.rstrip("/")
                            if link_norm not in visited and all(item[0].rstrip("/") != link_norm for item in queue):
                                queue.append((link, depth + 1))

        duration = round(time.perf_counter() - start_time, 2)
        pages_crawled_count = len(crawled_pages)
        pages_failed_count = len(errors)

        if pages_crawled_count == 0:
            status = "failed"
            success = False
        elif pages_failed_count > 0:
            status = "partial"
            success = True
        else:
            status = "completed"
            success = True

        sys.stderr.write(f"[INFO] Crawl completed in {duration}s: {pages_crawled_count} crawled, {pages_failed_count} failed\n")
        sys.stderr.flush()

        # Build synthesized website summary
        summary = self._build_website_summary(crawled_pages)

        return CrawlResult(
            success=success,
            status=status,
            target_url=normalized_target,
            pages_crawled=pages_crawled_count,
            pages_failed=pages_failed_count,
            execution_time_seconds=duration,
            website_summary=summary,
            pages=crawled_pages,
            errors=errors,
        )

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        base_target_url: str,
        timeout: float,
        max_redirect_hops: int = 5,
    ) -> Tuple[Optional[PageCrawlResult], Optional[CrawlError]]:
        """
        Safely fetches a single URL, resolving and validating redirects manually.
        """
        current_url = url
        hops = 0

        while hops < max_redirect_hops:
            hops += 1

            # Validate each hop before issuing request
            is_valid, reason, norm_url = URLSecurityValidator.validate_url(current_url)
            if not is_valid or not norm_url:
                sys.stderr.write(f"[WARN] Redirect to unsafe destination aborted: {current_url} ({reason})\n")
                sys.stderr.flush()
                return None, CrawlError(url=current_url, error_type="SSRFRedirectDenied", message=reason)

            try:
                response = await client.get(norm_url, timeout=timeout)
            except httpx.TimeoutException:
                sys.stderr.write(f"[ERROR] Timeout fetching {norm_url}\n")
                sys.stderr.flush()
                return None, CrawlError(url=norm_url, error_type="Timeout", message=f"Request timed out after {timeout} seconds")
            except httpx.ConnectError as exc:
                sys.stderr.write(f"[ERROR] Connection failed for {norm_url}: {str(exc)}\n")
                sys.stderr.flush()
                return None, CrawlError(url=norm_url, error_type="ConnectionError", message="Failed to establish connection to host")
            except httpx.HTTPError as exc:
                sys.stderr.write(f"[ERROR] HTTP error for {norm_url}: {str(exc)}\n")
                sys.stderr.flush()
                return None, CrawlError(url=norm_url, error_type="HTTPError", message=str(exc))
            except Exception as exc:
                sys.stderr.write(f"[ERROR] Unexpected fetch exception: {str(exc)}\n")
                sys.stderr.flush()
                return None, CrawlError(url=norm_url, error_type="UnexpectedError", message=str(exc))

            # Handle HTTP 3xx Redirects manually
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    return None, CrawlError(
                        url=norm_url,
                        error_type="InvalidRedirect",
                        message="Redirect response missing Location header",
                        status_code=response.status_code
                    )

                next_url = urljoin(norm_url, location)

                # Ensure redirect stays on same hostname
                if not URLSecurityValidator.is_same_hostname(base_target_url, next_url):
                    sys.stderr.write(f"[WARN] Redirect left target domain: {next_url}\n")
                    sys.stderr.flush()
                    return None, CrawlError(
                        url=norm_url,
                        error_type="CrossDomainRedirect",
                        message=f"Redirect to external host '{urlparse(next_url).hostname}' denied.",
                        status_code=response.status_code
                    )

                current_url = next_url
                continue

            # Handle Non-200 Status Codes
            if response.status_code != 200:
                sys.stderr.write(f"[WARN] HTTP {response.status_code} on {norm_url}\n")
                sys.stderr.flush()
                return None, CrawlError(
                    url=norm_url,
                    error_type="HTTPStatusError",
                    message=f"Server returned HTTP status {response.status_code}",
                    status_code=response.status_code
                )

            # Enforce Content-Type validation (HTML only)
            content_type = response.headers.get("Content-Type", "").lower()
            if not ("text/html" in content_type or "application/xhtml+xml" in content_type):
                sys.stderr.write(f"[WARN] Unsupported Content-Type '{content_type}' on {norm_url}\n")
                sys.stderr.flush()
                return None, CrawlError(
                    url=norm_url,
                    error_type="UnsupportedContentType",
                    message=f"Expected HTML, received '{content_type}'",
                    status_code=200
                )

            # Enforce payload size limit
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                sys.stderr.write(f"[ERROR] Response size exceeds {MAX_RESPONSE_BYTES} bytes\n")
                sys.stderr.flush()
                return None, CrawlError(
                    url=norm_url,
                    error_type="PayloadTooLarge",
                    message="Response exceeds 5MB payload limit",
                    status_code=200
                )

            html_body = response.text
            if len(html_body.encode("utf-8")) > MAX_RESPONSE_BYTES:
                html_body = html_body[:MAX_RESPONSE_BYTES]

            # Parse and sanitize HTML content
            try:
                page_result = ContentExtractor.extract_page(
                    html=html_body,
                    page_url=norm_url,
                    base_target_url=base_target_url,
                    status_code=response.status_code
                )
                return page_result, None
            except Exception as exc:
                sys.stderr.write(f"[ERROR] Extraction failed for {norm_url}: {str(exc)}\n")
                sys.stderr.flush()
                return None, CrawlError(url=norm_url, error_type="ExtractionError", message=f"Failed to parse HTML: {str(exc)}")

        return None, CrawlError(url=url, error_type="TooManyRedirects", message="Exceeded 5 redirect hops")

    def _build_website_summary(self, pages: List[PageCrawlResult]) -> WebsiteSummary:
        """
        Synthesizes a high-level summary across all crawled pages.
        """
        if not pages:
            return WebsiteSummary()

        root_page = pages[0]
        title = root_page.title or f"Website at {urlparse(root_page.url).hostname}"
        description = root_page.description

        # Aggregate headings
        collected_headings: List[str] = []
        for page in pages:
            for h in page.headings:
                if h.text not in collected_headings:
                    collected_headings.append(h.text)
                if len(collected_headings) >= 12:
                    break
            if len(collected_headings) >= 12:
                break

        # Aggregate main paragraphs
        collected_content: List[str] = []
        for page in pages:
            for p in page.main_content:
                if p not in collected_content:
                    collected_content.append(p)
                if len(collected_content) >= 8:
                    break
            if len(collected_content) >= 8:
                break

        if not description and collected_content:
            description = collected_content[0][:200] + ("..." if len(collected_content[0]) > 200 else "")

        return WebsiteSummary(
            title=title,
            description=description,
            headings=collected_headings,
            main_content=collected_content,
        )


# Global singleton crawl service
crawl_service = CrawlService()
