import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from watchfiles import Change

from freeact.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR
from freeact.tools.pytools.search.hybrid.watch import ToolWatcher


def create_tool_watcher(
    base_dir: Path,
    on_change: Callable[[Path], Awaitable[None]] | None = None,
    on_delete: Callable[[Path], Awaitable[None]] | None = None,
    **kwargs: int,
) -> ToolWatcher:
    async def _noop(path: Path) -> None:
        pass

    return ToolWatcher(
        base_dir,
        on_change=on_change or _noop,
        on_delete=on_delete or _noop,
        **kwargs,
    )


def recorder() -> tuple[list[Path], Callable[[Path], Awaitable[None]]]:
    events: list[Path] = []

    async def record(path: Path) -> None:
        events.append(path)

    return events, record


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        (f"{MCPTOOLS_DIR}/github/create_issue.py", True),
        (f"{GENTOOLS_DIR}/data/csv_parser/api.py", True),
        (f"{MCPTOOLS_DIR}/github/readme.md", False),
        ("other/file.py", False),
    ],
)
def test_watch_filter(tmp_path: Path, relative: str, expected: bool) -> None:
    watcher = create_tool_watcher(tmp_path)

    assert watcher._watch_filter(Change.modified, str(tmp_path / relative)) is expected


def test_filter_rejects_files_outside_base_dir(tmp_path: Path) -> None:
    watcher = create_tool_watcher(tmp_path / "workspace")

    assert watcher._watch_filter(Change.modified, str(tmp_path / MCPTOOLS_DIR / "tool.py")) is False


@pytest.mark.asyncio
async def test_start_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / MCPTOOLS_DIR).mkdir()
    watcher = create_tool_watcher(tmp_path)

    await watcher.start()
    await watcher.start()  # Should not raise
    try:
        assert watcher.is_running is True
    finally:
        await watcher.stop()


@pytest.mark.asyncio
async def test_stop_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / MCPTOOLS_DIR).mkdir()
    watcher = create_tool_watcher(tmp_path)

    await watcher.start()
    await watcher.stop()
    await watcher.stop()  # Should not raise

    assert watcher.is_running is False


@pytest.mark.asyncio
async def test_context_manager(tmp_path: Path) -> None:
    (tmp_path / MCPTOOLS_DIR).mkdir()

    async with create_tool_watcher(tmp_path) as watcher:
        assert watcher.is_running is True

    assert watcher.is_running is False


@pytest.mark.asyncio
async def test_no_directories_to_watch(tmp_path: Path) -> None:
    watcher = create_tool_watcher(tmp_path)

    await watcher.start()
    try:
        assert watcher.is_running is True
    finally:
        await watcher.stop()


@pytest.mark.asyncio
async def test_file_creation_triggers_on_change(tmp_path: Path) -> None:
    mcptools = tmp_path / MCPTOOLS_DIR / "cat"
    mcptools.mkdir(parents=True)
    changes, on_change = recorder()

    async with create_tool_watcher(tmp_path, on_change=on_change, debounce_ms=50):
        tool_file = mcptools / "tool.py"
        tool_file.write_text("def run(): pass")

        await asyncio.sleep(0.2)

    assert changes == [tool_file]


@pytest.mark.asyncio
async def test_file_modification_triggers_on_change(tmp_path: Path) -> None:
    mcptools = tmp_path / MCPTOOLS_DIR / "cat"
    mcptools.mkdir(parents=True)
    tool_file = mcptools / "tool.py"
    tool_file.write_text("def run(): pass")
    changes, on_change = recorder()

    async with create_tool_watcher(tmp_path, on_change=on_change, debounce_ms=50):
        tool_file.write_text("def run(): return 42")

        await asyncio.sleep(0.2)

    assert changes == [tool_file]


@pytest.mark.asyncio
async def test_file_deletion_triggers_on_delete(tmp_path: Path) -> None:
    mcptools = tmp_path / MCPTOOLS_DIR / "cat"
    mcptools.mkdir(parents=True)
    tool_file = mcptools / "tool.py"
    tool_file.write_text("def run(): pass")
    deletes, on_delete = recorder()

    async with create_tool_watcher(tmp_path, on_delete=on_delete, debounce_ms=50):
        tool_file.unlink()

        await asyncio.sleep(0.2)

    assert deletes == [tool_file]


@pytest.mark.asyncio
async def test_non_py_files_ignored(tmp_path: Path) -> None:
    mcptools = tmp_path / MCPTOOLS_DIR / "cat"
    mcptools.mkdir(parents=True)
    changes, on_change = recorder()

    async with create_tool_watcher(tmp_path, on_change=on_change, debounce_ms=50):
        (mcptools / "readme.md").write_text("# Tool")

        await asyncio.sleep(0.2)

    assert changes == []


@pytest.mark.asyncio
async def test_callback_error_does_not_stop_watcher(tmp_path: Path) -> None:
    mcptools = tmp_path / MCPTOOLS_DIR / "cat"
    mcptools.mkdir(parents=True)

    call_count = 0

    async def failing_callback(path: Path) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("First call fails")

    async with create_tool_watcher(tmp_path, on_change=failing_callback, debounce_ms=50) as watcher:
        (mcptools / "tool1.py").write_text("def run(): pass")
        await asyncio.sleep(0.2)

        (mcptools / "tool2.py").write_text("def run(): pass")
        await asyncio.sleep(0.2)

        assert watcher.is_running is True

    assert call_count == 2


@pytest.mark.asyncio
async def test_rapid_changes_debounced(tmp_path: Path) -> None:
    mcptools = tmp_path / MCPTOOLS_DIR / "cat"
    mcptools.mkdir(parents=True)
    tool_file = mcptools / "tool.py"
    tool_file.write_text("v1")
    changes, on_change = recorder()

    async with create_tool_watcher(tmp_path, on_change=on_change, debounce_ms=100):
        for i in range(5):
            tool_file.write_text(f"v{i + 2}")
            await asyncio.sleep(0.02)  # 20ms between writes

        # Wait for debounce
        await asyncio.sleep(0.3)

    # watchfiles batches rapid changes, so we expect 1-2 callbacks, not 5
    assert len(changes) < 5
