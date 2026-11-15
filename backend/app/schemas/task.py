"""
Task schemas for natural language intent understanding and CLI execution preparation.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskIntentRequest(BaseModel):
    """
    User natural language prompt request schema.
    """
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language instruction for the CLI agent",
        json_schema_extra={"example": "Crawl https://example.com and summarize it."}
    )


class TaskIntentResponse(BaseModel):
    """
    Structured intent representation parsed from user prompt.
    Prepared for Groq AI inference integration.
    """
    intent: str = Field(
        ...,
        description="Identified action intent (e.g. crawl_and_summarize, extract_json, extract_links, unknown)"
    )
    target_urls: List[str] = Field(
        default_factory=list,
        description="Extracted and validated URLs"
    )
    expected_format: str = Field(
        default="summary",
        description="Expected format: summary, json, or links"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted execution parameters"
    )
    cli_command_preview: List[str] = Field(
        default_factory=list,
        description="Preview of the structured CLI command tokens to be executed without shell=True"
    )
    is_valid: bool = Field(
        default=True,
        description="Whether the task intent is valid and executable"
    )
    message: Optional[str] = Field(
        default=None,
        description="Clarification or validation notes"
    )

