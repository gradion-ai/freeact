"""Unit tests for the hybrid search MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from freeact.agent.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR
from freeact.agent.tools.pytools.search.hybrid.database import SearchResult, ToolEntry
from freeact.agent.tools.pytools.search.hybrid.server import (
    ServerState,
    ToolResult,
    _get_env_config,
    search_tools,
)


@dataclass
class MockRequestContext:
    """Mock for MCP request context."""

    lifespan_context: ServerState


@dataclass
class MockContext:
    """Mock for MCP Context."""

    request_context: MockRequestContext


@pytest.fixture
def mock_database() -> MagicMock:
    """Create a mock Database."""
    db = MagicMock()
    db.get = AsyncMock()
    return db


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Create a mock ToolEmbedder."""
    embedder = MagicMock()
    embedder.embed_query = AsyncMock(return_value=[0.1] * 8)
    return embedder


@pytest.fixture
def mock_indexer() -> MagicMock:
    """Create a mock Indexer."""
    return MagicMock()


@pytest.fixture
def mock_search_engine() -> MagicMock:
    """Create a mock SearchEngine."""
    engine = MagicMock()
    engine.bm25_search = AsyncMock(return_value=[])
    engine.vector_search = AsyncMock(return_value=[])
    engine.hybrid_search = AsyncMock(return_value=[])
    return engine


@pytest.fixture
def server_state(
    mock_database: MagicMock,
    mock_embedder: MagicMock,
    mock_indexer: MagicMock,
    mock_search_engine: MagicMock,
) -> ServerState:
    """Create a ServerState with mocked dependencies."""
    return ServerState(
        database=mock_database,
        embedder=mock_embedder,
        indexer=mock_indexer,
        search_engine=mock_search_engine,
        tools_dir=Path(".freeact/generated"),
    )


@pytest.fixture
def mock_ctx(server_state: ServerState) -> MockContext:
    """Create a mock MCP context with server state."""
    return MockContext(request_context=MockRequestContext(lifespan_context=server_state))


@pytest.fixture
def sample_entries() -> list[ToolEntry]:
    """Sample tool entries for testing."""
    return [
        ToolEntry(
            id=f"{MCPTOOLS_DIR}:github:create_issue",
            description="Create a new issue in a GitHub repository.",
            file_hash="hash1",
            embedding=[0.1] * 8,
        ),
        ToolEntry(
            id=f"{GENTOOLS_DIR}:data:csv_parser",
            description="Parse CSV files into structured data.",
            file_hash="hash2",
            embedding=[0.2] * 8,
        ),
    ]


class TestToolResult:
    """Tests for ToolResult model."""

    def test_tool_result_fields(self) -> None:
        """Test ToolResult model has correct fields."""
        result = ToolResult(
            name="create_issue",
            category="github",
            source=MCPTOOLS_DIR,
            description="Create a new issue",
            path=f".freeact/generated/{MCPTOOLS_DIR}/github/create_issue.py",
        )

        assert result.name == "create_issue"
        assert result.category == "github"
        assert result.source == MCPTOOLS_DIR
        assert result.description == "Create a new issue"
        assert result.path == f".freeact/generated/{MCPTOOLS_DIR}/github/create_issue.py"

    def test_tool_result_source_literal(self) -> None:
        """Test ToolResult source must be gentools or mcptools."""
        result = ToolResult(
            name="tool",
            category="cat",
            source=GENTOOLS_DIR,
            description="desc",
            path=f".freeact/generated/{GENTOOLS_DIR}/cat/tool/api.py",
        )
        assert result.source == GENTOOLS_DIR
        assert result.path == f".freeact/generated/{GENTOOLS_DIR}/cat/tool/api.py"


class TestSearchToolsBM25Mode:
    """Tests for search_tools with BM25 mode."""

    @pytest.mark.asyncio
    async def test_bm25_mode_calls_bm25_search(
        self,
        mock_ctx: MockContext,
        mock_search_engine: MagicMock,
    ) -> None:
        """Test BM25 mode uses bm25_search method."""
        await search_tools(query="test query", mode="bm25", limit=5, ctx=mock_ctx)

        mock_search_engine.bm25_search.assert_awaited_once_with("test query", 5)
        mock_search_engine.vector_search.assert_not_awaited()
        mock_search_engine.hybrid_search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bm25_mode_returns_results(
        self,
        mock_ctx: MockContext,
        mock_database: MagicMock,
        mock_search_engine: MagicMock,
        sample_entries: list[ToolEntry],
    ) -> None:
        """Test BM25 mode returns correctly formatted results."""
        mock_search_engine.bm25_search.return_value = [
            SearchResult(id=f"{MCPTOOLS_DIR}:github:create_issue", score=0.9),
        ]
        mock_database.get.return_value = sample_entries[0]

        results = await search_tools(query="github", mode="bm25", limit=5, ctx=mock_ctx)

        assert len(results) == 1
        assert results[0].name == "create_issue"
        assert results[0].category == "github"
        assert results[0].source == MCPTOOLS_DIR
        assert results[0].path == f".freeact/generated/{MCPTOOLS_DIR}/github/create_issue.py"


class TestSearchToolsVectorMode:
    """Tests for search_tools with vector mode."""

    @pytest.mark.asyncio
    async def test_vector_mode_calls_vector_search(
        self,
        mock_ctx: MockContext,
        mock_embedder: MagicMock,
        mock_search_engine: MagicMock,
    ) -> None:
        """Test vector mode uses vector_search method."""
        mock_embedder.embed_query.return_value = [0.5] * 8

        await search_tools(query="test query", mode="vector", limit=5, ctx=mock_ctx)

        mock_embedder.embed_query.assert_awaited_once_with("test query")
        mock_search_engine.vector_search.assert_awaited_once_with([0.5] * 8, 5)
        mock_search_engine.bm25_search.assert_not_awaited()
        mock_search_engine.hybrid_search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_vector_mode_returns_results(
        self,
        mock_ctx: MockContext,
        mock_database: MagicMock,
        mock_embedder: MagicMock,
        mock_search_engine: MagicMock,
        sample_entries: list[ToolEntry],
    ) -> None:
        """Test vector mode returns correctly formatted results."""
        mock_search_engine.vector_search.return_value = [
            SearchResult(id=f"{GENTOOLS_DIR}:data:csv_parser", score=0.85),
        ]
        mock_database.get.return_value = sample_entries[1]

        results = await search_tools(query="parse data", mode="vector", limit=5, ctx=mock_ctx)

        assert len(results) == 1
        assert results[0].name == "csv_parser"
        assert results[0].category == "data"
        assert results[0].source == GENTOOLS_DIR
        assert results[0].path == f".freeact/generated/{GENTOOLS_DIR}/data/csv_parser/api.py"


class TestSearchToolsHybridMode:
    """Tests for search_tools with hybrid mode."""

    @pytest.mark.asyncio
    async def test_hybrid_mode_calls_hybrid_search(
        self,
        mock_ctx: MockContext,
        mock_embedder: MagicMock,
        mock_search_engine: MagicMock,
    ) -> None:
        """Test hybrid mode uses hybrid_search method."""
        mock_embedder.embed_query.return_value = [0.5] * 8

        await search_tools(query="test query", mode="hybrid", limit=5, ctx=mock_ctx)

        mock_embedder.embed_query.assert_awaited_once_with("test query")
        mock_search_engine.hybrid_search.assert_awaited_once_with("test query", [0.5] * 8, 5)
        mock_search_engine.bm25_search.assert_not_awaited()
        mock_search_engine.vector_search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hybrid_is_default_mode(
        self,
        mock_ctx: MockContext,
        mock_embedder: MagicMock,
        mock_search_engine: MagicMock,
    ) -> None:
        """Test hybrid mode is the default."""
        mock_embedder.embed_query.return_value = [0.5] * 8

        await search_tools(query="test query", limit=5, ctx=mock_ctx)

        mock_search_engine.hybrid_search.assert_awaited_once()


class TestSearchToolsEdgeCases:
    """Tests for edge cases in search_tools."""

    @pytest.mark.asyncio
    async def test_missing_database_entry_skipped(
        self,
        mock_ctx: MockContext,
        mock_database: MagicMock,
        mock_search_engine: MagicMock,
    ) -> None:
        """Test results with missing database entries are skipped."""
        mock_search_engine.bm25_search.return_value = [
            SearchResult(id=f"{MCPTOOLS_DIR}:github:create_issue", score=0.9),
            SearchResult(id=f"{MCPTOOLS_DIR}:github:missing", score=0.8),
        ]
        # First call returns entry, second returns None
        mock_database.get.side_effect = [
            ToolEntry(
                id=f"{MCPTOOLS_DIR}:github:create_issue",
                description="Create issue",
                file_hash="hash",
                embedding=[0.1] * 8,
            ),
            None,
        ]

        results = await search_tools(query="github", mode="bm25", limit=5, ctx=mock_ctx)

        assert len(results) == 1
        assert results[0].name == "create_issue"

    @pytest.mark.asyncio
    async def test_empty_results(
        self,
        mock_ctx: MockContext,
        mock_search_engine: MagicMock,
    ) -> None:
        """Test empty search results."""
        mock_search_engine.bm25_search.return_value = []

        results = await search_tools(query="nonexistent", mode="bm25", limit=5, ctx=mock_ctx)

        assert results == []

    @pytest.mark.asyncio
    async def test_limit_passed_to_search(
        self,
        mock_ctx: MockContext,
        mock_search_engine: MagicMock,
    ) -> None:
        """Test limit is passed to search engine."""
        await search_tools(query="test", mode="bm25", limit=10, ctx=mock_ctx)

        mock_search_engine.bm25_search.assert_awaited_once_with("test", 10)

    @pytest.mark.asyncio
    async def test_missing_context_raises(self) -> None:
        """Test missing context raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Context is required"):
            await search_tools(query="test", mode="bm25", limit=5, ctx=None)


class TestGetEnvConfig:
    """Tests for _get_env_config function."""

    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default configuration values."""
        # Clear any existing env vars
        for key in [
            "PYTOOLS_DIR",
            "PYTOOLS_DB_PATH",
            "PYTOOLS_EMBEDDING_MODEL",
            "PYTOOLS_EMBEDDING_DIM",
            "PYTOOLS_WATCH",
            "PYTOOLS_BM25_WEIGHT",
            "PYTOOLS_VEC_WEIGHT",
        ]:
            monkeypatch.delenv(key, raising=False)

        tools_dir, db_path, model, dim, sync, watch, bm25_w, vec_w = _get_env_config()

        assert str(tools_dir) == ".freeact/generated"
        assert db_path == ".freeact/search.db"
        assert model == "google-gla:gemini-embedding-001"
        assert dim == 3072
        assert sync is True
        assert watch is True
        assert bm25_w == 1.0
        assert vec_w == 1.0

    def test_custom_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom configuration from environment."""
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

    def test_watch_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PYTOOLS_WATCH is case insensitive."""
        monkeypatch.setenv("PYTOOLS_WATCH", "TRUE")
        _, _, _, _, _, watch, _, _ = _get_env_config()
        assert watch is True

        monkeypatch.setenv("PYTOOLS_WATCH", "True")
        _, _, _, _, _, watch, _, _ = _get_env_config()
        assert watch is True

        monkeypatch.setenv("PYTOOLS_WATCH", "FALSE")
        _, _, _, _, _, watch, _, _ = _get_env_config()
        assert watch is False

    def test_sync_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test PYTOOLS_SYNC is case insensitive."""
        monkeypatch.setenv("PYTOOLS_SYNC", "TRUE")
        _, _, _, _, sync, _, _, _ = _get_env_config()
        assert sync is True

        monkeypatch.setenv("PYTOOLS_SYNC", "True")
        _, _, _, _, sync, _, _, _ = _get_env_config()
        assert sync is True

        monkeypatch.setenv("PYTOOLS_SYNC", "FALSE")
        _, _, _, _, sync, _, _, _ = _get_env_config()
        assert sync is False
