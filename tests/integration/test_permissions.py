import json
from pathlib import Path

import pytest

from freeact.agent.config.config import _ConfigPaths
from freeact.permissions import PermissionManager


@pytest.fixture
def freeact_dir(tmp_path: Path) -> Path:
    """Return the .freeact directory path (not yet created)."""
    return _ConfigPaths(tmp_path).freeact_dir


@pytest.fixture
def permission_manager(freeact_dir: Path) -> PermissionManager:
    """Return a fresh PermissionManager instance."""
    return PermissionManager(freeact_dir)


class TestPermissionManagerPersistence:
    """Tests for file-based persistence (load/save)."""

    @pytest.mark.asyncio
    async def test_load_empty_permissions(self, permission_manager: PermissionManager):
        """Load from non-existent file returns empty allowed set."""
        await permission_manager.load()

        assert permission_manager._allowed_always == set()
        assert permission_manager._allowed_session == set()

    @pytest.mark.asyncio
    async def test_load_existing_permissions(self, freeact_dir: Path):
        """Load from existing permissions.json correctly populates _allowed_always."""
        freeact_dir.mkdir(parents=True)
        permissions_file = freeact_dir / "permissions.json"
        permissions_file.write_text(json.dumps({"allowed_tools": ["tool_a", "tool_b"]}))

        manager = PermissionManager(freeact_dir)
        await manager.load()

        assert manager._allowed_always == {"tool_a", "tool_b"}

    @pytest.mark.asyncio
    async def test_save_creates_file(self, freeact_dir: Path, permission_manager: PermissionManager):
        """Saving permissions creates the JSON file with correct structure."""
        permission_manager._allowed_always = {"tool_x", "tool_y"}

        await permission_manager.save()

        permissions_file = freeact_dir / "permissions.json"
        assert permissions_file.exists()
        data = json.loads(permissions_file.read_text())
        assert data == {"allowed_tools": ["tool_x", "tool_y"]}

    @pytest.mark.asyncio
    async def test_save_load_roundtrip(self, freeact_dir: Path):
        """Permissions survive save/load cycle with correct data."""
        manager1 = PermissionManager(freeact_dir)
        manager1._allowed_always = {"alpha", "beta", "gamma"}
        await manager1.save()

        manager2 = PermissionManager(freeact_dir)
        await manager2.load()

        assert manager2._allowed_always == {"alpha", "beta", "gamma"}


class TestPermissionManagerAllowMethods:
    """Tests for allow_always() and allow_session() methods."""

    @pytest.mark.asyncio
    async def test_allow_always_persists(self, freeact_dir: Path):
        """Calling allow_always() saves to disk and new instance can load it."""
        manager1 = PermissionManager(freeact_dir)
        await manager1.allow_always("persistent_tool")

        manager2 = PermissionManager(freeact_dir)
        await manager2.load()

        assert "persistent_tool" in manager2._allowed_always

    @pytest.mark.asyncio
    async def test_allow_session_not_persisted(self, freeact_dir: Path, permission_manager: PermissionManager):
        """Session permissions are not written to disk."""
        permission_manager.allow_session("session_tool")

        permissions_file = freeact_dir / "permissions.json"
        if permissions_file.exists():
            data = json.loads(permissions_file.read_text())
            assert "session_tool" not in data.get("allowed_tools", [])

    @pytest.mark.asyncio
    async def test_allow_session_clears_on_new_instance(self, freeact_dir: Path):
        """Session permissions don't survive new instance creation."""
        manager1 = PermissionManager(freeact_dir)
        manager1.allow_session("ephemeral_tool")
        assert manager1.is_allowed("ephemeral_tool")

        manager2 = PermissionManager(freeact_dir)
        await manager2.load()

        assert not manager2.is_allowed("ephemeral_tool")


class TestPermissionManagerIsAllowed:
    """Tests for is_allowed() logic."""

    @pytest.mark.asyncio
    async def test_is_allowed_always_tool(self, permission_manager: PermissionManager):
        """Returns True for always-allowed tools."""
        await permission_manager.allow_always("allowed_tool")

        assert permission_manager.is_allowed("allowed_tool")

    def test_is_allowed_session_tool(self, permission_manager: PermissionManager):
        """Returns True for session-allowed tools."""
        permission_manager.allow_session("session_tool")

        assert permission_manager.is_allowed("session_tool")

    def test_is_allowed_unknown_tool(self, permission_manager: PermissionManager):
        """Returns False for unknown tools."""
        assert not permission_manager.is_allowed("unknown_tool")

    def test_is_allowed_filesystem_within_freeact(self, freeact_dir: Path, permission_manager: PermissionManager):
        """Returns True for filesystem tools targeting paths within .freeact/."""
        target_path = str(freeact_dir / "subdir" / "file.txt")

        assert permission_manager.is_allowed("filesystem_read_file", {"path": target_path})
        assert permission_manager.is_allowed("filesystem_write_file", {"path": target_path})
        assert permission_manager.is_allowed("filesystem_edit_file", {"path": target_path})

    def test_is_allowed_filesystem_outside_freeact(self, tmp_path: Path, permission_manager: PermissionManager):
        """Returns False for filesystem tools targeting paths outside .freeact/."""
        outside_path = str(tmp_path / "outside" / "file.txt")

        assert not permission_manager.is_allowed("filesystem_read_file", {"path": outside_path})
        assert not permission_manager.is_allowed("filesystem_write_file", {"path": outside_path})

    def test_is_allowed_filesystem_multiple_paths(self, freeact_dir: Path, permission_manager: PermissionManager):
        """Tests paths argument with all paths within .freeact/."""
        paths = [
            str(freeact_dir / "file1.txt"),
            str(freeact_dir / "subdir" / "file2.txt"),
        ]

        assert permission_manager.is_allowed("filesystem_read_multiple_files", {"paths": paths})

    def test_is_allowed_filesystem_mixed_paths(
        self, tmp_path: Path, freeact_dir: Path, permission_manager: PermissionManager
    ):
        """Returns False when any path is outside .freeact/."""
        paths = [
            str(freeact_dir / "inside.txt"),
            str(tmp_path / "outside.txt"),
        ]

        assert not permission_manager.is_allowed("filesystem_read_multiple_files", {"paths": paths})

    def test_is_allowed_filesystem_freeact_dir_itself(self, freeact_dir: Path, permission_manager: PermissionManager):
        """Returns True when targeting the .freeact/ directory itself."""
        assert permission_manager.is_allowed("filesystem_list_directory", {"path": str(freeact_dir)})

    def test_is_allowed_non_filesystem_tool_with_path(self, freeact_dir: Path, permission_manager: PermissionManager):
        """Non-filesystem tools with path args are not auto-approved."""
        target_path = str(freeact_dir / "file.txt")

        assert not permission_manager.is_allowed("some_other_tool", {"path": target_path})


class TestPermissionManagerInit:
    """Tests for initialization behavior."""

    def test_init_creates_freeact_directory(self, freeact_dir: Path):
        """Constructor creates the .freeact/ directory if it doesn't exist."""
        assert not freeact_dir.exists()

        PermissionManager(freeact_dir)

        assert freeact_dir.exists()
        assert freeact_dir.is_dir()

    def test_init_uses_existing_directory(self, freeact_dir: Path):
        """Constructor works with existing directory."""
        freeact_dir.mkdir(parents=True)
        marker_file = freeact_dir / "marker.txt"
        marker_file.write_text("exists")

        PermissionManager(freeact_dir)

        assert marker_file.exists()
        assert marker_file.read_text() == "exists"

    def test_init_sets_permissions_file_path(self, freeact_dir: Path, permission_manager: PermissionManager):
        """Constructor sets the correct permissions file path."""
        expected_path = freeact_dir / "permissions.json"
        assert permission_manager._permissions_file == expected_path

    def test_init_initializes_empty_permission_sets(self, permission_manager: PermissionManager):
        """Constructor initializes empty permission sets."""
        assert permission_manager._allowed_always == set()
        assert permission_manager._allowed_session == set()
