"""
Pydantic schemas for website crawling and content extraction.
Matches Phase 2 & 3 data contracts strictly.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HeadingItem(BaseModel):
    """Extracted HTML heading tag."""
    level: str = Field(..., description="Heading tag level (h1, h2, h3)")
    text: str = Field(..., description="Clean text of the heading")


class WebsiteSummary(BaseModel):
    """Concise website summary synthesized from crawled pages."""
    title: str = Field(default="", description="Main website title")
    description: str = Field(default="", description="Meta description or summary")
    headings: List[str] = Field(default_factory=list, description="Primary headings")
    main_content: List[str] = Field(default_factory=list, description="Key extracted paragraphs")


class PageCrawlResult(BaseModel):
    """Detailed extraction result for an individual web page."""
    url: str = Field(..., description="Crawled page URL")
    status_code: int = Field(default=200, description="HTTP status code")
    title: str = Field(default="", description="Page title")
    description: str = Field(default="", description="Page meta description")
    language: Optional[str] = Field(default=None, description="HTML lang attribute")
    headings: List[HeadingItem] = Field(default_factory=list, description="Extracted headings")
    main_content: List[str] = Field(default_factory=list, description="Main text paragraphs")
    internal_links: List[str] = Field(default_factory=list, description="Links within the same hostname")
    external_links: List[str] = Field(default_factory=list, description="Links to other hostnames")
    word_count: int = Field(default=0, description="Approximate word count of main content")
    crawled_at: str = Field(..., description="ISO 8601 timestamp of crawl")


class CrawlError(BaseModel):
    """Information regarding a failed crawl attempt."""
    url: str = Field(..., description="URL that failed to crawl")
    error_type: str = Field(..., description="Error classification (e.g. HTTPError, Timeout, BlockedByRobots, SSRFDenied)")
    message: str = Field(..., description="Safe description of the error")
    status_code: Optional[int] = Field(default=None, description="HTTP status code if applicable")


class CrawlResult(BaseModel):
    """
    Complete crawl output returned by the CLI engine.
    Matches Section 6 required JSON specification.
    """
    success: bool = Field(..., description="Whether crawl completed successfully")
    status: str = Field(..., description="Crawl status: completed, partial, or failed")
    target_url: str = Field(..., description="Initial target URL requested")
    pages_crawled: int = Field(default=0, description="Count of successfully extracted pages")
    pages_failed: int = Field(default=0, description="Count of failed page attempts")
    execution_time_seconds: float = Field(default=0.0, description="Total crawl duration in seconds")
    website_summary: WebsiteSummary = Field(default_factory=WebsiteSummary, description="Aggregated summary")
    pages: List[PageCrawlResult] = Field(default_factory=list, description="List of crawled page records")
    errors: List[CrawlError] = Field(default_factory=list, description="List of encounter errors")
