"""Unit tests for the ToolWatcher module."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from freeact.agent.tools.pytools.search.hybrid.watch import ToolWatcher


class TestToolWatcherFilter:
    """Tests for watch filter logic."""

    def test_filter_accepts_py_files_in_mcptools(self, tmp_path: Path) -> None:
        """Test filter accepts .py files in mcptools/."""
        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )
        from watchfiles import Change

        path = str(tmp_path / "mcptools" / "github" / "create_issue.py")
        assert watcher._watch_filter(Change.modified, path) is True

    def test_filter_accepts_py_files_in_gentools(self, tmp_path: Path) -> None:
        """Test filter accepts .py files in gentools/."""
        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )
        from watchfiles import Change

        path = str(tmp_path / "gentools" / "data" / "csv_parser" / "api.py")
        assert watcher._watch_filter(Change.modified, path) is True

    def test_filter_rejects_non_py_files(self, tmp_path: Path) -> None:
        """Test filter rejects non-.py files."""
        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )
        from watchfiles import Change

        path = str(tmp_path / "mcptools" / "github" / "readme.md")
        assert watcher._watch_filter(Change.modified, path) is False

    def test_filter_rejects_files_outside_tool_dirs(self, tmp_path: Path) -> None:
        """Test filter rejects files outside mcptools/ and gentools/."""
        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )
        from watchfiles import Change

        path = str(tmp_path / "other" / "file.py")
        assert watcher._watch_filter(Change.modified, path) is False

    def test_filter_rejects_files_outside_base_dir(self, tmp_path: Path) -> None:
        """Test filter rejects files outside base directory."""
        watcher = ToolWatcher(
            tmp_path / "workspace",
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )
        from watchfiles import Change

        path = str(tmp_path / "mcptools" / "tool.py")
        assert watcher._watch_filter(Change.modified, path) is False


class TestToolWatcherLifecycle:
    """Tests for watcher lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self, tmp_path: Path) -> None:
        """Test start() sets is_running to True."""
        (tmp_path / "mcptools").mkdir()

        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )

        await watcher.start()
        try:
            assert watcher.is_running is True
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self, tmp_path: Path) -> None:
        """Test stop() sets is_running to False."""
        (tmp_path / "mcptools").mkdir()

        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )

        await watcher.start()
        await watcher.stop()

        assert watcher.is_running is False

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, tmp_path: Path) -> None:
        """Test calling start() multiple times is safe."""
        (tmp_path / "mcptools").mkdir()

        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )

        await watcher.start()
        await watcher.start()  # Should not raise
        try:
            assert watcher.is_running is True
        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self, tmp_path: Path) -> None:
        """Test calling stop() multiple times is safe."""
        (tmp_path / "mcptools").mkdir()

        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )

        await watcher.start()
        await watcher.stop()
        await watcher.stop()  # Should not raise

        assert watcher.is_running is False

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_path: Path) -> None:
        """Test watcher works as async context manager."""
        (tmp_path / "mcptools").mkdir()

        async with ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        ) as watcher:
            assert watcher.is_running is True

        assert watcher.is_running is False

    @pytest.mark.asyncio
    async def test_no_directories_to_watch(self, tmp_path: Path) -> None:
        """Test watcher handles missing mcptools/ and gentools/ gracefully."""
        # Neither mcptools nor gentools exist
        watcher = ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=lambda p: asyncio.sleep(0),
        )

        await watcher.start()
        try:
            # Should still be "running" (waiting for stop)
            assert watcher.is_running is True
        finally:
            await watcher.stop()


class TestToolWatcherEvents:
    """Tests for file change event handling."""

    @pytest.mark.asyncio
    async def test_file_creation_triggers_on_change(self, tmp_path: Path) -> None:
        """Test creating a .py file triggers on_change callback."""
        mcptools = tmp_path / "mcptools" / "cat"
        mcptools.mkdir(parents=True)

        changes: list[Path] = []

        async def on_change(path: Path) -> None:
            changes.append(path)

        async with ToolWatcher(
            tmp_path,
            on_change=on_change,
            on_delete=lambda p: asyncio.sleep(0),
            debounce_ms=50,  # Short debounce for faster tests
        ):
            # Create a file
            tool_file = mcptools / "tool.py"
            tool_file.write_text("def run(): pass")

            # Wait for debounce + processing
            await asyncio.sleep(0.2)

        assert len(changes) == 1
        assert changes[0] == tool_file

    @pytest.mark.asyncio
    async def test_file_modification_triggers_on_change(self, tmp_path: Path) -> None:
        """Test modifying a .py file triggers on_change callback."""
        mcptools = tmp_path / "mcptools" / "cat"
        mcptools.mkdir(parents=True)
        tool_file = mcptools / "tool.py"
        tool_file.write_text("def run(): pass")

        changes: list[Path] = []

        async def on_change(path: Path) -> None:
            changes.append(path)

        async with ToolWatcher(
            tmp_path,
            on_change=on_change,
            on_delete=lambda p: asyncio.sleep(0),
            debounce_ms=50,
        ):
            # Modify the file
            tool_file.write_text("def run(): return 42")

            await asyncio.sleep(0.2)

        assert len(changes) == 1
        assert changes[0] == tool_file

    @pytest.mark.asyncio
    async def test_file_deletion_triggers_on_delete(self, tmp_path: Path) -> None:
        """Test deleting a .py file triggers on_delete callback."""
        mcptools = tmp_path / "mcptools" / "cat"
        mcptools.mkdir(parents=True)
        tool_file = mcptools / "tool.py"
        tool_file.write_text("def run(): pass")

        deletes: list[Path] = []

        async def on_delete(path: Path) -> None:
            deletes.append(path)

        async with ToolWatcher(
            tmp_path,
            on_change=lambda p: asyncio.sleep(0),
            on_delete=on_delete,
            debounce_ms=50,
        ):
            # Delete the file
            tool_file.unlink()

            await asyncio.sleep(0.2)

        assert len(deletes) == 1
        assert deletes[0] == tool_file

    @pytest.mark.asyncio
    async def test_non_py_files_ignored(self, tmp_path: Path) -> None:
        """Test non-.py files don't trigger callbacks."""
        mcptools = tmp_path / "mcptools" / "cat"
        mcptools.mkdir(parents=True)

        changes: list[Path] = []

        async def on_change(path: Path) -> None:
            changes.append(path)

        async with ToolWatcher(
            tmp_path,
            on_change=on_change,
            on_delete=lambda p: asyncio.sleep(0),
            debounce_ms=50,
        ):
            # Create a non-.py file
            (mcptools / "readme.md").write_text("# Tool")

            await asyncio.sleep(0.2)

        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_callback_error_does_not_stop_watcher(self, tmp_path: Path) -> None:
        """Test that errors in callbacks don't stop the watcher."""
        mcptools = tmp_path / "mcptools" / "cat"
        mcptools.mkdir(parents=True)

        call_count = 0

        async def failing_callback(path: Path) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First call fails")

        async with ToolWatcher(
            tmp_path,
            on_change=failing_callback,
            on_delete=lambda p: asyncio.sleep(0),
            debounce_ms=50,
        ) as watcher:
            # First file - callback raises
            (mcptools / "tool1.py").write_text("def run(): pass")
            await asyncio.sleep(0.2)

            # Second file - callback should still be called
            (mcptools / "tool2.py").write_text("def run(): pass")
            await asyncio.sleep(0.2)

            # Watcher should still be running
            assert watcher.is_running is True

        assert call_count == 2


class TestToolWatcherDebounce:
    """Tests for debounce behavior."""

    @pytest.mark.asyncio
    async def test_rapid_changes_debounced(self, tmp_path: Path) -> None:
        """Test rapid changes to same file are debounced into one callback."""
        mcptools = tmp_path / "mcptools" / "cat"
        mcptools.mkdir(parents=True)
        tool_file = mcptools / "tool.py"
        tool_file.write_text("v1")

        changes: list[Path] = []

        async def on_change(path: Path) -> None:
            changes.append(path)

        async with ToolWatcher(
            tmp_path,
            on_change=on_change,
            on_delete=lambda p: asyncio.sleep(0),
            debounce_ms=100,
        ):
            # Rapid modifications
            for i in range(5):
                tool_file.write_text(f"v{i+2}")
                await asyncio.sleep(0.02)  # 20ms between writes

            # Wait for debounce
            await asyncio.sleep(0.3)

        # Should have fewer callbacks than writes due to debouncing
        # watchfiles batches these, so we expect 1-2 callbacks, not 5
        assert len(changes) < 5
