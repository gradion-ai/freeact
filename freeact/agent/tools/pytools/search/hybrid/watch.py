"""File watcher for real-time tool directory monitoring."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from types import TracebackType

from watchfiles import Change, awatch

from freeact.agent.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR


class ToolWatcher:
    """Watches mcptools/ and gentools/ for file changes.

    Monitors tool directories recursively for Python file changes and
    invokes callbacks for create/modify and delete events. Includes
    debouncing to handle rapid successive changes.

    Args:
        base_dir: Base directory containing mcptools/ and gentools/.
        on_change: Async callback for file creation or modification.
        on_delete: Async callback for file deletion.
        debounce_ms: Debounce window in milliseconds. Default 300ms.

    Example:
        ```python
        async def handle_change(path: Path) -> None:
            print(f"Changed: {path}")

        async def handle_delete(path: Path) -> None:
            print(f"Deleted: {path}")

        async with ToolWatcher(base_dir, handle_change, handle_delete):
            # Watcher is running
            await asyncio.sleep(60)
        ```
    """

    def __init__(
        self,
        base_dir: Path,
        on_change: Callable[[Path], Awaitable[None]],
        on_delete: Callable[[Path], Awaitable[None]],
        debounce_ms: int = 300,
    ) -> None:
        self._base_dir = base_dir
        self._on_change = on_change
        self._on_delete = on_delete
        self._debounce_ms = debounce_ms
        self._watch_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def _watch_filter(self, change: Change, path: str) -> bool:
        """Filter to only watch Python files in tool directories.

        Args:
            change: Type of change (added, modified, deleted).
            path: Path to the changed file.

        Returns:
            True if the change should be processed.
        """
        p = Path(path)

        # Only watch .py files
        if p.suffix != ".py":
            return False

        # Must be under mcptools/ or gentools/
        try:
            rel = p.relative_to(self._base_dir)
            parts = rel.parts
            if not parts:
                return False
            return parts[0] in (MCPTOOLS_DIR, GENTOOLS_DIR)
        except ValueError:
            return False

    async def _watch_loop(self) -> None:
        """Main watch loop that processes file changes."""
        # Collect directories to watch
        watch_paths: list[Path] = []

        mcptools = self._base_dir / MCPTOOLS_DIR
        if mcptools.is_dir():
            watch_paths.append(mcptools)

        gentools = self._base_dir / GENTOOLS_DIR
        if gentools.is_dir():
            watch_paths.append(gentools)

        if not watch_paths:
            # Nothing to watch, wait for stop
            await self._stop_event.wait()
            return

        async for changes in awatch(
            *watch_paths,
            watch_filter=self._watch_filter,
            debounce=self._debounce_ms,
            stop_event=self._stop_event,
            recursive=True,
        ):
            for change_type, path_str in changes:
                path = Path(path_str)
                try:
                    match change_type:
                        case Change.added | Change.modified:
                            await self._on_change(path)
                        case Change.deleted:
                            await self._on_delete(path)
                except Exception:
                    # Log errors but continue watching
                    # In production, this would use proper logging
                    pass

    async def start(self) -> None:
        """Start watching for file changes.

        Creates a background task that monitors tool directories.
        """
        if self._watch_task is not None:
            return

        self._stop_event.clear()
        self._watch_task = asyncio.create_task(self._watch_loop())
        # Allow watcher to initialize (needed for Linux inotify)
        await asyncio.sleep(0.05)

    async def stop(self) -> None:
        """Stop watching for file changes.

        Signals the watch loop to stop and waits for it to complete.
        """
        if self._watch_task is None:
            return

        self._stop_event.set()

        try:
            await self._watch_task
        except asyncio.CancelledError:
            pass

        self._watch_task = None

    @property
    def is_running(self) -> bool:
        """Whether the watcher is currently running."""
        return self._watch_task is not None and not self._watch_task.done()

    async def __aenter__(self) -> ToolWatcher:
        """Start watching on context entry."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop watching on context exit."""
        await self.stop()
