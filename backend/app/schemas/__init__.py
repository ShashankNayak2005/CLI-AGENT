"""
Pydantic Schemas Package
"""

from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.schemas.crawl_schema import CrawlError, CrawlResult, PageCrawlResult, WebsiteSummary
from app.schemas.health import HealthResponse
from app.schemas.intent_schema import CrawlIntent, IntentValidationResult, UnsupportedIntent
from app.schemas.task import TaskIntentRequest, TaskIntentResponse
from app.schemas.task_history_schema import (
    TaskDeleteResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskSummaryResponse,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "CrawlError",
    "CrawlIntent",
    "CrawlResult",
    "HealthResponse",
    "IntentValidationResult",
    "PageCrawlResult",
    "TaskDeleteResponse",
    "TaskDetailResponse",
    "TaskIntentRequest",
    "TaskIntentResponse",
    "TaskListResponse",
    "TaskSummaryResponse",
    "UnsupportedIntent",
    "WebsiteSummary",
]

