import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from freeact.tools.bsearch import (
    _get_api_key,
    _parse_llm_context_results,
    _parse_web_results,
    _request_headers,
    _wrap_text,
    web_search,
)


class TestGetApiKey:
    def test_returns_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "test-key-123")
        assert _get_api_key() == "test-key-123"

    def test_raises_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            _get_api_key()


class TestRequestHeaders:
    def test_includes_subscription_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "my-token")
        headers = _request_headers()
        assert headers["X-Subscription-Token"] == "my-token"

    def test_includes_accept_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "my-token")
        headers = _request_headers()
        assert headers["Accept"] == "application/json"


class TestWrapText:
    def test_wraps_non_none_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        result = _wrap_text("hello")
        assert result is not None
        assert "hello" in result
        assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in result

    def test_returns_none_for_none(self) -> None:
        assert _wrap_text(None) is None


class TestParseWebResults:
    def _make_web_response(self, results: list[dict]) -> dict:
        return {"web": {"results": results}}

    def test_extracts_title_url_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_web_response(
            [{"title": "Example", "url": "https://example.com", "description": "A description"}]
        )
        results = _parse_web_results(data)
        assert len(results) == 1
        assert "url" in results[0]
        assert results[0]["url"] == "https://example.com"

    def test_wraps_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_web_response([{"title": "My Title", "url": "https://example.com"}])
        results = _parse_web_results(data)
        assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in results[0]["title"]
        assert "My Title" in results[0]["title"]

    def test_wraps_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_web_response([{"title": "T", "url": "https://example.com", "description": "Desc text"}])
        results = _parse_web_results(data)
        assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in results[0]["description"]
        assert "Desc text" in results[0]["description"]

    def test_does_not_wrap_url(self) -> None:
        data = self._make_web_response([{"title": "T", "url": "https://example.com"}])
        results = _parse_web_results(data)
        assert results[0]["url"] == "https://example.com"

    def test_includes_published(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_web_response([{"title": "T", "url": "https://example.com", "page_age": "2 days ago"}])
        results = _parse_web_results(data)
        assert results[0]["published"] == "2 days ago"

    def test_includes_site_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_web_response(
            [{"title": "T", "url": "https://example.com", "profile": {"name": "Example Site"}}]
        )
        results = _parse_web_results(data)
        assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in results[0]["siteName"]
        assert "Example Site" in results[0]["siteName"]

    def test_missing_optional_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_web_response([{"title": "T", "url": "https://example.com"}])
        results = _parse_web_results(data)
        assert "description" not in results[0]
        assert "published" not in results[0]
        assert "siteName" not in results[0]

    def test_empty_results(self) -> None:
        data = self._make_web_response([])
        assert _parse_web_results(data) == []

    def test_missing_web_key(self) -> None:
        assert _parse_web_results({}) == []


class TestParseLlmContextResults:
    def _make_llm_response(self, results: list[dict], sources: dict | None = None) -> dict:
        data: dict = {"grounding": {"generic": results}}
        if sources is not None:
            data["sources"] = sources
        return data

    def test_extracts_title_url_snippets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_llm_response([{"title": "Title", "url": "https://example.com", "snippets": ["snippet1"]}])
        results, _ = _parse_llm_context_results(data)
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"
        assert len(results[0]["snippets"]) == 1

    def test_wraps_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_llm_response([{"title": "My Title", "url": "https://example.com", "snippets": []}])
        results, _ = _parse_llm_context_results(data)
        assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in results[0]["title"]
        assert "My Title" in results[0]["title"]

    def test_wraps_each_snippet(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)
        data = self._make_llm_response([{"title": "T", "url": "https://example.com", "snippets": ["s1", "s2"]}])
        results, _ = _parse_llm_context_results(data)
        for snippet in results[0]["snippets"]:
            assert "<<<EXTERNAL_UNTRUSTED_CONTENT" in snippet

    def test_does_not_wrap_url(self) -> None:
        data = self._make_llm_response([{"title": "T", "url": "https://example.com", "snippets": []}])
        results, _ = _parse_llm_context_results(data)
        assert results[0]["url"] == "https://example.com"

    def test_empty_grounding(self) -> None:
        data = self._make_llm_response([])
        results, _ = _parse_llm_context_results(data)
        assert results == []

    def test_missing_grounding_key(self) -> None:
        results, _ = _parse_llm_context_results({})
        assert results == []

    def test_returns_sources(self) -> None:
        sources = {"total": 3, "items": [{"name": "src1"}]}
        data = self._make_llm_response(
            [{"title": "T", "url": "https://example.com", "snippets": []}],
            sources=sources,
        )
        _, returned_sources = _parse_llm_context_results(data)
        assert returned_sources == sources


class TestWebSearchTool:
    def _mock_httpx(self, monkeypatch: pytest.MonkeyPatch, response_data: dict, status_code: int = 200) -> AsyncMock:
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()
        mock_response.elapsed = MagicMock()
        mock_response.elapsed.total_seconds.return_value = 0.45

        mock_get = AsyncMock(return_value=mock_response)

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        monkeypatch.setattr("freeact.tools.bsearch.httpx.AsyncClient", lambda: mock_client)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")
        monkeypatch.setattr("freeact.tools.security.secrets.token_hex", lambda n: "ab" * n)

        return mock_get

    def _web_response(self) -> dict:
        return {
            "web": {
                "results": [
                    {
                        "title": "Result 1",
                        "url": "https://example.com/1",
                        "description": "Description 1",
                    }
                ]
            }
        }

    def _llm_response(self) -> dict:
        return {
            "grounding": {
                "generic": [
                    {
                        "title": "Result 1",
                        "url": "https://example.com/1",
                        "snippets": ["Snippet text"],
                    }
                ]
            },
            "sources": {"total": 1},
        }

    @pytest.mark.asyncio
    async def test_web_mode_calls_correct_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_get = self._mock_httpx(monkeypatch, self._web_response())
        await web_search("test query", mode="web")
        call_args = mock_get.call_args
        assert "api.search.brave.com/res/v1/web/search" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_llm_context_mode_calls_correct_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_get = self._mock_httpx(monkeypatch, self._llm_response())
        await web_search("test query", mode="llm-context")
        call_args = mock_get.call_args
        assert "api.search.brave.com/res/v1/llm/context" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_passes_query_param(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_get = self._mock_httpx(monkeypatch, self._web_response())
        await web_search("my search query")
        call_args = mock_get.call_args
        assert call_args[1]["params"]["q"] == "my search query"

    @pytest.mark.asyncio
    async def test_web_mode_passes_count_param(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_get = self._mock_httpx(monkeypatch, self._web_response())
        await web_search("test", mode="web")
        call_args = mock_get.call_args
        assert "count" in call_args[1]["params"]

    @pytest.mark.asyncio
    async def test_llm_context_mode_omits_count_param(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_get = self._mock_httpx(monkeypatch, self._llm_response())
        await web_search("test", mode="llm-context")
        call_args = mock_get.call_args
        assert "count" not in call_args[1]["params"]

    @pytest.mark.asyncio
    async def test_passes_auth_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_get = self._mock_httpx(monkeypatch, self._web_response())
        await web_search("test")
        call_args = mock_get.call_args
        assert call_args[1]["headers"]["X-Subscription-Token"] == "test-key"

    @pytest.mark.asyncio
    async def test_web_mode_returns_json_with_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, self._web_response())
        result = await web_search("test")
        parsed = json.loads(result)
        assert "results" in parsed
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["url"] == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_llm_context_mode_returns_json_with_results_and_sources(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._mock_httpx(monkeypatch, self._llm_response())
        result = await web_search("test", mode="llm-context")
        parsed = json.loads(result)
        assert "results" in parsed
        assert "sources" in parsed
        assert len(parsed["results"]) == 1

    @pytest.mark.asyncio
    async def test_output_metadata_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_httpx(monkeypatch, self._web_response())
        result = await web_search("test query")
        parsed = json.loads(result)
        assert parsed["query"] == "test query"
        assert parsed["provider"] == "brave"
        assert parsed["mode"] == "web"
        assert parsed["count"] == 1
        assert isinstance(parsed["tookMs"], (int, float))
        assert parsed["externalContent"] is True

    @pytest.mark.asyncio
    async def test_default_mode_is_web(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_get = self._mock_httpx(monkeypatch, self._web_response())
        await web_search("test")
        call_args = mock_get.call_args
        assert "api.search.brave.com/res/v1/web/search" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        monkeypatch.setattr("freeact.tools.bsearch.httpx.AsyncClient", lambda: mock_client)
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        with pytest.raises(httpx.HTTPStatusError):
            await web_search("test")

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            await web_search("test")
