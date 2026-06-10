# Covers behavior-inventory.md section: 14 (google search, source-derived contract)
from types import SimpleNamespace
from typing import Any

import pytest

from freeact.tools import gsearch


def make_response(
    text: str | None,
    chunks: list[Any] | None = None,
) -> SimpleNamespace:
    grounding_metadata = None
    if chunks is not None:
        grounding_metadata = SimpleNamespace(grounding_chunks=chunks)
    candidate = SimpleNamespace(grounding_metadata=grounding_metadata)
    return SimpleNamespace(text=text, candidates=[candidate] if chunks is not None else [])


def web_chunk(uri: str) -> SimpleNamespace:
    return SimpleNamespace(web=SimpleNamespace(uri=uri))


def non_web_chunk() -> SimpleNamespace:
    return SimpleNamespace(web=None)


class FakeGenaiClient:
    response: SimpleNamespace = make_response("answer")
    captured: dict[str, Any] = {}

    def __init__(self) -> None:
        async def generate_content(*, model: str, contents: str, config: Any) -> SimpleNamespace:
            FakeGenaiClient.captured = {"model": model, "contents": contents, "config": config}
            return FakeGenaiClient.response

        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


@pytest.fixture
def fake_genai(monkeypatch: pytest.MonkeyPatch) -> type[FakeGenaiClient]:
    monkeypatch.setattr(gsearch.genai, "Client", FakeGenaiClient)

    async def resolve(url: str) -> str:
        return url.replace("redirect.example", "final.example")

    monkeypatch.setattr(gsearch, "_get_redirect_target", resolve)
    return FakeGenaiClient


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_answer_with_numbered_references(self, fake_genai: type[FakeGenaiClient]) -> None:
        """Output is the synthesized answer, a blank line, then numbered source URLs."""
        fake_genai.response = make_response(
            "The answer.",
            chunks=[web_chunk("https://a.example"), web_chunk("https://b.example")],
        )

        result = await gsearch.web_search(query="who wrote X?")

        assert result == "The answer.\n\n[1]: https://a.example\n[2]: https://b.example"

    @pytest.mark.asyncio
    async def test_no_grounding_returns_answer_only(self, fake_genai: type[FakeGenaiClient]) -> None:
        fake_genai.response = make_response("Just the answer.")

        result = await gsearch.web_search(query="q")

        assert result == "Just the answer."

    @pytest.mark.asyncio
    async def test_none_answer_text_becomes_empty(self, fake_genai: type[FakeGenaiClient]) -> None:
        fake_genai.response = make_response(None)

        result = await gsearch.web_search(query="q")

        assert result == ""

    @pytest.mark.asyncio
    async def test_only_web_chunks_become_references(self, fake_genai: type[FakeGenaiClient]) -> None:
        """Non-web grounding chunks are filtered; numbering follows chunk position."""
        fake_genai.response = make_response(
            "Answer.",
            chunks=[web_chunk("https://a.example"), non_web_chunk(), web_chunk("https://c.example")],
        )

        result = await gsearch.web_search(query="q")

        assert result == "Answer.\n\n[1]: https://a.example\n[3]: https://c.example"

    @pytest.mark.asyncio
    async def test_all_chunks_non_web_returns_answer_only(self, fake_genai: type[FakeGenaiClient]) -> None:
        fake_genai.response = make_response("Answer.", chunks=[non_web_chunk()])

        result = await gsearch.web_search(query="q")

        assert result == "Answer."

    @pytest.mark.asyncio
    async def test_redirect_urls_resolved(self, fake_genai: type[FakeGenaiClient]) -> None:
        """Grounding redirect URLs are resolved to their final targets."""
        fake_genai.response = make_response(
            "Answer.",
            chunks=[web_chunk("https://redirect.example/r/1")],
        )

        result = await gsearch.web_search(query="q")

        assert "[1]: https://final.example/r/1" in result

    @pytest.mark.asyncio
    async def test_query_and_grounding_config_passed_to_model(self, fake_genai: type[FakeGenaiClient]) -> None:
        fake_genai.response = make_response("Answer.")

        await gsearch.web_search(query="my question")

        assert fake_genai.captured["contents"] == "my question"
        config = fake_genai.captured["config"]
        assert config.tools[0].google_search is not None
        from google.genai import types

        assert config.thinking_config.thinking_level == types.ThinkingLevel.MEDIUM


class TestThinkingLevelOption:
    def test_parser_accepts_valid_levels(self) -> None:
        parser = gsearch.create_parser()
        for level in ("minimal", "low", "medium", "high"):
            args = parser.parse_args(["--thinking-level", level])
            assert args.thinking_level == level

    def test_parser_default_is_medium(self) -> None:
        parser = gsearch.create_parser()
        assert parser.parse_args([]).thinking_level == "medium"

    def test_parser_rejects_invalid_level(self) -> None:
        parser = gsearch.create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--thinking-level", "extreme"])
