"""
Pydantic schemas for the Conversational Chat Endpoint (POST /api/chat).
Defines request format and structured response containing intent, execution telemetry, and results.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Conversational instruction payload sent from React frontend.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Natural language instruction for the CLI agent",
        examples=["Crawl https://example.com and extract the important information into JSON."],
    )


class IntentPayload(BaseModel):
    """
    Echoed validated intent parameters.
    """
    intent: str = Field(..., description="Approved intent type (e.g. crawl_website or unsupported)")
    url: Optional[str] = Field(default=None, description="Target website URL")
    max_pages: Optional[int] = Field(default=None, description="Max pages requested")
    max_depth: Optional[int] = Field(default=None, description="Max crawl depth requested")


class ExecutionTelemetry(BaseModel):
    """
    Process execution telemetry metrics.
    """
    status: str = Field(..., description="Status: completed, failed, timeout, rejected, invalid_output")
    exit_code: Optional[int] = Field(default=None, description="Process return code")
    duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")


class ChatResponse(BaseModel):
    """
    Standard response payload for POST /api/chat.
    """
    success: bool = Field(..., description="Whether the entire request and execution succeeded")
    task_id: Optional[str] = Field(default=None, description="Database task identifier for persistent history")
    message: str = Field(..., description="User-facing summary message")
    intent: IntentPayload = Field(..., description="Extracted intent and validated parameters")
    execution: ExecutionTelemetry = Field(..., description="Process execution telemetry")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Extracted crawl data if executed")
