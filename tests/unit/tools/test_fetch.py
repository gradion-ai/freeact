import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from freeact.tools.fetch import (
    _extract_content,
    _extract_html,
    _parse_content_type,
    _truncate,
    web_fetch,
)


class TestParseContentType:
    def test_extracts_mime_type(self) -> None:
        assert _parse_content_type("text/html; charset=utf-8") == "text/html"

    def test_no_params(self) -> None:
        assert _parse_content_type("application/json") == "application/json"

    def test_empty_string(self) -> None:
        assert _parse_content_type("") == ""

    def test_uppercased(self) -> None:
        assert _parse_content_type("TEXT/HTML") == "text/html"


class TestExtractHtml:
    def test_uses_trafilatura_when_extraction_sufficient(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: "# Extracted markdown content here")
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "Plain text content here")
        metadata = MagicMock()
        metadata.title = "Page Title"
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: metadata)
        text, title, extractor = _extract_html("<html><body>Hello</body></html>")
        assert text == "# Extracted markdown content here"
        assert extractor == "trafilatura"

    def test_extracts_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: "content that is long enough")
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "plain text")
        metadata = MagicMock()
        metadata.title = "My Page Title"
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: metadata)
        _, title, _ = _extract_html("<html></html>")
        assert title == "My Page Title"

    def test_falls_back_to_plain_when_extract_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: None)
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "Full plain text")
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: None)
        text, title, extractor = _extract_html("<html><body>content</body></html>")
        assert text == "Full plain text"
        assert extractor == "trafilatura-plain"

    def test_falls_back_to_plain_when_extract_too_sparse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plain = "A" * 1000
        extracted = "B" * 100  # 10% of plain text, below 50% threshold
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: extracted)
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: plain)
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: None)
        text, _, extractor = _extract_html("<html></html>")
        assert text == plain
        assert extractor == "trafilatura-plain"

    def test_keeps_extract_when_ratio_at_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        plain = "A" * 100
        extracted = "B" * 50  # exactly 50%, at threshold
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: extracted)
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: plain)
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: None)
        text, _, extractor = _extract_html("<html></html>")
        assert text == extracted
        assert extractor == "trafilatura"

    def test_falls_back_to_raw_when_both_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: None)
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "")
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: None)
        raw_html = "<html><body>Raw content</body></html>"
        text, _, extractor = _extract_html(raw_html)
        assert text == raw_html
        assert extractor == "raw"

    def test_title_preserved_on_plain_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: None)
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "Some text")
        metadata = MagicMock()
        metadata.title = "Kept Title"
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: metadata)
        _, title, _ = _extract_html("<html></html>")
        assert title == "Kept Title"

    def test_title_none_when_metadata_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: "content that is long enough")
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "plain")
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: None)
        _, title, _ = _extract_html("<html></html>")
        assert title is None


class TestExtractContent:
    def test_html_delegates_to_extract_html(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: "# Markdown")
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "plain")
        metadata = MagicMock()
        metadata.title = "Title"
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: metadata)
        text, title, extractor = _extract_content("<html></html>", "text/html")
        assert extractor == "trafilatura"

    def test_json_pretty_prints(self) -> None:
        raw_json = '{"key":"value","num":42}'
        text, title, extractor = _extract_content(raw_json, "application/json")
        assert text == json.dumps({"key": "value", "num": 42}, indent=2)
        assert extractor == "json"
        assert title is None

    def test_json_parse_failure_falls_back_to_raw(self) -> None:
        bad_json = "{not valid json"
        text, title, extractor = _extract_content(bad_json, "application/json")
        assert text == bad_json
        assert extractor == "raw"

    def test_markdown_passes_through(self) -> None:
        md_content = "# Hello\n\nSome markdown content"
        text, title, extractor = _extract_content(md_content, "text/markdown")
        assert text == md_content
        assert extractor == "raw"
        assert title is None

    def test_other_returns_raw(self) -> None:
        plain = "Just some plain text"
        text, title, extractor = _extract_content(plain, "text/plain")
        assert text == plain
        assert extractor == "raw"
        assert title is None


class TestTruncate:
    def test_no_truncation_needed(self) -> None:
        text, truncated = _truncate("short", 100)
        assert text == "short"
        assert truncated is False

    def test_truncates_at_limit(self) -> None:
        text, truncated = _truncate("abcdefghij", 5)
        assert text == "abcde"
        assert truncated is True

    def test_exact_length_not_truncated(self) -> None:
        text, truncated = _truncate("abcde", 5)
        assert text == "abcde"
        assert truncated is False


class TestFetchTool:
    def _mock_httpx(
        self,
        monkeypatch: pytest.MonkeyPatch,
        response_text: str,
        content_type: str = "text/html",
        status_code: int = 200,
        final_url: str = "https://example.com/page",
    ) -> AsyncMock:
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = response_text
        mock_response.url = httpx.URL(final_url)
        mock_response.headers = {"content-type": content_type}
        mock_response.raise_for_status = MagicMock()
        mock_response.elapsed = MagicMock()
        mock_response.elapsed.total_seconds.return_value = 0.45

        mock_get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        monkeypatch.setattr("freeact.tools.fetch.httpx.AsyncClient", lambda **kwargs: mock_client)
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)

        return mock_get

    def _mock_trafilatura(self, monkeypatch: pytest.MonkeyPatch, extracted: str = "content") -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: extracted)
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "plain")
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: None)

    @pytest.mark.asyncio
    async def test_fetches_url_with_get(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_trafilatura(monkeypatch)
        mock_get = self._mock_httpx(monkeypatch, "<html>Hello</html>")
        await web_fetch("https://example.com/page")
        mock_get.assert_called_once()
        assert mock_get.call_args[0][0] == "https://example.com/page"

    @pytest.mark.asyncio
    async def test_follows_redirects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_trafilatura(monkeypatch)

        created_kwargs: dict = {}

        original_mock_get = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Hello</html>"
        mock_response.url = httpx.URL("https://example.com/page")
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()
        mock_response.elapsed = MagicMock()
        mock_response.elapsed.total_seconds.return_value = 0.1
        original_mock_get.return_value = mock_response

        mock_client = AsyncMock()
        mock_client.get = original_mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        def capture_kwargs(**kwargs: object) -> AsyncMock:
            created_kwargs.update(kwargs)
            return mock_client

        monkeypatch.setattr("freeact.tools.fetch.httpx.AsyncClient", capture_kwargs)

        await web_fetch("https://example.com/page")
        assert created_kwargs.get("follow_redirects") is True

    @pytest.mark.asyncio
    async def test_returns_json_with_all_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.fetch.extract", lambda *a, **kw: "Extracted content")
        monkeypatch.setattr("freeact.tools.fetch.html2txt", lambda *a, **kw: "plain")
        metadata = MagicMock()
        metadata.title = "Test Title"
        monkeypatch.setattr("freeact.tools.fetch.extract_metadata", lambda *a, **kw: metadata)
        self._mock_httpx(monkeypatch, "<html>Hello</html>")
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert "url" in parsed
        assert "finalUrl" in parsed
        assert "status" in parsed
        assert "contentType" in parsed
        assert "title" in parsed
        assert "extractor" in parsed
        assert "text" in parsed
        assert "truncated" in parsed
        assert "rawLength" in parsed
        assert "fetchedAt" in parsed
        assert "tookMs" in parsed
        assert "externalContent" in parsed

    @pytest.mark.asyncio
    async def test_html_content_extracted_as_markdown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_trafilatura(monkeypatch, extracted="# Markdown heading")
        self._mock_httpx(monkeypatch, "<html><h1>Markdown heading</h1></html>")
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert parsed["extractor"] == "trafilatura"

    @pytest.mark.asyncio
    async def test_json_content_pretty_printed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, '{"key":"value"}', content_type="application/json")
        result = await web_fetch("https://example.com/api")
        parsed = json.loads(result)
        assert parsed["extractor"] == "json"

    @pytest.mark.asyncio
    async def test_text_content_passed_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, "Plain text content", content_type="text/plain")
        result = await web_fetch("https://example.com/file.txt")
        parsed = json.loads(result)
        assert parsed["extractor"] == "raw"

    @pytest.mark.asyncio
    async def test_content_truncated_at_max_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        long_content = "x" * 200
        self._mock_httpx(monkeypatch, long_content, content_type="text/plain")
        result = await web_fetch("https://example.com/big", max_chars=50)
        parsed = json.loads(result)
        assert parsed["truncated"] is True
        assert parsed["rawLength"] == 200

    @pytest.mark.asyncio
    async def test_content_security_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, "Some text content", content_type="text/plain")
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in parsed["text"]
        assert "[NOTE:" in parsed["text"]

    @pytest.mark.asyncio
    async def test_default_max_chars_is_50000(self, monkeypatch: pytest.MonkeyPatch) -> None:
        content = "x" * 40000
        self._mock_httpx(monkeypatch, content, content_type="text/plain")
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert parsed["truncated"] is False

    @pytest.mark.asyncio
    async def test_final_url_from_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, "content", content_type="text/plain", final_url="https://example.com/redirected")
        result = await web_fetch("https://example.com/original")
        parsed = json.loads(result)
        assert parsed["url"] == "https://example.com/original"
        assert parsed["finalUrl"] == "https://example.com/redirected"

    @pytest.mark.asyncio
    async def test_status_code_in_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, "content", content_type="text/plain", status_code=200)
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert parsed["status"] == 200

    @pytest.mark.asyncio
    async def test_took_ms_in_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, "content", content_type="text/plain")
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert parsed["tookMs"] == 450

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        monkeypatch.setattr("freeact.tools.fetch.httpx.AsyncClient", lambda **kwargs: mock_client)

        with pytest.raises(httpx.HTTPStatusError):
            await web_fetch("https://example.com/missing")

    @pytest.mark.asyncio
    async def test_external_content_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, "content", content_type="text/plain")
        result = await web_fetch("https://example.com/page")
        parsed = json.loads(result)
        assert parsed["externalContent"] is True
