"""Unit tests for the Indexer module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from freeact.agent.tools.pytools.search.hybrid.database import Database
from freeact.agent.tools.pytools.search.hybrid.embed import ToolEmbedder
from freeact.agent.tools.pytools.search.hybrid.index import Indexer, SyncResult


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def dimensions() -> int:
    """Embedding dimensions for tests."""
    return 8


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_embedder() -> ToolEmbedder:
    """Create a mock embedder that returns deterministic embeddings."""
    embedder = AsyncMock(spec=ToolEmbedder)

    def make_embedding(text: str) -> list[float]:
        """Create a simple hash-based embedding for testing."""
        h = hash(text) % 1000
        return [float(h + i) / 1000.0 for i in range(8)]

    async def embed_documents(texts: list[str]) -> list[list[float]]:
        return [make_embedding(t) for t in texts]

    async def embed_query(text: str) -> list[float]:
        return make_embedding(text)

    embedder.embed_documents = embed_documents
    embedder.embed_query = embed_query
    return embedder


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_fields(self) -> None:
        """Test SyncResult has correct fields."""
        result = SyncResult(added=5, updated=2, deleted=1)

        assert result.added == 5
        assert result.updated == 2
        assert result.deleted == 1


class TestIndexerSync:
    """Tests for Indexer sync functionality."""

    @pytest.mark.asyncio
    async def test_sync_empty_directory(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test sync with empty tool directories."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            result = await indexer.start()

        assert result.added == 0
        assert result.updated == 0
        assert result.deleted == 0

    @pytest.mark.asyncio
    async def test_sync_indexes_new_tools(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test sync indexes tools from fixtures."""
        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, fixtures_dir, watching=False)
            result = await indexer.start()

            # Should have indexed the valid tools from fixtures
            assert result.added >= 3  # create_issue, list_repos, csv_parser
            assert result.updated == 0
            assert result.deleted == 0

            # Verify tools are in database
            assert await db.exists("mcptools:github:create_issue")
            assert await db.exists("mcptools:github:list_repos")
            assert await db.exists("gentools:data:csv_parser")

    @pytest.mark.asyncio
    async def test_sync_skips_unchanged_tools(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test sync skips tools that haven't changed."""
        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, fixtures_dir, watching=False)

            # First sync
            result1 = await indexer.start()
            await indexer.stop()

            # Second sync - nothing should change
            result2 = await indexer.start()

        assert result2.added == 0
        assert result2.updated == 0
        assert result2.deleted == 0
        assert result1.added > 0  # First sync did add tools

    @pytest.mark.asyncio
    async def test_sync_detects_modified_tools(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test sync detects and re-indexes modified tools."""
        # Create initial tool
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / "mcptools" / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Original docstring."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)

            # First sync
            result1 = await indexer.start()
            await indexer.stop()

            original_entry = await db.get("mcptools:cat:tool")
            assert original_entry is not None
            original_hash = original_entry.file_hash

            # Modify the tool
            tool_file.write_text('def run():\n    """Modified docstring."""\n    pass\n')

            # Second sync
            result2 = await indexer.start()

            modified_entry = await db.get("mcptools:cat:tool")

        assert result1.added == 1
        assert result2.updated == 1
        assert result2.added == 0
        assert modified_entry is not None
        assert modified_entry.file_hash != original_hash
        assert "Modified" in modified_entry.description

    @pytest.mark.asyncio
    async def test_sync_removes_deleted_tools(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test sync removes tools that no longer exist."""
        # Create initial tool
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / "mcptools" / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Docstring."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)

            # First sync
            await indexer.start()
            await indexer.stop()
            assert await db.exists("mcptools:cat:tool")

            # Delete the tool
            tool_file.unlink()

            # Second sync
            result = await indexer.start()

        assert result.deleted == 1
        assert not await db.exists("mcptools:cat:tool")


class TestIndexerFileHandling:
    """Tests for file change handling methods."""

    @pytest.mark.asyncio
    async def test_handle_file_change_indexes_new_tool(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_change indexes a new tool file."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / "mcptools" / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """New tool docstring."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()

            # Simulate file change event
            await indexer.handle_file_change(tool_file)

            assert await db.exists("mcptools:cat:tool")
            entry = await db.get("mcptools:cat:tool")

        assert entry is not None
        assert "New tool" in entry.description

    @pytest.mark.asyncio
    async def test_handle_file_change_updates_existing_tool(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_change updates an existing tool."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / "mcptools" / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Original."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()

            # Initial index
            await indexer.handle_file_change(tool_file)
            original = await db.get("mcptools:cat:tool")

            # Modify and handle change
            tool_file.write_text('def run():\n    """Updated."""\n    pass\n')
            await indexer.handle_file_change(tool_file)

            updated = await db.get("mcptools:cat:tool")

        assert original is not None
        assert updated is not None
        assert "Original" in original.description
        assert "Updated" in updated.description

    @pytest.mark.asyncio
    async def test_handle_file_change_ignores_invalid_path(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_change ignores files outside tool directories."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()
        other_file = tmp_path / "other.py"
        other_file.write_text('def run():\n    """Not a tool."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()

            # Should not raise, should just ignore
            await indexer.handle_file_change(other_file)

            ids = await db.list_ids()

        assert ids == []

    @pytest.mark.asyncio
    async def test_handle_file_delete_removes_mcptool(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_delete removes an mcptools entry."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / "mcptools" / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Doc."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()
            await indexer.handle_file_change(tool_file)

            assert await db.exists("mcptools:cat:tool")

            # Delete file and handle event
            tool_file.unlink()
            await indexer.handle_file_delete(tool_file)

            assert not await db.exists("mcptools:cat:tool")

    @pytest.mark.asyncio
    async def test_handle_file_delete_removes_gentool(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_delete removes a gentools entry."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / "gentools" / "cat" / "tool" / "api.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Doc."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()
            await indexer.handle_file_change(tool_file)

            assert await db.exists("gentools:cat:tool")

            # Delete and handle
            tool_file.unlink()
            await indexer.handle_file_delete(tool_file)

            assert not await db.exists("gentools:cat:tool")

    @pytest.mark.asyncio
    async def test_handle_file_delete_ignores_invalid_path(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_delete ignores paths outside tool directories."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()

            # Should not raise for path outside base_dir
            await indexer.handle_file_delete(tmp_path / "other.py")


class TestIndexerLifecycle:
    """Tests for Indexer lifecycle management."""

    @pytest.mark.asyncio
    async def test_context_manager(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test Indexer works as async context manager."""
        async with Database(db_path, dimensions) as db:
            async with Indexer(db, mock_embedder, fixtures_dir, watching=False):
                # Should have synced on entry
                assert await db.exists("mcptools:github:create_issue")

    @pytest.mark.asyncio
    async def test_start_returns_sync_result(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test start() returns SyncResult."""
        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, fixtures_dir, watching=False)
            result = await indexer.start()

        assert isinstance(result, SyncResult)
        assert result.added >= 0
        assert result.updated >= 0
        assert result.deleted >= 0

    @pytest.mark.asyncio
    async def test_stop_can_be_called_multiple_times(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test stop() is idempotent."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()
            await indexer.stop()
            await indexer.stop()  # Should not raise


class TestIndexerWatchingFlag:
    """Tests for watching flag behavior."""

    @pytest.mark.asyncio
    async def test_watching_false_skips_watcher(
        self, db_path: Path, dimensions: int, mock_embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test watching=False skips file watcher setup."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, mock_embedder, base_dir, watching=False)
            await indexer.start()

            # Watcher task should be None
            assert indexer._watcher_task is None

            await indexer.stop()
