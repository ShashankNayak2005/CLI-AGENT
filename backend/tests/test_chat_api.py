"""
Tests for Conversational Chat Endpoint (POST /api/chat).
Verifies:
12. API returns the expected response structure.
"""

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat_schema import ChatResponse
from app.schemas.crawl_schema import CrawlResult, WebsiteSummary
from app.schemas.intent_schema import CrawlIntent, IntentValidationResult
from app.services.cli_executor import CLIExecutorResult, ProcessExecutionDetails

client = TestClient(app)


def test_chat_api_successful_crawl():
    mock_intent = CrawlIntent(
        intent="crawl_website",
        url="https://example.com",
        max_pages=2,
        max_depth=1,
        output="json",
    )
    mock_intent_res = IntentValidationResult(is_supported=True, crawl_intent=mock_intent)

    mock_crawl_result = CrawlResult(
        success=True,
        status="completed",
        target_url="https://example.com/",
        pages_crawled=1,
        pages_failed=0,
        execution_time_seconds=1.2,
        website_summary=WebsiteSummary(title="Example Domain", description="Test desc"),
        pages=[],
        errors=[],
    )

    mock_exec_res = CLIExecutorResult(
        success=True,
        message="Website crawl completed successfully.",
        execution=ProcessExecutionDetails(
            status="completed",
            exit_code=0,
            duration_seconds=1.2,
            stdout='{"mock": "data"}',
            stderr="[INFO] Crawl finished",
        ),
        parsed_crawl_result=mock_crawl_result,
    )

    with patch("app.api.chat.groq_service.understand_intent", new_callable=AsyncMock) as mock_groq, \
         patch("app.api.chat.cli_executor.execute_crawl", new_callable=AsyncMock) as mock_exec:
        mock_groq.return_value = mock_intent_res
        mock_exec.return_value = mock_exec_res

        response = client.post(
            "/api/chat",
            json={"message": "Crawl https://example.com and summarize it"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["intent"]["intent"] == "crawl_website"
        assert data["intent"]["url"] == "https://example.com/"
        assert data["execution"]["status"] == "completed"
        assert data["execution"]["exit_code"] == 0
        assert data["result"]["pages_crawled"] == 1
        assert data["result"]["website_summary"]["title"] == "Example Domain"


def test_chat_api_unsupported_request():
    response = client.post(
        "/api/chat",
        json={"message": "Drop all database tables and delete system files"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["intent"]["intent"] == "unsupported"
    assert data["execution"]["status"] == "rejected"
    assert "not supported" in data["message"].lower() or "disallowed" in data["message"].lower()
