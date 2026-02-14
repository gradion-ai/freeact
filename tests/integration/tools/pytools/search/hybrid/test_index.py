"""Integration tests for the Indexer module."""

from __future__ import annotations

from pathlib import Path

import pytest

from freeact.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR
from freeact.tools.pytools.search.hybrid.database import Database
from freeact.tools.pytools.search.hybrid.embed import ToolEmbedder
from freeact.tools.pytools.search.hybrid.index import Indexer, SyncResult


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
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test sync with empty tool directories."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)
            result = await indexer.sync()

        assert result.added == 0
        assert result.updated == 0
        assert result.deleted == 0

    @pytest.mark.asyncio
    async def test_sync_indexes_new_tools(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test sync indexes tools from fixtures."""
        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, fixtures_dir)
            result = await indexer.sync()

            # Should have indexed the valid tools from fixtures
            assert result.added >= 3  # create_issue, list_repos, csv_parser
            assert result.updated == 0
            assert result.deleted == 0

            # Verify tools are in database
            assert await db.exists(f"{MCPTOOLS_DIR}:github:create_issue")
            assert await db.exists(f"{MCPTOOLS_DIR}:github:list_repos")
            assert await db.exists(f"{GENTOOLS_DIR}:data:csv_parser")

    @pytest.mark.asyncio
    async def test_sync_skips_unchanged_tools(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test sync skips tools that haven't changed."""
        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, fixtures_dir)

            # First sync
            result1 = await indexer.sync()

            # Second sync - nothing should change
            result2 = await indexer.sync()

        assert result2.added == 0
        assert result2.updated == 0
        assert result2.deleted == 0
        assert result1.added > 0  # First sync did add tools

    @pytest.mark.asyncio
    async def test_sync_detects_modified_tools(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test sync detects and re-indexes modified tools."""
        # Create initial tool
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / MCPTOOLS_DIR / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Original docstring."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)

            # First sync
            result1 = await indexer.sync()

            original_entry = await db.get(f"{MCPTOOLS_DIR}:cat:tool")
            assert original_entry is not None
            original_hash = original_entry.file_hash

            # Modify the tool
            tool_file.write_text('def run():\n    """Modified docstring."""\n    pass\n')

            # Second sync
            result2 = await indexer.sync()

            modified_entry = await db.get(f"{MCPTOOLS_DIR}:cat:tool")

        assert result1.added == 1
        assert result2.updated == 1
        assert result2.added == 0
        assert modified_entry is not None
        assert modified_entry.file_hash != original_hash
        assert "Modified" in modified_entry.description

    @pytest.mark.asyncio
    async def test_sync_removes_deleted_tools(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test sync removes tools that no longer exist."""
        # Create initial tool
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / MCPTOOLS_DIR / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Docstring."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)

            # First sync
            await indexer.sync()
            assert await db.exists(f"{MCPTOOLS_DIR}:cat:tool")

            # Delete the tool
            tool_file.unlink()

            # Second sync
            result = await indexer.sync()

        assert result.deleted == 1
        assert not await db.exists(f"{MCPTOOLS_DIR}:cat:tool")


class TestIndexerFileHandling:
    """Tests for file change handling methods."""

    @pytest.mark.asyncio
    async def test_handle_file_change_indexes_new_tool(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_change indexes a new tool file."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / MCPTOOLS_DIR / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """New tool docstring."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)

            # Simulate file change event
            await indexer.handle_file_change(tool_file)

            assert await db.exists(f"{MCPTOOLS_DIR}:cat:tool")
            entry = await db.get(f"{MCPTOOLS_DIR}:cat:tool")

        assert entry is not None
        assert "New tool" in entry.description

    @pytest.mark.asyncio
    async def test_handle_file_change_updates_existing_tool(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_change updates an existing tool."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / MCPTOOLS_DIR / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Original."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)

            # Initial index
            await indexer.handle_file_change(tool_file)
            original = await db.get(f"{MCPTOOLS_DIR}:cat:tool")

            # Modify and handle change
            tool_file.write_text('def run():\n    """Updated."""\n    pass\n')
            await indexer.handle_file_change(tool_file)

            updated = await db.get(f"{MCPTOOLS_DIR}:cat:tool")

        assert original is not None
        assert updated is not None
        assert "Original" in original.description
        assert "Updated" in updated.description

    @pytest.mark.asyncio
    async def test_handle_file_change_ignores_invalid_path(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_change ignores files outside tool directories."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()
        other_file = tmp_path / "other.py"
        other_file.write_text('def run():\n    """Not a tool."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)

            # Should not raise, should just ignore
            await indexer.handle_file_change(other_file)

            ids = await db.list_ids()

        assert ids == []

    @pytest.mark.asyncio
    async def test_handle_file_delete_removes_mcptool(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_delete removes an mcptools entry."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / MCPTOOLS_DIR / "cat" / "tool.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Doc."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)
            await indexer.handle_file_change(tool_file)

            assert await db.exists(f"{MCPTOOLS_DIR}:cat:tool")

            # Delete file and handle event
            tool_file.unlink()
            await indexer.handle_file_delete(tool_file)

            assert not await db.exists(f"{MCPTOOLS_DIR}:cat:tool")

    @pytest.mark.asyncio
    async def test_handle_file_delete_removes_gentool(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_delete removes a gentools entry."""
        base_dir = tmp_path / "workspace"
        tool_file = base_dir / GENTOOLS_DIR / "cat" / "tool" / "api.py"
        tool_file.parent.mkdir(parents=True)
        tool_file.write_text('def run():\n    """Doc."""\n    pass\n')

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)
            await indexer.handle_file_change(tool_file)

            assert await db.exists(f"{GENTOOLS_DIR}:cat:tool")

            # Delete and handle
            tool_file.unlink()
            await indexer.handle_file_delete(tool_file)

            assert not await db.exists(f"{GENTOOLS_DIR}:cat:tool")

    @pytest.mark.asyncio
    async def test_handle_file_delete_ignores_invalid_path(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test handle_file_delete ignores paths outside tool directories."""
        base_dir = tmp_path / "workspace"
        base_dir.mkdir()

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)

            # Should not raise for path outside base_dir
            await indexer.handle_file_delete(tmp_path / "other.py")


class TestIndexerLifecycle:
    """Tests for Indexer lifecycle management."""

    @pytest.mark.asyncio
    async def test_sync_returns_sync_result(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test sync() returns SyncResult."""
        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, fixtures_dir)
            result = await indexer.sync()

        assert isinstance(result, SyncResult)
        assert result.added >= 0
        assert result.updated >= 0
        assert result.deleted >= 0

    @pytest.mark.asyncio
    async def test_sync_works_without_watcher(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test sync() works without starting the watcher."""
        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, fixtures_dir)

            # No watcher started
            assert indexer._watcher is None

            # Sync should still work
            result = await indexer.sync()
            assert result.added >= 3

            # Still no watcher
            assert indexer._watcher is None

    @pytest.mark.asyncio
    async def test_unwatch_is_idempotent(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test unwatch() can be called multiple times."""
        base_dir = tmp_path / "workspace"
        (base_dir / MCPTOOLS_DIR).mkdir(parents=True)

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)
            await indexer.watch()
            await indexer.unwatch()
            await indexer.unwatch()  # Should not raise


class TestIndexerWatcher:
    """Tests for file watcher functionality."""

    @pytest.mark.asyncio
    async def test_context_manager_starts_watcher(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test context manager starts and stops the watcher."""
        base_dir = tmp_path / "workspace"
        (base_dir / MCPTOOLS_DIR).mkdir(parents=True)

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)

            async with indexer:
                # Watcher should be running
                assert indexer._watcher is not None
                assert indexer._watcher.is_running is True

            # Watcher should be stopped after exit
            assert indexer._watcher is None

    @pytest.mark.asyncio
    async def test_context_manager_does_not_sync(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test context manager does not implicitly sync."""
        async with Database(db_path, dimensions) as db:
            async with Indexer(db, embedder, fixtures_dir):
                # No sync happened on context entry
                assert not await db.exists(f"{MCPTOOLS_DIR}:github:create_issue")

    @pytest.mark.asyncio
    async def test_watch_starts_watcher(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test watch() starts the file watcher."""
        base_dir = tmp_path / "workspace"
        (base_dir / MCPTOOLS_DIR).mkdir(parents=True)

        async with Database(db_path, dimensions) as db:
            indexer = Indexer(db, embedder, base_dir)
            await indexer.watch()

            assert indexer._watcher is not None
            assert indexer._watcher.is_running is True

            await indexer.unwatch()

    @pytest.mark.asyncio
    async def test_watcher_indexes_new_file(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, tmp_path: Path
    ) -> None:
        """Test file watcher triggers indexing of new files."""
        import asyncio

        base_dir = tmp_path / "workspace"
        mcptools = base_dir / MCPTOOLS_DIR / "cat"
        mcptools.mkdir(parents=True)

        async with Database(db_path, dimensions) as db:
            async with Indexer(db, embedder, base_dir):
                # Create a new tool file
                tool_file = mcptools / "new_tool.py"
                tool_file.write_text('def run():\n    """A brand new tool."""\n    pass\n')

                # Wait for debounce + processing
                await asyncio.sleep(0.5)

                # Tool should be indexed
                assert await db.exists(f"{MCPTOOLS_DIR}:cat:new_tool")
                entry = await db.get(f"{MCPTOOLS_DIR}:cat:new_tool")
                assert entry is not None
                assert "brand new" in entry.description

    @pytest.mark.asyncio
    async def test_sync_works_with_watcher_running(
        self, db_path: Path, dimensions: int, embedder: ToolEmbedder, fixtures_dir: Path
    ) -> None:
        """Test sync() can be called while watcher is running."""
        async with Database(db_path, dimensions) as db:
            async with Indexer(db, embedder, fixtures_dir) as indexer:
                # Watcher is running
                assert indexer._watcher is not None

                # Sync should still work
                result = await indexer.sync()
                assert result.added >= 3
                assert await db.exists(f"{MCPTOOLS_DIR}:github:create_issue")
