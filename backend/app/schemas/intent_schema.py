"""
Pydantic schemas for AI-parsed user intent.
Enforces strict validation on intent, parameters, and URL safety.
"""

from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator

from app.security.url_validator import URLSecurityValidator


class CrawlIntent(BaseModel):
    """
    Structured intent representation for website crawling tasks.
    Enforces strict parameter bounds and anti-SSRF URL validation.
    """
    intent: Literal["crawl_website"] = Field(
        default="crawl_website",
        description="Identified CLI operation intent",
    )
    url: str = Field(
        ...,
        description="Public website URL to crawl",
        examples=["https://example.com"],
    )
    max_pages: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum pages to crawl (1 to 10)",
    )
    max_depth: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Maximum BFS link depth (0 to 2)",
    )
    output: Literal["json", "pretty"] = Field(
        default="json",
        description="Requested output format for CLI process",
    )

    @field_validator("url")
    @classmethod
    def validate_crawl_url(cls, v: str) -> str:
        """Ensures the URL is valid, uses http/https, and does not resolve to private/local IPs."""
        if not v or not isinstance(v, str):
            raise ValueError("URL must be a non-empty string.")

        is_valid, reason, normalized = URLSecurityValidator.validate_url(v.strip())
        if not is_valid or not normalized:
            raise ValueError(f"URL validation failed: {reason}")
        return normalized

    @field_validator("max_pages")
    @classmethod
    def clamp_max_pages(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("max_pages must be between 1 and 10.")
        return v

    @field_validator("max_depth")
    @classmethod
    def clamp_max_depth(cls, v: int) -> int:
        if v < 0 or v > 2:
            raise ValueError("max_depth must be between 0 and 2.")
        return v


class UnsupportedIntent(BaseModel):
    """
    Represents an unsupported or unauthorized intent requested by the user.
    """
    intent: Literal["unsupported"] = "unsupported"
    message: str = Field(
        default="The requested operation is not supported. CLI Agent AI only supports website crawling in this phase.",
        description="Explanation for why the request cannot be executed.",
    )
    suggested_action: Optional[str] = Field(
        default="Try requesting a website crawl, e.g.: 'Crawl https://example.com and summarize it.'",
        description="Helpful user prompt guidance.",
    )


class IntentValidationResult(BaseModel):
    """
    Container for intent parsing outcomes.
    """
    is_supported: bool
    crawl_intent: Optional[CrawlIntent] = None
    unsupported_intent: Optional[UnsupportedIntent] = None
    raw_ai_response: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
