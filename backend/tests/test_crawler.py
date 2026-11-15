"""
Unit tests for ContentExtractor and CrawlService using mocked HTTP responses.
"""

import pytest
from app.services.content_extractor import ContentExtractor
from app.schemas.crawl_schema import PageCrawlResult


SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Acme Corporation - Innovations</title>
    <meta name="description" content="Acme builds next-generation developer platforms.">
    <script>var tracking = true;</script>
    <style>.ad { color: red; }</style>
</head>
<body>
    <header><h1>Header to Ignore</h1></header>
    <nav><a href="/home">Home</a></nav>
    <main>
        <h1>Welcome to Acme Cloud</h1>
        <h2>Next-Generation CLI Tooling</h2>
        <h3>Developer Experience Reimagined</h3>
        <p>Acme Corporation develops high-performance autonomous agents and terminal software for engineering teams.</p>
        <p>Our distributed architecture ensures rapid execution and verified telemetry across all deployment environments.</p>
        <div class="banner">Sponsored banner text to remove</div>
        <a href="/products">Our Products</a>
        <a href="https://external-partner.com/docs">External Partner</a>
    </main>
    <footer><p>Copyright 2026</p></footer>
</body>
</html>
"""


def test_html_content_extraction():
    result = ContentExtractor.extract_page(
        html=SAMPLE_HTML,
        page_url="https://acme.org/index.html",
        base_target_url="https://acme.org",
        status_code=200,
    )

    assert isinstance(result, PageCrawlResult)
    assert result.title == "Acme Corporation - Innovations"
    assert result.description == "Acme builds next-generation developer platforms."
    assert result.language == "en"

    # Headings extracted from main, excluding header
    heading_texts = [h.text for h in result.headings]
    assert "Welcome to Acme Cloud" in heading_texts
    assert "Next-Generation CLI Tooling" in heading_texts
    assert "Developer Experience Reimagined" in heading_texts

    # Content extracted
    assert any("Acme Corporation develops" in p for p in result.main_content)
    assert any("distributed architecture" in p for p in result.main_content)

    # Links classified into internal and external
    assert "https://acme.org/products" in result.internal_links
    assert "https://external-partner.com/docs" in result.external_links


def test_duplicate_and_fragment_link_handling():
    html_with_dupes = """
    <html><body>
        <a href="/page1">Page 1</a>
        <a href="/page1#section2">Page 1 Section 2</a>
        <a href="/page1/">Page 1 Slash</a>
        <a href="javascript:void(0)">JS link</a>
        <a href="mailto:support@acme.org">Email link</a>
    </body></html>
    """
    result = ContentExtractor.extract_page(
        html=html_with_dupes,
        page_url="https://acme.org/",
        base_target_url="https://acme.org",
    )

    # Should deduplicate and ignore fragments/mail/js
    assert len(result.internal_links) == 1
    assert result.internal_links[0] == "https://acme.org/page1"
