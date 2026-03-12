import json

import pytest

from freeact.tools.fetch import fetch


@pytest.mark.anyio
async def test_fetches_html_page_with_trafilatura() -> None:
    """Article pages should use full trafilatura extraction with markdown."""
    result = await fetch("https://krasserm.github.io/2025/12/16/code-actions/")
    parsed = json.loads(result)

    assert parsed["status"] == 200
    assert parsed["contentType"] == "text/html"
    assert parsed["extractor"] == "trafilatura"
    assert parsed["externalContent"] is True
    assert parsed["title"] is not None
    assert "Code Actions" in parsed["title"]
    assert parsed["rawLength"] > 1000
    assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in parsed["text"]


@pytest.mark.anyio
async def test_falls_back_to_plain_on_index_page() -> None:
    """Index/listing pages with link-heavy headings should fall back to trafilatura-plain."""
    result = await fetch("https://krasserm.github.io")
    parsed = json.loads(result)

    assert parsed["status"] == 200
    assert parsed["contentType"] == "text/html"
    assert parsed["extractor"] == "trafilatura-plain"
    assert parsed["title"] is not None
    assert parsed["rawLength"] > 200
    # Verify all post titles are present in the extracted text
    assert "Code Actions as Tools" in parsed["text"]
    assert "single-user" in parsed["text"] or "multi-party" in parsed["text"]


@pytest.mark.anyio
async def test_fetches_json_endpoint() -> None:
    """JSON endpoints should be pretty-printed."""
    result = await fetch("https://httpbin.org/json")
    parsed = json.loads(result)

    assert parsed["status"] == 200
    assert parsed["contentType"] == "application/json"
    assert parsed["extractor"] == "json"


@pytest.mark.anyio
async def test_follows_redirects() -> None:
    """Redirects should be followed, with finalUrl reflecting the destination."""
    result = await fetch("https://httpbin.org/redirect/1")
    parsed = json.loads(result)

    assert parsed["status"] == 200
    assert parsed["finalUrl"] != parsed["url"]


@pytest.mark.anyio
async def test_truncation() -> None:
    """Content exceeding max_chars should be truncated."""
    result = await fetch("https://krasserm.github.io/2025/12/16/code-actions/", max_chars=500)
    parsed = json.loads(result)

    assert parsed["truncated"] is True
    assert parsed["rawLength"] > 500
