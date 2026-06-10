from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from freeact.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR
from freeact.tools.pytools.search.hybrid.database import SearchResult, ToolEntry
from freeact.tools.pytools.search.hybrid.server import (
    ServerState,
    ToolResult,
    _get_env_config,
    search_tools,
)

DEFAULT_TOOLS_DIR = Path(".freeact/generated")
DEFAULT_DB_PATH = ".freeact/search.db"

ENV_VARS = [
    "PYTOOLS_DIR",
    "PYTOOLS_DB_PATH",
    "PYTOOLS_EMBEDDING_MODEL",
    "PYTOOLS_EMBEDDING_DIM",
    "PYTOOLS_SYNC",
    "PYTOOLS_WATCH",
    "PYTOOLS_BM25_WEIGHT",
    "PYTOOLS_VEC_WEIGHT",
]


@dataclass
class MockRequestContext:
    lifespan_context: ServerState


@dataclass
class MockContext:
    request_context: MockRequestContext


@pytest.fixture
def mock_database() -> MagicMock:
    db = MagicMock()
    db.get = AsyncMock()
    return db


@pytest.fixture
def mock_embedder() -> MagicMock:
    embedder = MagicMock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 8)
    return embedder


@pytest.fixture
def mock_search_engine() -> MagicMock:
    engine = MagicMock()
    engine.bm25_search = AsyncMock(return_value=[])
    engine.vector_search = AsyncMock(return_value=[])
    engine.hybrid_search = AsyncMock(return_value=[])
    return engine


@pytest.fixture
def mock_ctx(
    mock_database: MagicMock,
    mock_embedder: MagicMock,
    mock_search_engine: MagicMock,
) -> MockContext:
    state = ServerState(
        database=mock_database,
        embedder=mock_embedder,
        indexer=MagicMock(),
        search_engine=mock_search_engine,
        tools_dir=DEFAULT_TOOLS_DIR,
    )
    return MockContext(request_context=MockRequestContext(lifespan_context=state))


def tool_entry(tool_id: str, description: str) -> ToolEntry:
    return ToolEntry(id=tool_id, description=description, file_hash="hash", embedding=[0.1] * 8)


class TestToolResult:
    @pytest.mark.parametrize(
        ("source", "path"),
        [
            (MCPTOOLS_DIR, f"{DEFAULT_TOOLS_DIR}/{MCPTOOLS_DIR}/github/create_issue.py"),
            (GENTOOLS_DIR, f"{DEFAULT_TOOLS_DIR}/{GENTOOLS_DIR}/github/create_issue/api.py"),
        ],
    )
    def test_tool_result_fields(self, source: str, path: str) -> None:
        result = ToolResult(
            name="create_issue",
            category="github",
            source=source,  # type: ignore[arg-type]
            description="Create a new issue",
            path=path,
        )
        assert result.name == "create_issue"
        assert result.category == "github"
        assert result.source == source
        assert result.description == "Create a new issue"
        assert result.path == path


class TestSearchToolsModes:
    @pytest.mark.asyncio
    async def test_bm25_mode_calls_bm25_search(self, mock_ctx: MockContext, mock_search_engine: MagicMock) -> None:
        await search_tools(query="test query", mode="bm25", limit=5, ctx=mock_ctx)

        mock_search_engine.bm25_search.assert_awaited_once_with("test query", 5)
        mock_search_engine.vector_search.assert_not_awaited()
        mock_search_engine.hybrid_search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bm25_mode_returns_results(
        self, mock_ctx: MockContext, mock_database: MagicMock, mock_search_engine: MagicMock
    ) -> None:
        tool_id = f"{MCPTOOLS_DIR}:github:create_issue"
        mock_search_engine.bm25_search.return_value = [SearchResult(id=tool_id, score=0.9)]
        mock_database.get.return_value = tool_entry(tool_id, "Create a new issue in a GitHub repository.")

        results = await search_tools(query="github", mode="bm25", limit=5, ctx=mock_ctx)

        assert len(results) == 1
        assert results[0].name == "create_issue"
        assert results[0].category == "github"
        assert results[0].source == MCPTOOLS_DIR
        assert results[0].path == f"{DEFAULT_TOOLS_DIR}/{MCPTOOLS_DIR}/github/create_issue.py"

    @pytest.mark.asyncio
    async def test_vector_mode_calls_vector_search(
        self, mock_ctx: MockContext, mock_embedder: MagicMock, mock_search_engine: MagicMock
    ) -> None:
        mock_embedder.embed_query.return_value = [0.5] * 8

        await search_tools(query="test query", mode="vector", limit=5, ctx=mock_ctx)

        mock_embedder.embed_query.assert_awaited_once_with("test query")
        mock_search_engine.vector_search.assert_awaited_once_with([0.5] * 8, 5)
        mock_search_engine.bm25_search.assert_not_awaited()
        mock_search_engine.hybrid_search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_vector_mode_returns_results(
        self, mock_ctx: MockContext, mock_database: MagicMock, mock_search_engine: MagicMock
    ) -> None:
        tool_id = f"{GENTOOLS_DIR}:data:csv_parser"
        mock_search_engine.vector_search.return_value = [SearchResult(id=tool_id, score=0.85)]
        mock_database.get.return_value = tool_entry(tool_id, "Parse CSV files into structured data.")

        results = await search_tools(query="parse data", mode="vector", limit=5, ctx=mock_ctx)

        assert len(results) == 1
        assert results[0].name == "csv_parser"
        assert results[0].category == "data"
        assert results[0].source == GENTOOLS_DIR
        assert results[0].path == f"{DEFAULT_TOOLS_DIR}/{GENTOOLS_DIR}/data/csv_parser/api.py"

    @pytest.mark.asyncio
    async def test_hybrid_mode_calls_hybrid_search(
        self, mock_ctx: MockContext, mock_embedder: MagicMock, mock_search_engine: MagicMock
    ) -> None:
        mock_embedder.embed_query.return_value = [0.5] * 8

        await search_tools(query="test query", mode="hybrid", limit=5, ctx=mock_ctx)

        mock_embedder.embed_query.assert_awaited_once_with("test query")
        mock_search_engine.hybrid_search.assert_awaited_once_with("test query", [0.5] * 8, 5)
        mock_search_engine.bm25_search.assert_not_awaited()
        mock_search_engine.vector_search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hybrid_is_default_mode(self, mock_ctx: MockContext, mock_search_engine: MagicMock) -> None:
        await search_tools(query="test query", limit=5, ctx=mock_ctx)

        mock_search_engine.hybrid_search.assert_awaited_once()


class TestSearchToolsEdgeCases:
    @pytest.mark.asyncio
    async def test_missing_database_entry_skipped(
        self, mock_ctx: MockContext, mock_database: MagicMock, mock_search_engine: MagicMock
    ) -> None:
        mock_search_engine.bm25_search.return_value = [
            SearchResult(id=f"{MCPTOOLS_DIR}:github:create_issue", score=0.9),
            SearchResult(id=f"{MCPTOOLS_DIR}:github:missing", score=0.8),
        ]
        mock_database.get.side_effect = [
            tool_entry(f"{MCPTOOLS_DIR}:github:create_issue", "Create issue"),
            None,
        ]

        results = await search_tools(query="github", mode="bm25", limit=5, ctx=mock_ctx)

        assert len(results) == 1
        assert results[0].name == "create_issue"

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_ctx: MockContext, mock_search_engine: MagicMock) -> None:
        mock_search_engine.bm25_search.return_value = []

        results = await search_tools(query="nonexistent", mode="bm25", limit=5, ctx=mock_ctx)

        assert results == []

    @pytest.mark.asyncio
    async def test_limit_passed_to_search(self, mock_ctx: MockContext, mock_search_engine: MagicMock) -> None:
        await search_tools(query="test", mode="bm25", limit=10, ctx=mock_ctx)

        mock_search_engine.bm25_search.assert_awaited_once_with("test", 10)

    @pytest.mark.asyncio
    async def test_missing_context_raises(self) -> None:
        with pytest.raises(RuntimeError, match="Context is required"):
            await search_tools(query="test", mode="bm25", limit=5, ctx=None)


class TestGetEnvConfig:
    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in ENV_VARS:
            monkeypatch.delenv(key, raising=False)

        tools_dir, db_path, model, dim, sync, watch, bm25_w, vec_w = _get_env_config()

        assert str(tools_dir) == str(DEFAULT_TOOLS_DIR)
        assert db_path == DEFAULT_DB_PATH
        assert model == "google-gla:gemini-embedding-001"
        assert dim == 3072
        assert sync is True
        assert watch is True
        assert bm25_w == 1.0
        assert vec_w == 1.0

    def test_custom_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PYTOOLS_DIR", "/custom/path")
        monkeypatch.setenv("PYTOOLS_DB_PATH", "/custom/db.sqlite")
        monkeypatch.setenv("PYTOOLS_EMBEDDING_MODEL", "openai:text-embedding-ada-002")
        monkeypatch.setenv("PYTOOLS_EMBEDDING_DIM", "1536")
        monkeypatch.setenv("PYTOOLS_SYNC", "false")
        monkeypatch.setenv("PYTOOLS_WATCH", "false")
        monkeypatch.setenv("PYTOOLS_BM25_WEIGHT", "0.5")
        monkeypatch.setenv("PYTOOLS_VEC_WEIGHT", "2.0")

        tools_dir, db_path, model, dim, sync, watch, bm25_w, vec_w = _get_env_config()

        assert str(tools_dir) == "/custom/path"
        assert db_path == "/custom/db.sqlite"
        assert model == "openai:text-embedding-ada-002"
        assert dim == 1536
        assert sync is False
        assert watch is False
        assert bm25_w == 0.5
        assert vec_w == 2.0

    @pytest.mark.parametrize("env_var", ["PYTOOLS_SYNC", "PYTOOLS_WATCH"])
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("TRUE", True), ("True", True), ("FALSE", False)],
    )
    def test_bool_env_case_insensitive(
        self, monkeypatch: pytest.MonkeyPatch, env_var: str, value: str, expected: bool
    ) -> None:
        monkeypatch.setenv(env_var, value)
        _, _, _, _, sync, watch, _, _ = _get_env_config()
        actual = sync if env_var == "PYTOOLS_SYNC" else watch
        assert actual is expected
