"""Integration tests for the hybrid search MCP server."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models import _cached_async_http_client

from freeact.agent.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR


@pytest.fixture(autouse=True)
def clear_http_client_cache() -> None:
    """Clear pydantic-ai's cached HTTP client to avoid cancel scope issues."""
    _cached_async_http_client.cache_clear()


@pytest.fixture
def tools_dir(tmp_path: Path) -> Path:
    """Create a temporary tools directory with fixtures."""
    fixtures = Path(__file__).parent / "fixtures"
    shutil.copytree(fixtures / MCPTOOLS_DIR, tmp_path / MCPTOOLS_DIR)
    shutil.copytree(fixtures / GENTOOLS_DIR, tmp_path / GENTOOLS_DIR)
    return tmp_path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def mcp_server(tools_dir: Path, db_path: Path) -> MCPServerStdio:
    """Create MCPServerStdio client (not connected) for the hybrid search server."""
    return MCPServerStdio(
        "uv",
        args=["run", "-m", "freeact.agent.tools.pytools.search.hybrid"],
        env={
            "PYTOOLS_DIR": str(tools_dir),
            "PYTOOLS_DB_PATH": str(db_path),
            "PYTOOLS_EMBEDDING_MODEL": "test",
            "PYTOOLS_EMBEDDING_DIM": "8",
            "PYTOOLS_WATCH": "true",
            "PYTOOLS_SYNC": "true",
        },
        timeout=30,
    )


async def call_search_tools(
    server: MCPServerStdio,
    query: str,
    mode: str = "hybrid",
    limit: int = 5,
) -> list[dict]:
    """Helper to call search_tools and parse the JSON result."""
    # direct_call_tool returns the parsed result directly for structured outputs
    return await server.direct_call_tool(
        "search_tools",
        {"query": query, "mode": mode, "limit": limit},
    )


class TestServerLifecycle:
    """Test server startup and shutdown."""

    @pytest.mark.asyncio
    async def test_server_starts_and_provides_tools(self, mcp_server: MCPServerStdio) -> None:
        """Server starts and exposes the search_tools tool."""
        async with mcp_server:
            tools = await mcp_server.list_tools()
            tool_names = [t.name for t in tools]
            assert "search_tools" in tool_names


class TestInitialIndexSync:
    """Test initial indexing on startup."""

    @pytest.mark.asyncio
    async def test_all_tools_indexed(self, mcp_server: MCPServerStdio) -> None:
        """All 4 fixture tools are indexed and searchable."""
        async with mcp_server:
            # Use vector search to find all tools (test embedder returns same embeddings)
            result = await call_search_tools(mcp_server, query="utility", mode="vector", limit=10)
            # Should find all 4 tools
            assert len(result) == 4


class TestSearchModes:
    """Test all search modes via MCP client."""

    @pytest.mark.asyncio
    async def test_bm25_search(self, mcp_server: MCPServerStdio) -> None:
        """BM25 search finds tools by keyword."""
        async with mcp_server:
            result = await call_search_tools(mcp_server, query="weather forecast", mode="bm25", limit=5)
            names = [r["name"] for r in result]
            assert "get_forecast" in names

    @pytest.mark.asyncio
    async def test_vector_search(self, mcp_server: MCPServerStdio) -> None:
        """Vector search finds semantically similar tools."""
        async with mcp_server:
            result = await call_search_tools(mcp_server, query="shorten text", mode="vector", limit=5)
            # Should find summarizer (semantic similarity)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search(self, mcp_server: MCPServerStdio) -> None:
        """Hybrid search combines BM25 and vector results."""
        async with mcp_server:
            result = await call_search_tools(mcp_server, query="translate language", mode="hybrid", limit=5)
            names = [r["name"] for r in result]
            assert "translator" in names


class TestFileWatching:
    """Test real-time file watching."""

    @pytest.mark.asyncio
    async def test_new_tool_indexed(self, mcp_server: MCPServerStdio, tools_dir: Path) -> None:
        """Adding a new tool file triggers indexing."""
        async with mcp_server:
            # Add new tool
            new_tool = tools_dir / MCPTOOLS_DIR / "weather" / "get_humidity.py"
            new_tool.write_text('''
"""Humidity tool."""


def run(city: str) -> int:
    """Get humidity percentage for a city.

    Args:
        city: City name.

    Returns:
        Humidity percentage.
    """
    return 50
''')

            # Wait for watcher to detect change
            await asyncio.sleep(0.5)

            result = await call_search_tools(mcp_server, query="humidity", mode="bm25", limit=5)
            names = [r["name"] for r in result]
            assert "get_humidity" in names

    @pytest.mark.asyncio
    async def test_modified_tool_reindexed(self, mcp_server: MCPServerStdio, tools_dir: Path) -> None:
        """Modifying a tool file triggers re-indexing."""
        async with mcp_server:
            tool_file = tools_dir / MCPTOOLS_DIR / "weather" / "get_forecast.py"
            tool_file.write_text('''
"""Updated weather tool."""


def run(city: str) -> dict:
    """Get detailed temperature and precipitation forecast.

    Args:
        city: City name.

    Returns:
        Temperature and precipitation data.
    """
    return {}
''')

            await asyncio.sleep(0.5)

            result = await call_search_tools(mcp_server, query="temperature precipitation", mode="bm25", limit=5)
            # Should find updated tool
            assert len(result) > 0
            assert any("temperature" in r.get("description", "").lower() for r in result)

    @pytest.mark.asyncio
    async def test_deleted_tool_removed(self, mcp_server: MCPServerStdio, tools_dir: Path) -> None:
        """Deleting a tool file removes it from index."""
        async with mcp_server:
            # First verify tool exists
            result = await call_search_tools(mcp_server, query="weather alerts region", mode="bm25", limit=5)
            assert any(r["name"] == "get_alerts" for r in result)

            # Delete the tool
            tool_file = tools_dir / MCPTOOLS_DIR / "weather" / "get_alerts.py"
            tool_file.unlink()

            await asyncio.sleep(0.5)

            # Verify tool is gone
            result = await call_search_tools(mcp_server, query="weather alerts region", mode="bm25", limit=5)
            assert not any(r["name"] == "get_alerts" for r in result)


class TestResultFormat:
    """Test search result structure."""

    @pytest.mark.asyncio
    async def test_mcptools_source(self, mcp_server: MCPServerStdio) -> None:
        """mcptools have correct source field."""
        async with mcp_server:
            result = await call_search_tools(mcp_server, query="weather", mode="bm25", limit=5)
            weather_tools = [r for r in result if r["category"] == "weather"]
            assert all(r["source"] == MCPTOOLS_DIR for r in weather_tools)

    @pytest.mark.asyncio
    async def test_gentools_source(self, mcp_server: MCPServerStdio) -> None:
        """gentools have correct source field."""
        async with mcp_server:
            result = await call_search_tools(mcp_server, query="text", mode="bm25", limit=5)
            text_tools = [r for r in result if r["category"] == "text"]
            assert all(r["source"] == GENTOOLS_DIR for r in text_tools)

    @pytest.mark.asyncio
    async def test_result_fields(self, mcp_server: MCPServerStdio) -> None:
        """Results have all required fields."""
        async with mcp_server:
            result = await call_search_tools(mcp_server, query="forecast", mode="bm25", limit=1)
            assert len(result) > 0
            r = result[0]
            assert "name" in r
            assert "category" in r
            assert "source" in r
            assert "description" in r
            assert "path" in r


class TestConcurrentServers:
    """Test multiple server instances accessing the same database."""

    @pytest.mark.asyncio
    async def test_concurrent_searches_with_multiple_servers(
        self, mcp_server: MCPServerStdio, tools_dir: Path, db_path: Path
    ) -> None:
        """Multiple servers can search concurrently against a shared database."""
        # First, start the main server with sync to populate the database
        async with mcp_server:
            result = await call_search_tools(mcp_server, query="utility", mode="vector", limit=10)
            assert len(result) == 4  # Verify database is populated

        # Create 3 additional server instances with sync and watch disabled
        def create_readonly_server() -> MCPServerStdio:
            return MCPServerStdio(
                "uv",
                args=["run", "-m", "freeact.agent.tools.pytools.search.hybrid"],
                env={
                    "PYTOOLS_DIR": str(tools_dir),
                    "PYTOOLS_DB_PATH": str(db_path),
                    "PYTOOLS_EMBEDDING_MODEL": "test",
                    "PYTOOLS_EMBEDDING_DIM": "8",
                    "PYTOOLS_WATCH": "false",
                    "PYTOOLS_SYNC": "false",
                },
                timeout=30,
            )

        servers = [create_readonly_server() for _ in range(3)]

        async def search_with_server(server: MCPServerStdio, query: str, mode: str) -> list[dict]:
            async with server:
                return await call_search_tools(server, query=query, mode=mode, limit=5)

        # Run all 3 searches concurrently with different queries/modes
        results = await asyncio.gather(
            search_with_server(servers[0], "weather forecast", "bm25"),
            search_with_server(servers[1], "text summarize", "vector"),
            search_with_server(servers[2], "translate", "hybrid"),
        )

        # Verify each search returned expected results
        # Server 0: BM25 search for "weather forecast"
        names_0 = [r["name"] for r in results[0]]
        assert "get_forecast" in names_0

        # Server 1: Vector search for "text summarize"
        assert len(results[1]) > 0

        # Server 2: Hybrid search for "translate"
        names_2 = [r["name"] for r in results[2]]
        assert "translator" in names_2
