"""
Tests for Groq AI intent extraction with mocked responses.
Covers:
1. Groq returns a valid crawl intent.
2. Groq returns invalid JSON.
3. Groq returns an unsupported intent.
4. Missing URL is rejected.
5. Private/local URLs are rejected.
6. Invalid max_pages and max_depth are rejected.
"""

from unittest.mock import MagicMock, patch
import pytest

from app.schemas.intent_schema import CrawlIntent
from app.services.groq_service import GroqService


@pytest.fixture
def mock_groq():
    service = GroqService(api_key="gsk_test_mock_key", model="llama-3.3-70b-versatile")
    mock_client = MagicMock()
    service._client = mock_client
    return service, mock_client


@pytest.mark.anyio
async def test_groq_returns_valid_crawl_intent(mock_groq):
    service, client = mock_groq
    mock_choice = MagicMock()
    mock_choice.message.content = '{"intent": "crawl_website", "url": "https://example.com", "max_pages": 4, "max_depth": 1, "output": "json"}'
    client.chat.completions.create.return_value.choices = [mock_choice]

    result = await service.understand_intent("Please crawl https://example.com with 4 pages")

    assert result.is_supported is True
    assert result.crawl_intent is not None
    assert result.crawl_intent.url == "https://example.com/"
    assert result.crawl_intent.max_pages == 4
    assert result.crawl_intent.max_depth == 1


@pytest.mark.anyio
async def test_groq_returns_invalid_json(mock_groq):
    service, client = mock_groq
    mock_choice = MagicMock()
    mock_choice.message.content = "Not a json payload {broken"
    client.chat.completions.create.return_value.choices = [mock_choice]

    result = await service.understand_intent("Crawl https://example.com")

    assert result.is_supported is False
    assert "malformed JSON" in result.error_message


@pytest.mark.anyio
async def test_groq_returns_unsupported_intent(mock_groq):
    service, client = mock_groq
    mock_choice = MagicMock()
    mock_choice.message.content = '{"intent": "unsupported", "message": "Arbitrary execution is not supported."}'
    client.chat.completions.create.return_value.choices = [mock_choice]

    result = await service.understand_intent("Delete all files on drive C")

    assert result.is_supported is False
    assert result.unsupported_intent is not None
    assert result.unsupported_intent.intent == "unsupported"


@pytest.mark.anyio
async def test_missing_url_is_rejected(mock_groq):
    service, client = mock_groq
    mock_choice = MagicMock()
    # Missing required URL field
    mock_choice.message.content = '{"intent": "crawl_website", "max_pages": 5}'
    client.chat.completions.create.return_value.choices = [mock_choice]

    result = await service.understand_intent("Crawl something")

    assert result.is_supported is False
    assert "invalid crawl parameters" in result.error_message.lower()


@pytest.mark.anyio
async def test_private_local_urls_rejected(mock_groq):
    service, client = mock_groq
    mock_choice = MagicMock()
    # Attempts SSRF against internal localhost
    mock_choice.message.content = '{"intent": "crawl_website", "url": "http://127.0.0.1:8000/admin"}'
    client.chat.completions.create.return_value.choices = [mock_choice]

    result = await service.understand_intent("Crawl http://127.0.0.1:8000/admin")

    assert result.is_supported is False
    assert "validation failed" in result.error_message.lower()


@pytest.mark.anyio
async def test_invalid_max_pages_and_depth_rejected(mock_groq):
    service, client = mock_groq
    mock_choice = MagicMock()
    # max_pages > 10 should be rejected by Pydantic schema validation
    mock_choice.message.content = '{"intent": "crawl_website", "url": "https://example.com", "max_pages": 999, "max_depth": 5}'
    client.chat.completions.create.return_value.choices = [mock_choice]

    result = await service.understand_intent("Crawl https://example.com with 999 pages")

    assert result.is_supported is False
    assert "invalid crawl parameters" in result.error_message.lower()
