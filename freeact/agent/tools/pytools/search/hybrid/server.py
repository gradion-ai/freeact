"""MCP server for hybrid BM25/vector tool search."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from freeact.agent.tools.pytools.search.hybrid.database import Database
from freeact.agent.tools.pytools.search.hybrid.embed import ToolEmbedder
from freeact.agent.tools.pytools.search.hybrid.extract import parse_tool_id
from freeact.agent.tools.pytools.search.hybrid.index import Indexer
from freeact.agent.tools.pytools.search.hybrid.search import SearchConfig, SearchEngine


class ToolResult(BaseModel):
    """A tool search result."""

    name: str = Field(description="Tool name (e.g., 'create_issue')")
    category: str = Field(description="Category/server name (e.g., 'github')")
    source: Literal["gentools", "mcptools"] = Field(description="Tool source")
    description: str = Field(description="Tool description")
    path: str = Field(description="Relative path to the tool source file")


@dataclass
class ServerState:
    """State shared across the server lifetime."""

    database: Database
    embedder: ToolEmbedder
    indexer: Indexer
    search_engine: SearchEngine


def _get_env_config() -> tuple[Path, str, str, int, bool, bool, float, float]:
    """Get configuration from environment variables.

    Returns:
        Tuple of (tools_dir, db_path, embedding_model, embedding_dim,
        sync_enabled, watch_enabled, bm25_weight, vec_weight).
    """
    tools_dir = Path(os.environ.get("PYTOOLS_DIR", "."))
    db_path = os.environ.get("PYTOOLS_DB_PATH", ".freeact/search.db")
    embedding_model = os.environ.get("PYTOOLS_EMBEDDING_MODEL", "google-gla:gemini-embedding-001")
    embedding_dim = int(os.environ.get("PYTOOLS_EMBEDDING_DIM", "3072"))
    sync_enabled = os.environ.get("PYTOOLS_SYNC", "true").lower() == "true"
    watch_enabled = os.environ.get("PYTOOLS_WATCH", "true").lower() == "true"
    bm25_weight = float(os.environ.get("PYTOOLS_BM25_WEIGHT", "1.0"))
    vec_weight = float(os.environ.get("PYTOOLS_VEC_WEIGHT", "1.0"))

    return tools_dir, db_path, embedding_model, embedding_dim, sync_enabled, watch_enabled, bm25_weight, vec_weight


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[ServerState]:
    """Initialize and manage server state lifecycle.

    Initializes database, embedder, indexer, and search engine on startup.
    Optionally syncs the index and starts file watching.
    Cleans up the file watcher on shutdown.
    """
    tools_dir, db_path, embedding_model, embedding_dim, sync_enabled, watch_enabled, bm25_weight, vec_weight = (
        _get_env_config()
    )

    # Initialize components
    if embedding_model == "test":
        from pydantic_ai.embeddings import TestEmbeddingModel

        embedder = ToolEmbedder(TestEmbeddingModel(dimensions=embedding_dim))
    else:
        embedder = ToolEmbedder(embedding_model, settings={"dimensions": embedding_dim})
    database = Database(db_path, embedding_dim)
    await database.initialize()

    search_config = SearchConfig(bm25_weight=bm25_weight, vec_weight=vec_weight)
    search_engine = SearchEngine(database, search_config)
    indexer = Indexer(database, embedder, tools_dir)

    # Optionally sync and start watcher
    if watch_enabled:
        async with indexer:
            if sync_enabled:
                await indexer.sync()
            yield ServerState(database, embedder, indexer, search_engine)
    else:
        if sync_enabled:
            await indexer.sync()
        yield ServerState(database, embedder, indexer, search_engine)


mcp = FastMCP("pytools_hybrid_search", log_level="ERROR", lifespan=lifespan)


@mcp.tool(
    name="search_tools",
    annotations={
        "title": "Search Tools",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def search_tools(
    query: Annotated[
        str,
        Field(
            description="Search query that matches the tool descriptions. Use natural "
            "language for 'hybrid' (default) and 'vector' modes; use keywords for 'bm25' mode."
        ),
    ],
    mode: Annotated[
        Literal["bm25", "vector", "hybrid"],
        Field(
            description="Search mode: 'hybrid' combines keyword and semantic matching, "
            "'bm25' for keyword/exact term matching, 'vector' for semantic similarity."
        ),
    ] = "hybrid",
    limit: Annotated[int, Field(description="Maximum number of results to return.", ge=1, le=50)] = 5,
    ctx: Context | None = None,
) -> list[ToolResult]:
    """Search for tools with a query matching their description.

    Returns ranked results with tool name, category, source, description,
    and file path.
    """
    if ctx is None:
        raise RuntimeError("Context is required")

    state: ServerState = ctx.request_context.lifespan_context

    # Perform search based on mode
    match mode:
        case "bm25":
            results = await state.search_engine.bm25_search(query, limit)
        case "vector":
            embedding = await state.embedder.embed_query(query)
            results = await state.search_engine.vector_search(embedding, limit)
        case "hybrid":
            embedding = await state.embedder.embed_query(query)
            results = await state.search_engine.hybrid_search(query, embedding, limit)

    # Build response
    tool_results = []
    for result in results:
        source, category, name = parse_tool_id(result.id)
        entry = await state.database.get(result.id)
        if entry is None:
            continue

        # Construct path based on source type
        if source == "mcptools":
            path = f"{source}/{category}/{name}.py"
        else:  # gentools
            path = f"{source}/{category}/{name}/api.py"

        tool_results.append(
            ToolResult(
                name=name,
                category=category,
                source=source,  # type: ignore[arg-type]
                description=entry.description,
                path=path,
            )
        )

    return tool_results


def main() -> None:
    """Entry point for the hybrid search MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
