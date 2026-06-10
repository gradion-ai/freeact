import json
from unittest.mock import MagicMock

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
from tests.unit.tools.conftest import InstallHttpClient

CLIENT_TARGET = "freeact.tools.bsearch.httpx.AsyncClient"
WRAP_MARKER = "<<<EXTERNAL_UNTRUSTED_CONTENT"


def search_response(data: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    response.elapsed.total_seconds.return_value = 0.45
    return response


def web_response() -> dict:
    return {"web": {"results": [{"title": "Result 1", "url": "https://example.com/1", "description": "Description 1"}]}}


def llm_response() -> dict:
    return {
        "grounding": {"generic": [{"title": "Result 1", "url": "https://example.com/1", "snippets": ["Snippet text"]}]},
        "sources": {"total": 1},
    }


class TestGetApiKey:
    def test_returns_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "test-key-123")
        assert _get_api_key() == "test-key-123"

    def test_raises_when_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            _get_api_key()


def test_request_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "my-token")
    headers = _request_headers()
    assert headers["X-Subscription-Token"] == "my-token"
    assert headers["Accept"] == "application/json"


class TestWrapText:
    def test_wraps_non_none_text(self) -> None:
        result = _wrap_text("hello")
        assert result is not None
        assert "hello" in result
        assert WRAP_MARKER in result

    def test_returns_none_for_none(self) -> None:
        assert _wrap_text(None) is None


class TestParseWebResults:
    def test_wraps_untrusted_fields(self) -> None:
        data = {
            "web": {
                "results": [
                    {
                        "title": "My Title",
                        "url": "https://example.com",
                        "description": "Desc text",
                        "page_age": "2 days ago",
                        "profile": {"name": "Example Site"},
                    }
                ]
            }
        }
        results = _parse_web_results(data)
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"
        assert WRAP_MARKER in results[0]["title"]
        assert "My Title" in results[0]["title"]
        assert WRAP_MARKER in results[0]["description"]
        assert "Desc text" in results[0]["description"]
        assert results[0]["published"] == "2 days ago"
        assert WRAP_MARKER in results[0]["siteName"]
        assert "Example Site" in results[0]["siteName"]

    def test_missing_optional_fields(self) -> None:
        results = _parse_web_results({"web": {"results": [{"title": "T", "url": "https://example.com"}]}})
        assert "description" not in results[0]
        assert "published" not in results[0]
        assert "siteName" not in results[0]

    @pytest.mark.parametrize("data", [{"web": {"results": []}}, {}])
    def test_empty_or_missing_results(self, data: dict) -> None:
        assert _parse_web_results(data) == []


class TestParseLlmContextResults:
    def test_wraps_untrusted_fields_and_returns_sources(self) -> None:
        sources = {"total": 3, "items": [{"name": "src1"}]}
        data = {
            "grounding": {"generic": [{"title": "My Title", "url": "https://example.com", "snippets": ["s1", "s2"]}]},
            "sources": sources,
        }
        results, returned_sources = _parse_llm_context_results(data)
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"
        assert WRAP_MARKER in results[0]["title"]
        assert "My Title" in results[0]["title"]
        assert len(results[0]["snippets"]) == 2
        for snippet in results[0]["snippets"]:
            assert WRAP_MARKER in snippet
        assert returned_sources == sources

    @pytest.mark.parametrize("data", [{"grounding": {"generic": []}}, {}])
    def test_empty_or_missing_grounding(self, data: dict) -> None:
        results, _ = _parse_llm_context_results(data)
        assert results == []


class TestWebSearchTool:
    @pytest.fixture(autouse=True)
    def api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

    @pytest.mark.parametrize(
        ("mode", "url_fragment", "has_count"),
        [
            ("web", "api.search.brave.com/res/v1/web/search", True),
            ("llm-context", "api.search.brave.com/res/v1/llm/context", False),
        ],
    )
    @pytest.mark.asyncio
    async def test_mode_endpoint_and_params(
        self,
        install_http_client: InstallHttpClient,
        mode: str,
        url_fragment: str,
        has_count: bool,
    ) -> None:
        data = web_response() if mode == "web" else llm_response()
        http = install_http_client(CLIENT_TARGET, search_response(data))
        await web_search("test query", mode=mode)  # type: ignore[arg-type]
        call_args = http.get.call_args
        assert url_fragment in call_args[0][0]
        assert ("count" in call_args[1]["params"]) is has_count

    @pytest.mark.asyncio
    async def test_default_mode_request(self, install_http_client: InstallHttpClient) -> None:
        http = install_http_client(CLIENT_TARGET, search_response(web_response()))
        await web_search("my search query")
        call_args = http.get.call_args
        assert "api.search.brave.com/res/v1/web/search" in call_args[0][0]
        assert call_args[1]["params"]["q"] == "my search query"
        assert call_args[1]["headers"]["X-Subscription-Token"] == "test-key"

    @pytest.mark.asyncio
    async def test_web_mode_returns_json_with_results(self, install_http_client: InstallHttpClient) -> None:
        install_http_client(CLIENT_TARGET, search_response(web_response()))
        result = await web_search("test")
        parsed = json.loads(result)
        assert "results" in parsed
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["url"] == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_llm_context_mode_returns_json_with_results_and_sources(
        self, install_http_client: InstallHttpClient
    ) -> None:
        install_http_client(CLIENT_TARGET, search_response(llm_response()))
        result = await web_search("test", mode="llm-context")
        parsed = json.loads(result)
        assert "results" in parsed
        assert "sources" in parsed
        assert len(parsed["results"]) == 1

    @pytest.mark.asyncio
    async def test_output_metadata_fields(self, install_http_client: InstallHttpClient) -> None:
        install_http_client(CLIENT_TARGET, search_response(web_response()))
        result = await web_search("test query")
        parsed = json.loads(result)
        assert parsed["query"] == "test query"
        assert parsed["provider"] == "brave"
        assert parsed["mode"] == "web"
        assert parsed["count"] == 1
        assert isinstance(parsed["tookMs"], (int, float))
        assert parsed["externalContent"] is True

    @pytest.mark.asyncio
    async def test_http_error_propagates(self, install_http_client: InstallHttpClient) -> None:
        response = search_response({}, status_code=401)
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=response
        )
        install_http_client(CLIENT_TARGET, response)
        with pytest.raises(httpx.HTTPStatusError):
            await web_search("test")

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            await web_search("test")
