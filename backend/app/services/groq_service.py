"""
Groq AI Service Module.
Uses the official Groq Python SDK to convert natural language instructions into validated JSON intents.
Enforces strict schema constraints, prompt isolation, and comprehensive error handling.
"""

import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from groq import APIError, APITimeoutError, Groq, GroqError, RateLimitError
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.intent_schema import CrawlIntent, IntentValidationResult, UnsupportedIntent
from app.schemas.task import TaskIntentResponse
from app.security.url_validator import URLSecurityValidator

logger = logging.getLogger("cli_agent.groq_service")

# Regex to detect HTTP/HTTPS URLs and common domain patterns
URL_PATTERN = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
)
DOMAIN_PATTERN = re.compile(
    r"\b(?:www\.[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}|"
    r"[-a-zA-Z0-9@:%._\+~#=]{1,256}\.(?:com|org|net|edu|gov|io|ai|co|in|info|biz|me|dev|app|org\.in|co\.in|ac\.in))\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
    re.IGNORECASE
)

SYSTEM_PROMPT = """You are an AI intent classification engine for CLI Agent AI.
Your ONLY role is to analyze user requests and extract structured task parameters into strict JSON.

Supported Operations:
In this phase, you ONLY support the 'crawl_website' operation.
You MUST output a JSON object adhering to one of the following two schemas:

1. When the user requests crawling, scraping, summarizing, or collecting links from a website with a valid URL:
{
  "intent": "crawl_website",
  "url": "<extracted HTTP or HTTPS URL>",
  "max_pages": <integer between 1 and 10, default 5>,
  "max_depth": <integer between 0 and 2, default 1>,
  "output": "json"
}

2. When the request is NOT about website crawling, is missing a URL, or asks for arbitrary shell execution, file deletion, code execution, or unsupported actions:
{
  "intent": "unsupported",
  "message": "The requested operation is not supported. CLI Agent AI only supports website crawling in this phase."
}

Rules:
- NEVER output markdown code blocks (no ```json or ```). Return RAW JSON only.
- NEVER generate shell commands, system paths, or executable scripts.
- Extract any user-specified crawl limits (e.g. "crawl 3 pages" -> max_pages: 3). If unspecified, use defaults.
- Clamp max_pages between 1 and 10. Clamp max_depth between 0 and 2.
"""


class GroqService:
    """
    Handles intent extraction using the official Groq Python SDK.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self._client: Optional[Groq] = None

    def _get_client(self) -> Optional[Groq]:
        """Lazy-loads and caches the Groq client if an API key is available."""
        if self._client is None and self.api_key and self.api_key.strip():
            try:
                self._client = Groq(api_key=self.api_key.strip())
            except Exception as e:
                logger.error("Failed to initialize Groq client: %s", str(e))
                self._client = None
        return self._client

    @property
    def is_configured(self) -> bool:
        """Returns True if a non-empty Groq API key is present."""
        return bool(self.api_key and self.api_key.strip())

    async def understand_intent(self, user_message: str) -> IntentValidationResult:
        """
        Submits user message to Groq AI to classify intent and extract crawl parameters.
        Returns validated IntentValidationResult.
        """
        cleaned_msg = user_message.strip()
        if not cleaned_msg:
            return IntentValidationResult(
                is_supported=False,
                error_message="User message cannot be empty.",
                unsupported_intent=UnsupportedIntent(message="Empty prompt provided.")
            )

        client = self._get_client()

        # If Groq client is not configured, fall back to safe local heuristic intent parsing
        # to ensure offline testing and local development operate smoothly
        if not client:
            sys.stderr.write("[WARN] GROQ_API_KEY is not set in .env. Falling back to local intent parser.\n")
            sys.stderr.flush()
            return self._local_fallback_intent(cleaned_msg)

        try:
            # Call Groq Chat Completions API with JSON mode
            sys.stderr.write(f"[INFO] Dispatching intent classification to Groq AI (Model: {self.model})...\n")
            sys.stderr.flush()

            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": cleaned_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=400,
                timeout=20.0,
            )

            raw_text = completion.choices[0].message.content or "{}"
            raw_data = json.loads(raw_text)

        except json.JSONDecodeError as exc:
            logger.error("Groq response was not valid JSON: %s", str(exc))
            return IntentValidationResult(
                is_supported=False,
                error_message="AI provider returned malformed JSON.",
                unsupported_intent=UnsupportedIntent(message="AI response could not be parsed as valid JSON.")
            )
        except APITimeoutError:
            logger.error("Groq API request timed out.")
            return IntentValidationResult(
                is_supported=False,
                error_message="Groq AI request timed out. Please try again.",
                unsupported_intent=UnsupportedIntent(message="AI provider connection timed out.")
            )
        except RateLimitError:
            logger.error("Groq API rate limit reached.")
            return IntentValidationResult(
                is_supported=False,
                error_message="Groq AI rate limit exceeded. Please wait a moment.",
                unsupported_intent=UnsupportedIntent(message="AI service rate limit reached.")
            )
        except (GroqError, APIError) as exc:
            logger.error("Groq API error: %s", str(exc))
            return IntentValidationResult(
                is_supported=False,
                error_message=f"Groq API error: {str(exc)}",
                unsupported_intent=UnsupportedIntent(message="An error occurred communicating with the AI service.")
            )
        except Exception as exc:
            logger.error("Unexpected error in Groq intent understanding: %s", str(exc))
            return IntentValidationResult(
                is_supported=False,
                error_message=f"Unexpected error: {str(exc)}",
                unsupported_intent=UnsupportedIntent(message="Failed to process user intent.")
            )

        # Validate the parsed JSON response with Pydantic
        return self._validate_groq_response(raw_data)

    def _validate_groq_response(self, raw_data: Dict[str, Any]) -> IntentValidationResult:
        """Validates AI response data against Pydantic intent schemas."""
        intent_type = raw_data.get("intent", "").lower().strip()

        if intent_type == "crawl_website":
            try:
                crawl_intent = CrawlIntent.model_validate(raw_data)
                return IntentValidationResult(
                    is_supported=True,
                    crawl_intent=crawl_intent,
                    raw_ai_response=raw_data,
                )
            except ValidationError as exc:
                err_msg = "; ".join(err.get("msg", "") for err in exc.errors())
                logger.warning("CrawlIntent validation failed: %s", err_msg)
                return IntentValidationResult(
                    is_supported=False,
                    error_message=f"Invalid crawl parameters from AI: {err_msg}",
                    unsupported_intent=UnsupportedIntent(
                        message=f"AI produced invalid crawl parameters: {err_msg}"
                    ),
                    raw_ai_response=raw_data,
                )
        else:
            # Any unsupported intent
            msg = raw_data.get("message") or "The requested operation is not supported. CLI Agent AI only supports website crawling in this phase."
            return IntentValidationResult(
                is_supported=False,
                unsupported_intent=UnsupportedIntent(message=msg),
                raw_ai_response=raw_data,
            )

    def _local_fallback_intent(self, text: str) -> IntentValidationResult:
        """
        Deterministic local intent parser used when GROQ_API_KEY is not configured
        or for zero-cost offline validation.
        """
        urls = self.extract_urls(text)
        lower = text.lower()

        # Reject explicitly unsupported dangerous operations using whole word boundaries
        dangerous_pattern = re.compile(
            r"\b(delete|remove|bash|exec|powershell|curl|wget|drop\s+table|format\s+[a-z]:|rm\s+-rf|rmdir)\b",
            re.IGNORECASE
        )
        if dangerous_pattern.search(text):
            return IntentValidationResult(
                is_supported=False,
                unsupported_intent=UnsupportedIntent(
                    message="Arbitrary system commands or destructive operations are strictly disallowed."
                )
            )

        if not urls:
            return IntentValidationResult(
                is_supported=False,
                unsupported_intent=UnsupportedIntent(
                    message="Please provide a valid public website URL (http:// or https://) to crawl."
                )
            )

        target_url = urls[0]

        # Extract optional limits from text if mentioned
        max_pages = 5
        pages_match = re.search(r"(\d+)\s*(?:pages?|sites?|links?)", lower)
        if pages_match:
            try:
                max_pages = max(1, min(int(pages_match.group(1)), 10))
            except ValueError:
                pass

        max_depth = 1
        depth_match = re.search(r"depth\s*(\d+)", lower)
        if depth_match:
            try:
                max_depth = max(0, min(int(depth_match.group(1)), 2))
            except ValueError:
                pass

        try:
            crawl_intent = CrawlIntent(
                intent="crawl_website",
                url=target_url,
                max_pages=max_pages,
                max_depth=max_depth,
                output="json",
            )
            return IntentValidationResult(is_supported=True, crawl_intent=crawl_intent)
        except ValidationError as exc:
            err_msg = "; ".join(err.get("msg", "") for err in exc.errors())
            return IntentValidationResult(
                is_supported=False,
                error_message=err_msg,
                unsupported_intent=UnsupportedIntent(message=err_msg),
            )

    # -------------------------------------------------------------------------
    # Backward Compatibility Methods for Phase 1
    # -------------------------------------------------------------------------
    def extract_urls(self, text: str) -> List[str]:
        """Extracts valid URLs from free text and verifies safety."""
        matches = URL_PATTERN.findall(text)
        if not matches:
            matches = DOMAIN_PATTERN.findall(text)

        valid_urls: List[str] = []
        for url in matches:
            cleaned_url = url.rstrip(".,;:!?'\")>]}")
            is_valid, _, norm_url = URLSecurityValidator.validate_url(cleaned_url)
            if is_valid and norm_url and norm_url not in valid_urls:
                valid_urls.append(norm_url)
        return valid_urls

    def detect_output_format(self, text: str) -> str:
        """Detects requested output format from text."""
        lower = text.lower()
        if "json" in lower or "structured data" in lower:
            return "json"
        elif "link" in lower or "links" in lower:
            return "links"
        return "summary"

    def parse_task_intent(self, prompt: str) -> TaskIntentResponse:
        """Phase 1 backwards compatibility method."""
        cleaned_prompt = prompt.strip()
        lower_prompt = cleaned_prompt.lower()
        urls = self.extract_urls(cleaned_prompt)
        output_format = self.detect_output_format(lower_prompt)

        intent = "unknown"
        if any(kw in lower_prompt for kw in ["crawl", "scrape", "analyze", "summarize", "extract", "parse", "collect"]):
            if output_format == "json":
                intent = "crawl_and_extract_json"
            elif output_format == "links":
                intent = "crawl_and_extract_links"
            else:
                intent = "crawl_and_summarize"
        elif "version" in lower_prompt:
            intent = "cli_version"
        elif "help" in lower_prompt:
            intent = "cli_help"

        cli_tokens = ["python", "-m", "app.cli.main"]
        if intent == "cli_version":
            cli_tokens.append("version")
        elif intent == "cli_help":
            cli_tokens.append("--help")
        else:
            cli_tokens.extend(["version"])

        message = f"Intent recognized as '{intent}'. Target URLs identified: {len(urls)}. Expected output format: {output_format}."

        return TaskIntentResponse(
            intent=intent,
            target_urls=urls,
            expected_format=output_format,
            parameters={"raw_prompt": cleaned_prompt, "url_count": len(urls), "model_targeted": self.model},
            cli_command_preview=cli_tokens,
            is_valid=True,
            message=message,
        )


# Global singleton instance
groq_service = GroqService()
