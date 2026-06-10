import asyncio
import shutil
from pathlib import Path

import pytest
from pydantic_ai.mcp import MCPServerStdio

from freeact.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR


@pytest.fixture
def tools_dir(tmp_path: Path) -> Path:
    fixtures = Path(__file__).parent / "fixtures"
    shutil.copytree(fixtures / MCPTOOLS_DIR, tmp_path / MCPTOOLS_DIR)
    shutil.copytree(fixtures / GENTOOLS_DIR, tmp_path / GENTOOLS_DIR)
    return tmp_path


def create_server(tools_dir: Path, db_path: Path, sync: bool = True, watch: bool = True) -> MCPServerStdio:
    return MCPServerStdio(
        "uv",
        args=["run", "-m", "freeact.tools.pytools.search.hybrid"],
        env={
            "PYTOOLS_DIR": str(tools_dir),
            "PYTOOLS_DB_PATH": str(db_path),
            "PYTOOLS_EMBEDDING_MODEL": "test",
            "PYTOOLS_EMBEDDING_DIM": "8",
            "PYTOOLS_WATCH": str(watch).lower(),
            "PYTOOLS_SYNC": str(sync).lower(),
        },
        timeout=30,
    )


@pytest.fixture
def mcp_server(tools_dir: Path, db_path: Path) -> MCPServerStdio:
    return create_server(tools_dir, db_path)


async def call_search_tools(
    server: MCPServerStdio,
    query: str,
    mode: str = "hybrid",
    limit: int = 5,
) -> list[dict]:
    return await server.direct_call_tool(
        "search_tools",
        {"query": query, "mode": mode, "limit": limit},
    )


@pytest.mark.asyncio
async def test_server_starts_and_provides_tools(mcp_server: MCPServerStdio) -> None:
    async with mcp_server:
        tools = await mcp_server.list_tools()

        assert "search_tools" in [t.name for t in tools]


@pytest.mark.asyncio
async def test_all_tools_indexed(mcp_server: MCPServerStdio) -> None:
    async with mcp_server:
        # Vector search matches all tools (test embedder returns same embeddings)
        result = await call_search_tools(mcp_server, query="utility", mode="vector", limit=10)

        assert len(result) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "query", "expected_name"),
    [
        ("bm25", "weather forecast", "get_forecast"),
        ("vector", "shorten text", None),
        ("hybrid", "translate language", "translator"),
    ],
)
async def test_search_modes(mcp_server: MCPServerStdio, mode: str, query: str, expected_name: str | None) -> None:
    async with mcp_server:
        result = await call_search_tools(mcp_server, query=query, mode=mode, limit=5)

        assert len(result) > 0
        if expected_name is not None:
            assert expected_name in [r["name"] for r in result]


@pytest.mark.asyncio
async def test_new_tool_indexed(mcp_server: MCPServerStdio, tools_dir: Path) -> None:
    async with mcp_server:
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

        assert "get_humidity" in [r["name"] for r in result]


@pytest.mark.asyncio
async def test_modified_tool_reindexed(mcp_server: MCPServerStdio, tools_dir: Path) -> None:
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

        assert len(result) > 0
        assert any("temperature" in r.get("description", "").lower() for r in result)


@pytest.mark.asyncio
async def test_deleted_tool_removed(mcp_server: MCPServerStdio, tools_dir: Path) -> None:
    async with mcp_server:
        result = await call_search_tools(mcp_server, query="weather alerts region", mode="bm25", limit=5)
        assert any(r["name"] == "get_alerts" for r in result)

        (tools_dir / MCPTOOLS_DIR / "weather" / "get_alerts.py").unlink()

        await asyncio.sleep(0.5)

        result = await call_search_tools(mcp_server, query="weather alerts region", mode="bm25", limit=5)
        assert not any(r["name"] == "get_alerts" for r in result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "category", "source"),
    [
        ("weather", "weather", MCPTOOLS_DIR),
        ("text", "text", GENTOOLS_DIR),
    ],
)
async def test_result_source(mcp_server: MCPServerStdio, query: str, category: str, source: str) -> None:
    async with mcp_server:
        result = await call_search_tools(mcp_server, query=query, mode="bm25", limit=5)
        matching = [r for r in result if r["category"] == category]

        assert all(r["source"] == source for r in matching)


@pytest.mark.asyncio
async def test_result_fields(mcp_server: MCPServerStdio) -> None:
    async with mcp_server:
        result = await call_search_tools(mcp_server, query="forecast", mode="bm25", limit=1)

        assert len(result) > 0
        assert {"name", "category", "source", "description", "path"} <= result[0].keys()


@pytest.mark.asyncio
async def test_concurrent_searches_with_multiple_servers(
    mcp_server: MCPServerStdio, tools_dir: Path, db_path: Path
) -> None:
    # Start the main server with sync to populate the database
    async with mcp_server:
        result = await call_search_tools(mcp_server, query="utility", mode="vector", limit=10)
        assert len(result) == 4

    servers = [create_server(tools_dir, db_path, sync=False, watch=False) for _ in range(3)]

    async def search_with_server(server: MCPServerStdio, query: str, mode: str) -> list[dict]:
        async with server:
            return await call_search_tools(server, query=query, mode=mode, limit=5)

    results = await asyncio.gather(
        search_with_server(servers[0], "weather forecast", "bm25"),
        search_with_server(servers[1], "text summarize", "vector"),
        search_with_server(servers[2], "translate", "hybrid"),
    )

    assert "get_forecast" in [r["name"] for r in results[0]]
    assert len(results[1]) > 0
    assert "translator" in [r["name"] for r in results[2]]
