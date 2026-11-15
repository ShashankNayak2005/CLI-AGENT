"""
HTML content extraction service using BeautifulSoup4.
Extracts title, meta description, headings, main paragraphs, and internal/external links
while strictly eliminating scripts, styles, navigation, footers, headers, and ads.
"""

from datetime import datetime, timezone
import re
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.schemas.crawl_schema import HeadingItem, PageCrawlResult
from app.security.url_validator import URLSecurityValidator


# Tags completely discarded before text parsing
DISALLOWED_TAGS = {
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "button",
    "svg",
    "iframe",
    "object",
    "embed",
    "canvas",
    "menu",
    "dialog",
}

# Regex to detect ad/banner/cookie classes and ids
AD_PATTERN = re.compile(r"(ad|ads|advertisement|banner|cookie|popup|modal|tracker|share|social)", re.IGNORECASE)


class ContentExtractor:
    """
    Parses and sanitizes HTML content into structured page data.
    """

    @classmethod
    def extract_page(cls, html: str, page_url: str, base_target_url: str, status_code: int = 200) -> PageCrawlResult:
        """
        Parses raw HTML and returns a sanitized PageCrawlResult.
        """
        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Language before stripping tags
        language = None
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            language = str(html_tag["lang"]).strip()
        else:
            meta_lang = soup.find("meta", attrs={"http-equiv": re.compile(r"content-language", re.I)})
            if meta_lang and meta_lang.get("content"):
                language = str(meta_lang["content"]).strip()

        # 2. Extract Links before stripping nav/footer tags
        internal_links, external_links = cls._extract_links(soup, page_url, base_target_url)

        # 3. Extract Meta Description & Title
        title = cls._extract_title(soup)
        description = cls._extract_description(soup)

        # 4. Decompose Disallowed Elements
        for tag in soup.find_all(list(DISALLOWED_TAGS)):
            tag.decompose()

        # Also remove elements with prominent ad / banner classes or ids
        for tag in soup.find_all(True, attrs={"class": AD_PATTERN}):
            tag.decompose()
        for tag in soup.find_all(True, attrs={"id": AD_PATTERN}):
            tag.decompose()

        # 5. Extract Headings (H1, H2, H3)
        headings = cls._extract_headings(soup)

        # 6. Extract Main Content Paragraphs
        main_content = cls._extract_main_content(soup)

        # 7. Word Count Calculation
        word_count = sum(len(p.split()) for p in main_content)

        crawled_at = datetime.now(timezone.utc).isoformat()

        return PageCrawlResult(
            url=page_url,
            status_code=status_code,
            title=title,
            description=description,
            language=language,
            headings=headings,
            main_content=main_content,
            internal_links=internal_links,
            external_links=external_links,
            word_count=word_count,
            crawled_at=crawled_at,
        )

    @classmethod
    def _extract_title(cls, soup: BeautifulSoup) -> str:
        """Extracts page title, falling back to OpenGraph title."""
        if soup.title and soup.title.string:
            text = soup.title.string.strip()
            if text:
                return text

        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            return str(og_title["content"]).strip()

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return ""

    @classmethod
    def _extract_description(cls, soup: BeautifulSoup) -> str:
        """Extracts meta description tag or OpenGraph description."""
        meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        if meta_desc and meta_desc.get("content"):
            return str(meta_desc["content"]).strip()

        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            return str(og_desc["content"]).strip()

        return ""

    @classmethod
    def _extract_headings(cls, soup: BeautifulSoup) -> List[HeadingItem]:
        """Extracts H1, H2, and H3 tags in order."""
        headings: List[HeadingItem] = []
        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = tag.get_text(separator=" ", strip=True)
            # Filter empty or noisy headings
            if text and len(text) <= 300:
                clean_text = " ".join(text.split())
                headings.append(HeadingItem(level=tag.name.lower(), text=clean_text))
        return headings

    @classmethod
    def _extract_main_content(cls, soup: BeautifulSoup) -> List[str]:
        """
        Extracts substantive text paragraphs from <p>, <article>, and main content blocks.
        """
        paragraphs: List[str] = []
        seen: Set[str] = set()

        # Prioritize main or article containers if available
        container = soup.find("main") or soup.find("article") or soup.body or soup

        for p_tag in container.find_all(["p", "li"]):
            text = p_tag.get_text(separator=" ", strip=True)
            clean_text = " ".join(text.split())

            # Filter out short snippets, boilerplate, or duplicates
            if len(clean_text) >= 20 and clean_text not in seen:
                seen.add(clean_text)
                paragraphs.append(clean_text)

        # Fallback if no <p> or <li> matched
        if not paragraphs:
            raw_text = container.get_text(separator="\n", strip=True)
            for line in raw_text.splitlines():
                clean_line = " ".join(line.split())
                if len(clean_line) >= 25 and clean_line not in seen:
                    seen.add(clean_line)
                    paragraphs.append(clean_line)
                    if len(paragraphs) >= 15:
                        break

        return paragraphs

    @classmethod
    def _extract_links(cls, soup: BeautifulSoup, page_url: str, base_target_url: str) -> Tuple[List[str], List[str]]:
        """
        Finds all anchor links, normalizes them, and categorizes into internal vs external.
        """
        internal_links: List[str] = []
        external_links: List[str] = []
        seen_urls: Set[str] = set()

        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag["href"].strip()
            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                continue

            try:
                # Resolve relative URL against current page URL
                absolute_url = urljoin(page_url, raw_href)
                parsed = urlparse(absolute_url)

                # Strictly require http or https schemes
                if parsed.scheme.lower() not in ("http", "https"):
                    continue

                # Strip fragment
                normalized_url = absolute_url.split("#")[0].rstrip("/")
                if not normalized_url or normalized_url in seen_urls:
                    continue

                seen_urls.add(normalized_url)

                # Classify internal vs external based on hostname
                if URLSecurityValidator.is_same_hostname(base_target_url, normalized_url):
                    internal_links.append(normalized_url)
                else:
                    external_links.append(normalized_url)
            except Exception:
                continue

        return internal_links, external_links
