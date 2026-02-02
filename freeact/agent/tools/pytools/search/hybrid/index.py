"""Indexer for keeping the search database in sync with tool files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from ipybox.utils import arun

from freeact.agent.tools.pytools.search.hybrid.database import Database, ToolEntry
from freeact.agent.tools.pytools.search.hybrid.embed import ToolEmbedder
from freeact.agent.tools.pytools.search.hybrid.extract import (
    ToolInfo,
    scan_tools,
    tool_info_from_path,
)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    added: int
    updated: int
    deleted: int


def _compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of file contents.

    Args:
        filepath: Path to the file.

    Returns:
        Hex-encoded SHA256 hash.
    """
    content = filepath.read_bytes()
    return hashlib.sha256(content).hexdigest()


def _make_embedding_text(tool_info: ToolInfo) -> str:
    """Create text for embedding generation.

    Combines tool ID and description as specified in the spec:
    "{id}: {description}"

    Args:
        tool_info: Tool information.

    Returns:
        Text to embed.
    """
    return f"{tool_info.id}: {tool_info.description}"


class Indexer:
    """Keeps the search database in sync with tool files.

    Coordinates database, embedder, file scanning, and (optionally) file watching
    to maintain an up-to-date search index.

    On start:
    1. Scans mcptools/ and gentools/ for tools
    2. Compares file hashes to detect new/changed/deleted tools
    3. Indexes new and changed tools (generates embeddings, stores in database)
    4. Removes deleted tools from the database
    5. If watching=True, starts file watcher for ongoing updates (Step 6)

    Args:
        database: Database instance for storing tool entries.
        embedder: Embedder for generating tool embeddings.
        base_dir: Base directory containing mcptools/ and gentools/.
        watching: Whether to watch for file changes after initial sync.

    Example:
        ```python
        async with Indexer(database, embedder, base_dir) as indexer:
            # Database is synced and watcher is running
            ...
        ```
    """

    def __init__(
        self,
        database: Database,
        embedder: ToolEmbedder,
        base_dir: Path,
        watching: bool = True,
    ) -> None:
        self._database = database
        self._embedder = embedder
        self._base_dir = base_dir
        self._watching = watching
        self._watcher_task: object | None = None  # Will be asyncio.Task in Step 6

    async def start(self) -> SyncResult:
        """Start the indexer: sync database and optionally start file watcher.

        Returns:
            SyncResult with counts of added, updated, and deleted tools.
        """
        result = await self._sync()

        if self._watching:
            # File watcher will be implemented in Step 6
            pass

        return result

    async def stop(self) -> None:
        """Stop the indexer and file watcher if running."""
        # File watcher cleanup will be implemented in Step 6
        self._watcher_task = None

    async def _sync(self) -> SyncResult:
        """Perform incremental sync of tool files to database.

        Scans all tool files, compares hashes, and updates the database:
        - New tools: index (embed + store)
        - Changed tools: re-index
        - Deleted tools: remove from database

        Returns:
            SyncResult with counts.
        """
        # Scan filesystem for current tools
        current_tools = await arun(lambda: scan_tools(self._base_dir))
        current_ids = {tool.id for tool in current_tools}

        # Get existing IDs from database
        existing_ids = set(await self._database.list_ids())

        # Categorize tools
        new_ids = current_ids - existing_ids
        removed_ids = existing_ids - current_ids
        potentially_changed_ids = current_ids & existing_ids

        # Find actually changed tools (hash mismatch)
        tools_by_id = {tool.id: tool for tool in current_tools}
        changed_ids: set[str] = set()

        for tool_id in potentially_changed_ids:
            tool = tools_by_id[tool_id]
            current_hash = await arun(lambda t=tool: _compute_file_hash(t.filepath))
            stored_hash = await self._database.get_hash(tool_id)
            if current_hash != stored_hash:
                changed_ids.add(tool_id)

        # Collect tools to index (new + changed)
        tools_to_index = [tools_by_id[tid] for tid in (new_ids | changed_ids)]

        # Index new and changed tools
        if tools_to_index:
            await self._index_tools_batch(tools_to_index)

        # Remove deleted tools
        for tool_id in removed_ids:
            await self._remove_tool(tool_id)

        return SyncResult(
            added=len(new_ids),
            updated=len(changed_ids),
            deleted=len(removed_ids),
        )

    async def _index_tools_batch(self, tools: list[ToolInfo]) -> None:
        """Index multiple tools in a batch.

        Generates embeddings for all tools in one API call, then stores them.

        Args:
            tools: List of tools to index.
        """
        if not tools:
            return

        # Prepare embedding texts
        texts = [_make_embedding_text(tool) for tool in tools]

        # Generate embeddings in batch
        embeddings = await self._embedder.embed_documents(texts)

        # Compute file hashes
        hashes = await arun(lambda: [_compute_file_hash(tool.filepath) for tool in tools])

        # Create entries
        entries = [
            ToolEntry(
                id=tool.id,
                description=tool.description,
                file_hash=file_hash,
                embedding=embedding,
            )
            for tool, embedding, file_hash in zip(tools, embeddings, hashes, strict=True)
        ]

        # Separate new entries from updates
        new_entries: list[ToolEntry] = []
        for entry in entries:
            if await self._database.exists(entry.id):
                await self._database.update(entry)
            else:
                new_entries.append(entry)

        # Batch add new entries
        if new_entries:
            await self._database.add_batch(new_entries)

    async def _index_tool(self, tool_info: ToolInfo) -> None:
        """Index a single tool.

        Generates embedding and stores in database. Updates if already exists.

        Args:
            tool_info: Tool to index.
        """
        await self._index_tools_batch([tool_info])

    async def _remove_tool(self, tool_id: str) -> None:
        """Remove a tool from the database.

        Args:
            tool_id: ID of the tool to remove.
        """
        await self._database.delete(tool_id)

    async def handle_file_change(self, filepath: Path) -> None:
        """Handle a file change event from the watcher.

        This method is called by the file watcher (Step 6) when a file
        is created or modified.

        Args:
            filepath: Path to the changed file.
        """
        tool_info = await arun(lambda: tool_info_from_path(filepath, self._base_dir))
        if tool_info is not None:
            await self._index_tool(tool_info)

    async def handle_file_delete(self, filepath: Path) -> None:
        """Handle a file deletion event from the watcher.

        This method is called by the file watcher (Step 6) when a file
        is deleted. Derives the tool ID from the path and removes it.

        Args:
            filepath: Path to the deleted file.
        """
        # Derive tool ID from path without reading the file
        try:
            rel_path = filepath.relative_to(self._base_dir)
        except ValueError:
            return

        parts = rel_path.parts

        # mcptools/<category>/<tool>.py
        if len(parts) == 3 and parts[0] == "mcptools" and parts[2].endswith(".py"):
            category = parts[1]
            tool_name = Path(parts[2]).stem
            tool_id = f"mcptools:{category}:{tool_name}"
            await self._remove_tool(tool_id)

        # gentools/<category>/<tool>/api.py
        elif len(parts) == 4 and parts[0] == "gentools" and parts[3] == "api.py":
            category = parts[1]
            tool_name = parts[2]
            tool_id = f"gentools:{category}:{tool_name}"
            await self._remove_tool(tool_id)

    async def __aenter__(self) -> Indexer:
        """Start the indexer on context entry."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop the indexer on context exit."""
        await self.stop()
