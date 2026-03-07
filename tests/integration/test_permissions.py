import json
from pathlib import Path

import pytest

from freeact.permissions import PermissionManager


@pytest.fixture
def freeact_dir(tmp_path: Path) -> Path:
    """Return the .freeact directory path (not yet created)."""
    return tmp_path / ".freeact"


@pytest.fixture
def permission_manager(freeact_dir: Path) -> PermissionManager:
    """Return a fresh PermissionManager instance."""
    return PermissionManager(freeact_dir)


class TestPatternMatching:
    """Tests for fnmatch glob matching."""

    def test_exact_match(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("github_search_repositories")
        assert permission_manager.check_tool("github_search_repositories") == "allow"

    def test_star_wildcard(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("github_*")
        assert permission_manager.check_tool("github_search_repositories") == "allow"
        assert permission_manager.check_tool("github_create_issue") == "allow"

    def test_question_mark_wildcard(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("tool_?")
        assert permission_manager.check_tool("tool_a") == "allow"
        assert permission_manager.check_tool("tool_ab") is None

    def test_no_match_returns_none(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("github_*")
        assert permission_manager.check_tool("filesystem_read_file") is None


class TestToolPermissionEvaluation:
    """Tests for check_tool() returning 'allow' / 'ask' / None."""

    def test_allow_always(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("my_tool")
        assert permission_manager.check_tool("my_tool") == "allow"

    def test_allow_session(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_session.append("my_tool")
        assert permission_manager.check_tool("my_tool") == "allow"

    def test_ask_always(self, permission_manager: PermissionManager):
        permission_manager._tool_ask_always.append("my_tool")
        assert permission_manager.check_tool("my_tool") == "ask"

    def test_ask_session(self, permission_manager: PermissionManager):
        permission_manager._tool_ask_session.append("my_tool")
        assert permission_manager.check_tool("my_tool") == "ask"

    def test_ask_overrides_allow(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("my_tool")
        permission_manager._tool_ask_always.append("my_tool")
        assert permission_manager.check_tool("my_tool") == "ask"

    def test_ask_session_overrides_allow_always(self, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("my_tool")
        permission_manager._tool_ask_session.append("my_tool")
        assert permission_manager.check_tool("my_tool") == "ask"

    def test_no_match(self, permission_manager: PermissionManager):
        assert permission_manager.check_tool("unknown_tool") is None

    def test_evaluation_order_ask_session_first(self, permission_manager: PermissionManager):
        """Ask-session is checked before ask-always."""
        permission_manager._tool_ask_session.append("tool_*")
        permission_manager._tool_ask_always.append("tool_a")
        # Both match, but ask-session wins (first match in evaluation order)
        assert permission_manager.check_tool("tool_a") == "ask"


class TestShellPermissionEvaluation:
    """Tests for check_shell() returning 'allow' / 'ask' / None."""

    def test_allow_always(self, permission_manager: PermissionManager):
        permission_manager._shell_allow_always.append("git *")
        assert permission_manager.check_shell("git status") == "allow"

    def test_allow_session(self, permission_manager: PermissionManager):
        permission_manager._shell_allow_session.append("git *")
        assert permission_manager.check_shell("git push origin main") == "allow"

    def test_ask_always(self, permission_manager: PermissionManager):
        permission_manager._shell_ask_always.append("rm *")
        assert permission_manager.check_shell("rm -rf /") == "ask"

    def test_ask_overrides_allow(self, permission_manager: PermissionManager):
        permission_manager._shell_allow_always.append("git *")
        permission_manager._shell_ask_always.append("git push *")
        assert permission_manager.check_shell("git push origin main") == "ask"

    def test_no_match(self, permission_manager: PermissionManager):
        assert permission_manager.check_shell("curl http://example.com") is None


class TestNewPersistence:
    """Tests for new JSON format save/load, migration, and roundtrip."""

    @pytest.mark.asyncio
    async def test_new_format_save(self, freeact_dir: Path, permission_manager: PermissionManager):
        permission_manager._tool_allow_always.append("github_*")
        permission_manager._tool_ask_always.append("dangerous_tool")
        permission_manager._shell_allow_always.append("git *")
        permission_manager._shell_ask_always.append("rm *")

        await permission_manager.save()

        data = json.loads((freeact_dir / "permissions.json").read_text())
        assert data == {
            "tool_permissions": {
                "ask": ["dangerous_tool"],
                "allow": ["github_*"],
            },
            "shell_permissions": {
                "ask": ["rm *"],
                "allow": ["git *"],
            },
        }

    @pytest.mark.asyncio
    async def test_new_format_load(self, freeact_dir: Path):
        freeact_dir.mkdir(parents=True)
        data = {
            "tool_permissions": {
                "ask": ["dangerous_*"],
                "allow": ["safe_*"],
            },
            "shell_permissions": {
                "ask": ["rm *"],
                "allow": ["git *"],
            },
        }
        (freeact_dir / "permissions.json").write_text(json.dumps(data))

        manager = PermissionManager(freeact_dir)
        await manager.load()

        assert manager._tool_ask_always == ["dangerous_*"]
        assert manager._tool_allow_always == ["safe_*"]
        assert manager._shell_ask_always == ["rm *"]
        assert manager._shell_allow_always == ["git *"]

    @pytest.mark.asyncio
    async def test_old_format_migration(self, freeact_dir: Path):
        """Old format with 'allowed_tools' is auto-migrated."""
        freeact_dir.mkdir(parents=True)
        old_data = {"allowed_tools": ["tool_a", "tool_b"]}
        (freeact_dir / "permissions.json").write_text(json.dumps(old_data))

        manager = PermissionManager(freeact_dir)
        await manager.load()

        assert manager._tool_allow_always == ["tool_a", "tool_b"]
        assert manager._tool_ask_always == []

        # Verify re-save uses new format
        await manager.save()
        new_data = json.loads((freeact_dir / "permissions.json").read_text())
        assert "allowed_tools" not in new_data
        assert new_data["tool_permissions"]["allow"] == ["tool_a", "tool_b"]

    @pytest.mark.asyncio
    async def test_roundtrip(self, freeact_dir: Path):
        manager1 = PermissionManager(freeact_dir)
        manager1._tool_allow_always = ["github_*", "filesystem_*"]
        manager1._tool_ask_always = ["dangerous_*"]
        manager1._shell_allow_always = ["git *"]
        manager1._shell_ask_always = ["rm *"]
        await manager1.save()

        manager2 = PermissionManager(freeact_dir)
        await manager2.load()

        assert manager2._tool_allow_always == ["github_*", "filesystem_*"]
        assert manager2._tool_ask_always == ["dangerous_*"]
        assert manager2._shell_allow_always == ["git *"]
        assert manager2._shell_ask_always == ["rm *"]

    @pytest.mark.asyncio
    async def test_load_empty(self, permission_manager: PermissionManager):
        """Load from non-existent file returns empty lists."""
        await permission_manager.load()
        assert permission_manager._tool_allow_always == []
        assert permission_manager._tool_ask_always == []
        assert permission_manager._shell_allow_always == []
        assert permission_manager._shell_ask_always == []


class TestPatternSuggestion:
    """Tests for suggest_tool_pattern() and suggest_shell_pattern()."""

    def test_suggest_tool_pattern_returns_full_name(self, permission_manager: PermissionManager):
        assert permission_manager.suggest_tool_pattern("github_search_repositories") == "github_search_repositories"

    def test_suggest_shell_pattern_command_with_subcommand(self, permission_manager: PermissionManager):
        assert permission_manager.suggest_shell_pattern("git add /path/to/file.py") == "git add *"

    def test_suggest_shell_pattern_single_token(self, permission_manager: PermissionManager):
        assert permission_manager.suggest_shell_pattern("ls") == "ls *"

    def test_suggest_shell_pattern_command_only(self, permission_manager: PermissionManager):
        assert permission_manager.suggest_shell_pattern("ls -la /tmp") == "ls *"

    def test_suggest_shell_pattern_pip_install(self, permission_manager: PermissionManager):
        assert permission_manager.suggest_shell_pattern("pip install pandas") == "pip install *"


class TestIsAllowedBackwardCompat:
    """Tests for is_allowed() backward compatibility."""

    @pytest.mark.asyncio
    async def test_is_allowed_true_when_check_tool_returns_allow(self, permission_manager: PermissionManager):
        await permission_manager.allow_always("my_tool", domain="tool")
        assert permission_manager.is_allowed("my_tool")

    def test_is_allowed_false_when_no_match(self, permission_manager: PermissionManager):
        assert not permission_manager.is_allowed("unknown")

    def test_is_allowed_false_when_ask(self, permission_manager: PermissionManager):
        permission_manager._tool_ask_always.append("my_tool")
        assert not permission_manager.is_allowed("my_tool")

    def test_is_allowed_filesystem_auto_approval(self, freeact_dir: Path, permission_manager: PermissionManager):
        target = str(freeact_dir / "subdir" / "file.txt")
        assert permission_manager.is_allowed("filesystem_read_file", {"path": target})

    def test_is_allowed_filesystem_outside_freeact(self, tmp_path: Path, permission_manager: PermissionManager):
        outside = str(tmp_path / "outside" / "file.txt")
        assert not permission_manager.is_allowed("filesystem_read_file", {"path": outside})


class TestAllowMethods:
    """Tests for allow_always() and allow_session() with domain parameter."""

    @pytest.mark.asyncio
    async def test_allow_always_tool(self, permission_manager: PermissionManager):
        await permission_manager.allow_always("github_*", domain="tool")
        assert "github_*" in permission_manager._tool_allow_always

    @pytest.mark.asyncio
    async def test_allow_always_shell(self, permission_manager: PermissionManager):
        await permission_manager.allow_always("git *", domain="shell")
        assert "git *" in permission_manager._shell_allow_always

    def test_allow_session_tool(self, permission_manager: PermissionManager):
        permission_manager.allow_session("github_*", domain="tool")
        assert "github_*" in permission_manager._tool_allow_session

    def test_allow_session_shell(self, permission_manager: PermissionManager):
        permission_manager.allow_session("git *", domain="shell")
        assert "git *" in permission_manager._shell_allow_session

    @pytest.mark.asyncio
    async def test_allow_always_persists(self, freeact_dir: Path):
        manager1 = PermissionManager(freeact_dir)
        await manager1.allow_always("github_*", domain="tool")

        manager2 = PermissionManager(freeact_dir)
        await manager2.load()
        assert "github_*" in manager2._tool_allow_always

    def test_allow_session_not_persisted(self, freeact_dir: Path):
        manager1 = PermissionManager(freeact_dir)
        manager1.allow_session("temp_tool", domain="tool")

        manager2 = PermissionManager(freeact_dir)
        assert "temp_tool" not in manager2._tool_allow_session


class TestPermissionManagerInit:
    """Tests for initialization behavior."""

    def test_init_does_not_create_freeact_directory(self, freeact_dir: Path):
        """Constructor does not eagerly create the .freeact/ directory."""
        assert not freeact_dir.exists()
        PermissionManager(freeact_dir)
        assert not freeact_dir.exists()

    @pytest.mark.asyncio
    async def test_save_creates_freeact_directory(self, freeact_dir: Path):
        """Saving creates the .freeact/ directory if it doesn't exist."""
        manager = PermissionManager(freeact_dir)
        assert not freeact_dir.exists()
        await manager.save()
        assert freeact_dir.exists()

    def test_init_sets_permissions_file_path(self, freeact_dir: Path, permission_manager: PermissionManager):
        expected_path = freeact_dir / "permissions.json"
        assert permission_manager._permissions_file == expected_path

    def test_init_initializes_empty_lists(self, permission_manager: PermissionManager):
        assert permission_manager._tool_allow_always == []
        assert permission_manager._tool_ask_always == []
        assert permission_manager._tool_allow_session == []
        assert permission_manager._tool_ask_session == []
        assert permission_manager._shell_allow_always == []
        assert permission_manager._shell_ask_always == []
        assert permission_manager._shell_allow_session == []
        assert permission_manager._shell_ask_session == []
