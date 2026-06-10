import json
from unittest.mock import MagicMock

import httpx
import pytest

from freeact.tools.fetch import (
    _extract_content,
    _extract_html,
    _parse_content_type,
    _truncate,
    web_fetch,
)
from tests.unit.tools.conftest import InstallHttpClient

CLIENT_TARGET = "freeact.tools.fetch.httpx.AsyncClient"


def mock_extraction(
    monkeypatch: pytest.MonkeyPatch,
    extracted: str | None,
    plain: str,
    title: str | None = None,
) -> None:
    metadata: MagicMock | None = None
    if title is not None:
        metadata = MagicMock()
        metadata.title = title
    monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: extracted)
    monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: plain)
    monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: metadata)


def fetch_response(
    text: str,
    content_type: str = "text/html",
    status_code: int = 200,
    final_url: str = "https://example.com/page",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.url = httpx.URL(final_url)
    response.headers = {"content-type": content_type}
    response.raise_for_status = MagicMock()
    response.elapsed.total_seconds.return_value = 0.45
    return response


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("text/html; charset=utf-8", "text/html"),
        ("application/json", "application/json"),
        ("", ""),
        ("TEXT/HTML", "text/html"),
    ],
)
def test_parse_content_type(header: str, expected: str) -> None:
    assert _parse_content_type(header) == expected


class TestExtractHtml:
    def test_uses_trafilatura_when_extraction_sufficient(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_extraction(monkeypatch, "# Extracted markdown content here", "Plain text content here", title="Page Title")
        text, title, extractor = _extract_html("<html><body>Hello</body></html>")
        assert text == "# Extracted markdown content here"
        assert title == "Page Title"
        assert extractor == "trafilatura"

    def test_falls_back_to_plain_when_extract_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_extraction(monkeypatch, None, "Full plain text")
        text, _, extractor = _extract_html("<html><body>content</body></html>")
        assert text == "Full plain text"
        assert extractor == "trafilatura-plain"

    def test_falls_back_to_plain_when_extract_too_sparse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plain = "A" * 1000
        extracted = "B" * 100  # 10% of plain text, below 50% threshold
        mock_extraction(monkeypatch, extracted, plain)
        text, _, extractor = _extract_html("<html></html>")
        assert text == plain
        assert extractor == "trafilatura-plain"

    def test_keeps_extract_when_ratio_at_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plain = "A" * 100
        extracted = "B" * 50  # exactly 50%, at threshold
        mock_extraction(monkeypatch, extracted, plain)
        text, _, extractor = _extract_html("<html></html>")
        assert text == extracted
        assert extractor == "trafilatura"

    def test_falls_back_to_raw_when_both_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_extraction(monkeypatch, None, "")
        raw_html = "<html><body>Raw content</body></html>"
        text, _, extractor = _extract_html(raw_html)
        assert text == raw_html
        assert extractor == "raw"

    def test_title_preserved_on_plain_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_extraction(monkeypatch, None, "Some text", title="Kept Title")
        _, title, _ = _extract_html("<html></html>")
        assert title == "Kept Title"

    def test_title_none_when_metadata_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_extraction(monkeypatch, "content that is long enough", "plain")
        _, title, _ = _extract_html("<html></html>")
        assert title is None


class TestExtractContent:
    def test_html_delegates_to_extract_html(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_extraction(monkeypatch, "# Markdown", "plain", title="Title")
        _, _, extractor = _extract_content("<html></html>", "text/html")
        assert extractor == "trafilatura"

    def test_json_pretty_prints(self) -> None:
        text, title, extractor = _extract_content('{"key":"value","num":42}', "application/json")
        assert text == json.dumps({"key": "value", "num": 42}, indent=2)
        assert extractor == "json"
        assert title is None

    def test_json_parse_failure_falls_back_to_raw(self) -> None:
        bad_json = "{not valid json"
        text, _, extractor = _extract_content(bad_json, "application/json")
        assert text == bad_json
        assert extractor == "raw"

    @pytest.mark.parametrize(
        ("content", "content_type"),
        [
            ("# Hello\n\nSome markdown content", "text/markdown"),
            ("Just some plain text", "text/plain"),
        ],
    )
    def test_non_html_passes_through_raw(self, content: str, content_type: str) -> None:
        text, title, extractor = _extract_content(content, content_type)
        assert text == content
        assert extractor == "raw"
        assert title is None


@pytest.mark.parametrize(
    ("text", "max_chars", "expected_text", "expected_truncated"),
    [
        ("short", 100, "short", False),
        ("abcdefghij", 5, "abcde", True),
        ("abcde", 5, "abcde", False),
    ],
)
def test_truncate(text: str, max_chars: int, expected_text: str, expected_truncated: bool) -> None:
    assert _truncate(text, max_chars) == (expected_text, expected_truncated)


class TestFetchTool:
    @pytest.mark.asyncio
    async def test_fetches_url_with_get(self, install_http_client: InstallHttpClient) -> None:
        http = install_http_client(CLIENT_TARGET, fetch_response("Hello", content_type="text/plain"))
        await web_fetch("https://example.com/page")
        http.get.assert_called_once()
        assert http.get.call_args[0][0] == "https://example.com/page"

    @pytest.mark.asyncio
    async def test_follows_redirects(self, install_http_client: InstallHttpClient) -> None:
        http = install_http_client(CLIENT_TARGET, fetch_response("Hello", content_type="text/plain"))
        await web_fetch("https://example.com/page")
        assert http.client_kwargs.get("follow_redirects") is True

    @pytest.mark.asyncio
    async def test_returns_json_with_all_fields(
        self, monkeypatch: pytest.MonkeyPatch, install_http_client: InstallHttpClient
    ) -> None:
        mock_extraction(monkeypatch, "Extracted content", "plain", title="Test Title")
        install_http_client(CLIENT_TARGET, fetch_response("<html>Hello</html>"))
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        for key in (
            "url",
            "finalUrl",
            "contentType",
            "title",
            "extractor",
            "text",
            "truncated",
            "rawLength",
            "fetchedAt",
        ):
            assert key in parsed
        assert parsed["status"] == 200
        assert parsed["tookMs"] == 450
        assert parsed["externalContent"] is True

    @pytest.mark.asyncio
    async def test_html_content_extracted_as_markdown(
        self, monkeypatch: pytest.MonkeyPatch, install_http_client: InstallHttpClient
    ) -> None:
        mock_extraction(monkeypatch, "# Markdown heading", "plain")
        install_http_client(CLIENT_TARGET, fetch_response("<html><h1>Markdown heading</h1></html>"))
        result = await web_fetch("https://example.com/page")
        assert json.loads(result)["extractor"] == "trafilatura"

    @pytest.mark.parametrize(
        ("content", "content_type", "expected_extractor"),
        [
            ('{"key":"value"}', "application/json", "json"),
            ("Plain text content", "text/plain", "raw"),
        ],
    )
    @pytest.mark.asyncio
    async def test_non_html_extractor(
        self,
        install_http_client: InstallHttpClient,
        content: str,
        content_type: str,
        expected_extractor: str,
    ) -> None:
        install_http_client(CLIENT_TARGET, fetch_response(content, content_type=content_type))
        result = await web_fetch("https://example.com/page")
        assert json.loads(result)["extractor"] == expected_extractor

    @pytest.mark.asyncio
    async def test_content_truncated_at_max_chars(self, install_http_client: InstallHttpClient) -> None:
        install_http_client(CLIENT_TARGET, fetch_response("x" * 200, content_type="text/plain"))
        result = await web_fetch("https://example.com/big", max_chars=50)
        parsed = json.loads(result)
        assert parsed["truncated"] is True
        assert parsed["rawLength"] == 200

    @pytest.mark.asyncio
    async def test_default_max_chars_is_50000(self, install_http_client: InstallHttpClient) -> None:
        install_http_client(CLIENT_TARGET, fetch_response("x" * 40000, content_type="text/plain"))
        result = await web_fetch("https://example.com/page")
        assert json.loads(result)["truncated"] is False

    @pytest.mark.asyncio
    async def test_content_security_wrapped(self, install_http_client: InstallHttpClient) -> None:
        install_http_client(CLIENT_TARGET, fetch_response("Some text content", content_type="text/plain"))
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in parsed["text"]
        assert "[NOTE:" in parsed["text"]

    @pytest.mark.asyncio
    async def test_final_url_from_response(self, install_http_client: InstallHttpClient) -> None:
        response = fetch_response("content", content_type="text/plain", final_url="https://example.com/redirected")
        install_http_client(CLIENT_TARGET, response)
        result = await web_fetch("https://example.com/original")
        parsed = json.loads(result)
        assert parsed["url"] == "https://example.com/original"
        assert parsed["finalUrl"] == "https://example.com/redirected"

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, install_http_client: InstallHttpClient) -> None:
        response = fetch_response("", status_code=404)
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=response
        )
        install_http_client(CLIENT_TARGET, response)
        with pytest.raises(httpx.HTTPStatusError):
            await web_fetch("https://example.com/missing")
