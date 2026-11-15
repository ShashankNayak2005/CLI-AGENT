"""
Tests for Groq AI Service preparatory module.
"""

from app.services.groq_service import GroqService


def test_url_extraction():
    service = GroqService()
    prompt = "Please crawl https://example.com/blog and also check https://docs.python.org/3/."
    urls = service.extract_urls(prompt)
    assert len(urls) == 2
    assert "https://example.com/blog" in urls
    assert "https://docs.python.org/3/" in urls


def test_output_format_detection():
    service = GroqService()
    assert service.detect_output_format("Scrape this and return json") == "json"
    assert service.detect_output_format("Collect all links from the page") == "links"
    assert service.detect_output_format("Give me a quick summary of the homepage") == "summary"


def test_intent_parsing():
    service = GroqService()
    # Example 1
    r1 = service.parse_task_intent("Crawl a website and summarize it.")
    assert r1.intent == "crawl_and_summarize"
    assert r1.expected_format == "summary"

    # Example 2
    r2 = service.parse_task_intent("Extract website information into JSON.")
    assert r2.intent == "crawl_and_extract_json"
    assert r2.expected_format == "json"

    # Example 3
    r3 = service.parse_task_intent("Analyze a website and collect its important links.")
    assert r3.intent == "crawl_and_extract_links"
    assert r3.expected_format == "links"

