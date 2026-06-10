import asyncio
from pathlib import Path

import pytest

from freeact.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR
from freeact.tools.pytools.hybrid.database import Database
from freeact.tools.pytools.hybrid.embed import ToolEmbedder
from freeact.tools.pytools.hybrid.index import Indexer, SyncResult

MCPTOOL_ID = f"{MCPTOOLS_DIR}:cat:tool"
GENTOOL_ID = f"{GENTOOLS_DIR}:cat:tool"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    base_dir = tmp_path / "workspace"
    base_dir.mkdir()
    return base_dir


def write_tool(base_dir: Path, relative: str, docstring: str) -> Path:
    tool_file = base_dir / relative
    tool_file.parent.mkdir(parents=True, exist_ok=True)
    tool_file.write_text(f'def run():\n    """{docstring}"""\n    pass\n')
    return tool_file


def test_sync_result_fields() -> None:
    result = SyncResult(added=5, updated=2, deleted=1)

    assert result.added == 5
    assert result.updated == 2
    assert result.deleted == 1


@pytest.mark.asyncio
async def test_sync_empty_directory(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    indexer = Indexer(db, embedder, workspace)
    result = await indexer.sync()

    assert result.added == 0
    assert result.updated == 0
    assert result.deleted == 0


@pytest.mark.asyncio
async def test_sync_indexes_new_tools(db: Database, embedder: ToolEmbedder, fixtures_dir: Path) -> None:
    indexer = Indexer(db, embedder, fixtures_dir)
    result = await indexer.sync()

    assert isinstance(result, SyncResult)
    assert result.added >= 3  # create_issue, list_repos, csv_parser
    assert result.updated == 0
    assert result.deleted == 0

    assert await db.exists(f"{MCPTOOLS_DIR}:github:create_issue")
    assert await db.exists(f"{MCPTOOLS_DIR}:github:list_repos")
    assert await db.exists(f"{GENTOOLS_DIR}:data:csv_parser")


@pytest.mark.asyncio
async def test_sync_skips_unchanged_tools(db: Database, embedder: ToolEmbedder, fixtures_dir: Path) -> None:
    indexer = Indexer(db, embedder, fixtures_dir)

    result1 = await indexer.sync()
    result2 = await indexer.sync()

    assert result1.added > 0
    assert result2.added == 0
    assert result2.updated == 0
    assert result2.deleted == 0


@pytest.mark.asyncio
async def test_sync_detects_modified_tools(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    write_tool(workspace, f"{MCPTOOLS_DIR}/cat/tool.py", "Original docstring.")
    indexer = Indexer(db, embedder, workspace)

    result1 = await indexer.sync()
    original_entry = await db.get(MCPTOOL_ID)
    assert original_entry is not None

    write_tool(workspace, f"{MCPTOOLS_DIR}/cat/tool.py", "Modified docstring.")

    result2 = await indexer.sync()
    modified_entry = await db.get(MCPTOOL_ID)

    assert result1.added == 1
    assert result2.updated == 1
    assert result2.added == 0
    assert modified_entry is not None
    assert modified_entry.file_hash != original_entry.file_hash
    assert "Modified" in modified_entry.description


@pytest.mark.asyncio
async def test_sync_removes_deleted_tools(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    tool_file = write_tool(workspace, f"{MCPTOOLS_DIR}/cat/tool.py", "Docstring.")
    indexer = Indexer(db, embedder, workspace)

    await indexer.sync()
    assert await db.exists(MCPTOOL_ID)

    tool_file.unlink()
    result = await indexer.sync()

    assert result.deleted == 1
    assert not await db.exists(MCPTOOL_ID)


@pytest.mark.asyncio
async def test_handle_file_change_indexes_new_tool(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    tool_file = write_tool(workspace, f"{MCPTOOLS_DIR}/cat/tool.py", "New tool docstring.")
    indexer = Indexer(db, embedder, workspace)

    await indexer.handle_file_change(tool_file)

    entry = await db.get(MCPTOOL_ID)
    assert entry is not None
    assert "New tool" in entry.description


@pytest.mark.asyncio
async def test_handle_file_change_updates_existing_tool(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    tool_file = write_tool(workspace, f"{MCPTOOLS_DIR}/cat/tool.py", "Original.")
    indexer = Indexer(db, embedder, workspace)

    await indexer.handle_file_change(tool_file)
    original = await db.get(MCPTOOL_ID)

    write_tool(workspace, f"{MCPTOOLS_DIR}/cat/tool.py", "Updated.")
    await indexer.handle_file_change(tool_file)
    updated = await db.get(MCPTOOL_ID)

    assert original is not None
    assert updated is not None
    assert "Original" in original.description
    assert "Updated" in updated.description


@pytest.mark.asyncio
async def test_handle_file_change_ignores_invalid_path(
    db: Database, embedder: ToolEmbedder, workspace: Path, tmp_path: Path
) -> None:
    other_file = tmp_path / "other.py"
    other_file.write_text('def run():\n    """Not a tool."""\n    pass\n')
    indexer = Indexer(db, embedder, workspace)

    await indexer.handle_file_change(other_file)

    assert await db.list_ids() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("relative", "tool_id"),
    [
        (f"{MCPTOOLS_DIR}/cat/tool.py", MCPTOOL_ID),
        (f"{GENTOOLS_DIR}/cat/tool/api.py", GENTOOL_ID),
    ],
)
async def test_handle_file_delete_removes_tool(
    db: Database, embedder: ToolEmbedder, workspace: Path, relative: str, tool_id: str
) -> None:
    tool_file = write_tool(workspace, relative, "Doc.")
    indexer = Indexer(db, embedder, workspace)

    await indexer.handle_file_change(tool_file)
    assert await db.exists(tool_id)

    tool_file.unlink()
    await indexer.handle_file_delete(tool_file)

    assert not await db.exists(tool_id)


@pytest.mark.asyncio
async def test_handle_file_delete_ignores_invalid_path(
    db: Database, embedder: ToolEmbedder, workspace: Path, tmp_path: Path
) -> None:
    indexer = Indexer(db, embedder, workspace)

    await indexer.handle_file_delete(tmp_path / "other.py")


@pytest.mark.asyncio
async def test_sync_works_without_watcher(db: Database, embedder: ToolEmbedder, fixtures_dir: Path) -> None:
    indexer = Indexer(db, embedder, fixtures_dir)

    assert indexer._watcher is None

    result = await indexer.sync()
    assert result.added >= 3

    assert indexer._watcher is None


@pytest.mark.asyncio
async def test_watch_and_unwatch(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    (workspace / MCPTOOLS_DIR).mkdir()
    indexer = Indexer(db, embedder, workspace)

    await indexer.watch()
    assert indexer._watcher is not None
    assert indexer._watcher.is_running is True

    await indexer.unwatch()
    await indexer.unwatch()  # idempotent, should not raise


@pytest.mark.asyncio
async def test_context_manager_starts_watcher(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    (workspace / MCPTOOLS_DIR).mkdir()
    indexer = Indexer(db, embedder, workspace)

    async with indexer:
        assert indexer._watcher is not None
        assert indexer._watcher.is_running is True

    assert indexer._watcher is None


@pytest.mark.asyncio
async def test_context_manager_does_not_sync(db: Database, embedder: ToolEmbedder, fixtures_dir: Path) -> None:
    async with Indexer(db, embedder, fixtures_dir):
        assert not await db.exists(f"{MCPTOOLS_DIR}:github:create_issue")


@pytest.mark.asyncio
async def test_watcher_indexes_new_file(db: Database, embedder: ToolEmbedder, workspace: Path) -> None:
    (workspace / MCPTOOLS_DIR / "cat").mkdir(parents=True)

    async with Indexer(db, embedder, workspace):
        write_tool(workspace, f"{MCPTOOLS_DIR}/cat/new_tool.py", "A brand new tool.")

        # Wait for debounce + processing
        await asyncio.sleep(0.5)

        entry = await db.get(f"{MCPTOOLS_DIR}:cat:new_tool")
        assert entry is not None
        assert "brand new" in entry.description


@pytest.mark.asyncio
async def test_sync_works_with_watcher_running(db: Database, embedder: ToolEmbedder, fixtures_dir: Path) -> None:
    async with Indexer(db, embedder, fixtures_dir) as indexer:
        assert indexer._watcher is not None

        result = await indexer.sync()
        assert result.added >= 3
        assert await db.exists(f"{MCPTOOLS_DIR}:github:create_issue")
