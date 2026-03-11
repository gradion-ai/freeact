import json
from pathlib import Path

import pytest

from freeact.agent.call import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    TextEdit,
)
from freeact.permissions import DEFAULT_ALLOW_RULES, PermissionManager


@pytest.fixture
def freeact_dir(tmp_path: Path) -> Path:
    """Return the .freeact directory path (not yet created)."""
    return tmp_path / ".freeact"


@pytest.fixture
def working_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def permission_manager(working_dir: Path, freeact_dir: Path) -> PermissionManager:
    """Return a fresh PermissionManager instance."""
    return PermissionManager(working_dir, freeact_dir)


class TestTypeSpecificMatching:
    """Tests for is_allowed() with type-specific ToolCall matching."""

    def test_generic_call_wildcard(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(GenericCall(tool_name="github_*", tool_args={}, ptc=False))
        tc = GenericCall(tool_name="github_search_repositories", tool_args={"q": "test"}, ptc=False)
        assert permission_manager.is_allowed(tc)

    def test_generic_call_exact(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(GenericCall(tool_name="github_search_repositories", tool_args={}, ptc=False))
        tc = GenericCall(tool_name="github_search_repositories", tool_args={"q": "test"}, ptc=False)
        assert permission_manager.is_allowed(tc)

    def test_generic_call_no_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(GenericCall(tool_name="github_*", tool_args={}, ptc=False))
        tc = GenericCall(tool_name="filesystem_read_file", tool_args={}, ptc=False)
        assert not permission_manager.is_allowed(tc)

    def test_shell_action_tool_name_and_command(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(ShellAction(tool_name="bash", command="git *"))
        tc = ShellAction(tool_name="bash", command="git status")
        assert permission_manager.is_allowed(tc)

    def test_shell_action_command_mismatch(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(ShellAction(tool_name="bash", command="git *"))
        tc = ShellAction(tool_name="bash", command="rm -rf /")
        assert not permission_manager.is_allowed(tc)

    def test_code_action_tool_name_only(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(CodeAction(tool_name="ipybox_*", code=""))
        tc = CodeAction(tool_name="ipybox_execute_ipython_cell", code="print(1)")
        assert permission_manager.is_allowed(tc)

    def test_file_read_all_paths_must_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/**",), head=None, tail=None))
        tc = FileRead(
            tool_name="filesystem_read_file",
            paths=("src/main.py",),
            head=None,
            tail=None,
        )
        assert permission_manager.is_allowed(tc)

    def test_file_read_path_mismatch(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/**",), head=None, tail=None))
        tc = FileRead(
            tool_name="filesystem_read_file",
            paths=("tests/test_foo.py",),
            head=None,
            tail=None,
        )
        assert not permission_manager.is_allowed(tc)

    def test_file_read_multiple_paths_all_must_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/**",), head=None, tail=None))
        # One path matches, one doesn't
        tc = FileRead(
            tool_name="filesystem_read_multiple_files",
            paths=("src/main.py", "tests/test_foo.py"),
            head=None,
            tail=None,
        )
        assert not permission_manager.is_allowed(tc)

    def test_file_read_multiple_paths_all_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/**",), head=None, tail=None))
        tc = FileRead(
            tool_name="filesystem_read_multiple_files",
            paths=("src/main.py", "src/config.py"),
            head=None,
            tail=None,
        )
        assert permission_manager.is_allowed(tc)

    def test_file_write_path_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileWrite(tool_name="filesystem_*", path="src/**", content=""))
        tc = FileWrite(
            tool_name="filesystem_write_file",
            path="src/main.py",
            content="print(1)",
        )
        assert permission_manager.is_allowed(tc)

    def test_file_write_path_mismatch(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileWrite(tool_name="filesystem_*", path="src/**", content=""))
        tc = FileWrite(
            tool_name="filesystem_write_file",
            path="tests/test.py",
            content="pass",
        )
        assert not permission_manager.is_allowed(tc)

    def test_file_edit_path_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileEdit(tool_name="filesystem_*", path="src/**", edits=()))
        tc = FileEdit(
            tool_name="filesystem_edit_file",
            path="src/main.py",
            edits=(TextEdit(old_text="a", new_text="b"),),
        )
        assert permission_manager.is_allowed(tc)

    def test_file_edit_path_mismatch(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileEdit(tool_name="filesystem_*", path="src/**", edits=()))
        tc = FileEdit(
            tool_name="filesystem_edit_file",
            path="tests/test.py",
            edits=(TextEdit(old_text="a", new_text="b"),),
        )
        assert not permission_manager.is_allowed(tc)


class TestEvaluationOrder:
    """Tests for ask/allow evaluation order: ask-session, ask-always, allow-session, allow-always."""

    def test_ask_overrides_allow(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(GenericCall(tool_name="my_tool", tool_args={}, ptc=False))
        permission_manager._always.ask.append({"type": "GenericCall", "tool_name": "my_tool"})
        tc = GenericCall(tool_name="my_tool", tool_args={}, ptc=False)
        assert not permission_manager.is_allowed(tc)

    def test_ask_session_overrides_allow_always(self, permission_manager: PermissionManager) -> None:
        permission_manager._always.allow.append({"type": "GenericCall", "tool_name": "my_tool"})
        permission_manager._session.ask.append({"type": "GenericCall", "tool_name": "my_tool"})
        tc = GenericCall(tool_name="my_tool", tool_args={}, ptc=False)
        assert not permission_manager.is_allowed(tc)

    def test_allow_session_before_allow_always(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(GenericCall(tool_name="my_tool", tool_args={}, ptc=False))
        tc = GenericCall(tool_name="my_tool", tool_args={}, ptc=False)
        assert permission_manager.is_allowed(tc)

    def test_no_match_returns_false(self, permission_manager: PermissionManager) -> None:
        tc = GenericCall(tool_name="unknown", tool_args={}, ptc=False)
        assert not permission_manager.is_allowed(tc)


class TestPathNormalization:
    """Tests for absolute -> relative path normalization."""

    def test_absolute_path_normalized_to_relative(
        self, working_dir: Path, permission_manager: PermissionManager
    ) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/**",), head=None, tail=None))
        absolute_path = str(working_dir / "src" / "main.py")
        tc = FileRead(
            tool_name="filesystem_read_file",
            paths=(absolute_path,),
            head=None,
            tail=None,
        )
        assert permission_manager.is_allowed(tc)

    def test_path_outside_workspace_stays_absolute(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("/etc/**",), head=None, tail=None))
        tc = FileRead(
            tool_name="filesystem_read_file",
            paths=("/etc/hosts",),
            head=None,
            tail=None,
        )
        assert permission_manager.is_allowed(tc)


class TestPersistenceRoundtrip:
    """Tests for save/load with new typed dict format."""

    def test_save_new_format(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        manager.allow_always(GenericCall(tool_name="github_*", tool_args={}, ptc=False))
        manager.allow_always(ShellAction(tool_name="bash", command="git *"))

        data = json.loads((freeact_dir / "permissions.json").read_text())
        assert data == {
            "ask": [],
            "allow": DEFAULT_ALLOW_RULES
            + [
                {"type": "GenericCall", "tool_name": "github_*"},
                {"type": "ShellAction", "tool_name": "bash", "command": "git *"},
            ],
        }

    def test_load_new_format(self, freeact_dir: Path, working_dir: Path) -> None:
        freeact_dir.mkdir(parents=True)
        data = {
            "ask": [{"type": "ShellAction", "tool_name": "bash", "command": "rm *"}],
            "allow": [
                {"type": "GenericCall", "tool_name": "safe_*"},
                {"type": "ShellAction", "tool_name": "bash", "command": "git *"},
            ],
        }
        (freeact_dir / "permissions.json").write_text(json.dumps(data))

        manager = PermissionManager(working_dir, freeact_dir)
        manager.load()

        assert manager.is_allowed(GenericCall(tool_name="safe_tool", tool_args={}, ptc=False))
        assert manager.is_allowed(ShellAction(tool_name="bash", command="git status"))
        assert not manager.is_allowed(ShellAction(tool_name="bash", command="rm -rf /"))

    def test_roundtrip(self, freeact_dir: Path, working_dir: Path) -> None:
        m1 = PermissionManager(working_dir, freeact_dir)
        m1.allow_always(GenericCall(tool_name="github_*", tool_args={}, ptc=False))
        m1.allow_always(ShellAction(tool_name="bash", command="git *"))

        m2 = PermissionManager(working_dir, freeact_dir)
        m2.load()

        assert m2.is_allowed(GenericCall(tool_name="github_search", tool_args={}, ptc=False))
        assert m2.is_allowed(ShellAction(tool_name="bash", command="git status"))

    def test_load_missing_file_keeps_defaults(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        manager.load()
        assert manager._always.ask == []
        assert manager._always.allow == DEFAULT_ALLOW_RULES


class TestAllowMethods:
    """Tests for allow_always() and allow_session() with deduplication."""

    def test_allow_always_persists(self, freeact_dir: Path, working_dir: Path) -> None:
        m1 = PermissionManager(working_dir, freeact_dir)
        m1.allow_always(GenericCall(tool_name="github_*", tool_args={}, ptc=False))

        m2 = PermissionManager(working_dir, freeact_dir)
        m2.load()
        assert m2.is_allowed(GenericCall(tool_name="github_search", tool_args={}, ptc=False))

    def test_allow_session_not_persisted(self, freeact_dir: Path, working_dir: Path) -> None:
        m1 = PermissionManager(working_dir, freeact_dir)
        m1.allow_session(GenericCall(tool_name="temp_tool", tool_args={}, ptc=False))

        m2 = PermissionManager(working_dir, freeact_dir)
        assert not m2.is_allowed(GenericCall(tool_name="temp_tool", tool_args={}, ptc=False))

    def test_allow_always_deduplicates(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        manager.allow_always(GenericCall(tool_name="github_*", tool_args={}, ptc=False))
        manager.allow_always(GenericCall(tool_name="github_*", tool_args={}, ptc=False))

        data = json.loads((freeact_dir / "permissions.json").read_text())
        github_entries = [e for e in data["allow"] if e.get("tool_name") == "github_*"]
        assert len(github_entries) == 1

    def test_allow_session_deduplicates(self, permission_manager: PermissionManager) -> None:
        tc = GenericCall(tool_name="github_*", tool_args={}, ptc=False)
        permission_manager.allow_session(tc)
        permission_manager.allow_session(tc)
        assert len(permission_manager._session.allow) == 1


class TestPermissionManagerInit:
    """Tests for initialization behavior."""

    def test_constructor_does_not_create_freeact_directory(self, freeact_dir: Path, working_dir: Path) -> None:
        assert not freeact_dir.exists()
        PermissionManager(working_dir, freeact_dir)
        assert not freeact_dir.exists()

    def test_save_creates_freeact_directory(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        assert not freeact_dir.exists()
        manager.save()
        assert freeact_dir.exists()

    def test_init_saves_defaults_when_no_file(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        manager.init()
        assert (freeact_dir / "permissions.json").exists()
        data = json.loads((freeact_dir / "permissions.json").read_text())
        assert data == {"ask": [], "allow": DEFAULT_ALLOW_RULES}

    def test_init_loads_from_file_when_exists(self, freeact_dir: Path, working_dir: Path) -> None:
        freeact_dir.mkdir(parents=True)
        custom_rules = {
            "ask": [],
            "allow": [{"type": "GenericCall", "tool_name": "custom_*"}],
        }
        (freeact_dir / "permissions.json").write_text(json.dumps(custom_rules))

        manager = PermissionManager(working_dir, freeact_dir)
        manager.init()
        assert manager._always.allow == [{"type": "GenericCall", "tool_name": "custom_*"}]

    def test_init_restores_defaults_after_file_deleted(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        manager.init()
        (freeact_dir / "permissions.json").unlink()

        manager2 = PermissionManager(working_dir, freeact_dir)
        manager2.init()
        assert manager2._always.allow == DEFAULT_ALLOW_RULES

    def test_defaults_active_without_load(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        tc = GenericCall(tool_name="pytools_list_categories", tool_args={}, ptc=False)
        assert manager.is_allowed(tc)


class TestPathPatternSemantics:
    """Tests for path pattern matching with PurePosixPath.full_match."""

    def test_single_star_matches_direct_child(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/*",), head=None, tail=None))
        tc = FileRead(tool_name="filesystem_read_file", paths=("src/main.py",), head=None, tail=None)
        assert permission_manager.is_allowed(tc)

    def test_single_star_does_not_cross_slash(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/*",), head=None, tail=None))
        tc = FileRead(tool_name="filesystem_read_file", paths=("src/sub/main.py",), head=None, tail=None)
        assert not permission_manager.is_allowed(tc)

    def test_double_star_matches_any_depth(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", paths=("src/**",), head=None, tail=None))
        assert permission_manager.is_allowed(
            FileRead(tool_name="filesystem_read_file", paths=("src/main.py",), head=None, tail=None)
        )
        assert permission_manager.is_allowed(
            FileRead(tool_name="filesystem_read_file", paths=("src/sub/main.py",), head=None, tail=None)
        )
        assert permission_manager.is_allowed(
            FileRead(tool_name="filesystem_read_file", paths=("src/a/b/c.py",), head=None, tail=None)
        )

    def test_freeact_double_star_matches_nested(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileWrite(tool_name="filesystem_*", path=".freeact/**", content=""))
        tc = FileWrite(
            tool_name="filesystem_write_file",
            path=".freeact/sessions/abc/main.jsonl",
            content="data",
        )
        assert permission_manager.is_allowed(tc)

    def test_double_star_slash_star_dot_py_matches_any_depth(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileEdit(tool_name="filesystem_*", path="**/*.py", edits=()))
        assert permission_manager.is_allowed(
            FileEdit(
                tool_name="filesystem_edit_file",
                path="main.py",
                edits=(TextEdit(old_text="a", new_text="b"),),
            )
        )
        assert permission_manager.is_allowed(
            FileEdit(
                tool_name="filesystem_edit_file",
                path="src/deep/nested/file.py",
                edits=(TextEdit(old_text="a", new_text="b"),),
            )
        )
