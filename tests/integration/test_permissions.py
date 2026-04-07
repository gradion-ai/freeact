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
)
from freeact.permissions import DEFAULT_ALLOW_RULES, DEFAULT_ASK_RULES, PermissionManager, PermissionsConfig


@pytest.fixture
def freeact_dir(tmp_path: Path) -> Path:
    """Return the .freeact directory path (not yet created)."""
    return tmp_path / ".freeact"


@pytest.fixture
def working_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def permission_manager(working_dir: Path, freeact_dir: Path) -> PermissionManager:
    """Return a fresh PermissionManager instance with default rules loaded."""
    return PermissionManager(working_dir, freeact_dir)


@pytest.fixture
def empty_permission_manager(working_dir: Path, freeact_dir: Path) -> PermissionManager:
    """Return a PermissionManager with no default rules.

    Use this for tests that exercise matching/evaluation semantics in isolation
    (e.g. negative-match cases for paths inside the workspace) where the broad
    default allow rules would otherwise mask the assertion.
    """
    manager = PermissionManager(working_dir, freeact_dir)
    manager._always = PermissionsConfig.empty()
    return manager


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
        tc = GenericCall(tool_name="filesystem_read_text_file", tool_args={}, ptc=False)
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

    def test_file_read_path_must_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None))
        tc = FileRead(
            tool_name="filesystem_read_text_file",
            path="src/main.py",
            offset=None,
            limit=None,
        )
        assert permission_manager.is_allowed(tc)

    def test_file_read_path_mismatch(self, empty_permission_manager: PermissionManager) -> None:
        empty_permission_manager.allow_session(
            FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None)
        )
        tc = FileRead(
            tool_name="filesystem_read_text_file",
            path="tests/test_foo.py",
            offset=None,
            limit=None,
        )
        assert not empty_permission_manager.is_allowed(tc)

    def test_file_write_path_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileWrite(tool_name="filesystem_*", path="src/**", content=""))
        tc = FileWrite(
            tool_name="filesystem_write_text_file",
            path="src/main.py",
            content="print(1)",
        )
        assert permission_manager.is_allowed(tc)

    def test_file_write_path_mismatch(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileWrite(tool_name="filesystem_*", path="src/**", content=""))
        tc = FileWrite(
            tool_name="filesystem_write_text_file",
            path="tests/test.py",
            content="pass",
        )
        assert not permission_manager.is_allowed(tc)

    def test_file_edit_path_match(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileEdit(tool_name="filesystem_*", path="src/**", old_text="", new_text=""))
        tc = FileEdit(
            tool_name="filesystem_edit_text_file",
            path="src/main.py",
            old_text="a",
            new_text="b",
        )
        assert permission_manager.is_allowed(tc)

    def test_file_edit_path_mismatch(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileEdit(tool_name="filesystem_*", path="src/**", old_text="", new_text=""))
        tc = FileEdit(
            tool_name="filesystem_edit_text_file",
            path="tests/test.py",
            old_text="a",
            new_text="b",
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
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None))
        absolute_path = str(working_dir / "src" / "main.py")
        tc = FileRead(
            tool_name="filesystem_read_text_file",
            path=absolute_path,
            offset=None,
            limit=None,
        )
        assert permission_manager.is_allowed(tc)

    def test_path_outside_workspace_stays_absolute(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", path="/etc/**", offset=None, limit=None))
        tc = FileRead(
            tool_name="filesystem_read_text_file",
            path="/etc/hosts",
            offset=None,
            limit=None,
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
            "ask": DEFAULT_ASK_RULES,
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
        assert manager._always.ask == DEFAULT_ASK_RULES
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
        assert data == {"ask": DEFAULT_ASK_RULES, "allow": DEFAULT_ALLOW_RULES}

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
        assert manager2._always.ask == DEFAULT_ASK_RULES
        assert manager2._always.allow == DEFAULT_ALLOW_RULES

    def test_defaults_active_without_load(self, freeact_dir: Path, working_dir: Path) -> None:
        manager = PermissionManager(working_dir, freeact_dir)
        tc = GenericCall(tool_name="pytools_list_categories", tool_args={}, ptc=False)
        assert manager.is_allowed(tc)


class TestPathPatternSemantics:
    """Tests for path pattern matching with PurePosixPath.full_match."""

    def test_single_star_matches_direct_child(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", path="src/*", offset=None, limit=None))
        tc = FileRead(tool_name="filesystem_read_text_file", path="src/main.py", offset=None, limit=None)
        assert permission_manager.is_allowed(tc)

    def test_single_star_does_not_cross_slash(self, empty_permission_manager: PermissionManager) -> None:
        empty_permission_manager.allow_session(
            FileRead(tool_name="filesystem_*", path="src/*", offset=None, limit=None)
        )
        tc = FileRead(tool_name="filesystem_read_text_file", path="src/sub/main.py", offset=None, limit=None)
        assert not empty_permission_manager.is_allowed(tc)

    def test_double_star_matches_any_depth(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None))
        assert permission_manager.is_allowed(
            FileRead(tool_name="filesystem_read_text_file", path="src/main.py", offset=None, limit=None)
        )
        assert permission_manager.is_allowed(
            FileRead(tool_name="filesystem_read_text_file", path="src/sub/main.py", offset=None, limit=None)
        )
        assert permission_manager.is_allowed(
            FileRead(tool_name="filesystem_read_text_file", path="src/a/b/c.py", offset=None, limit=None)
        )

    def test_freeact_double_star_matches_nested(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileWrite(tool_name="filesystem_*", path=".freeact/**", content=""))
        tc = FileWrite(
            tool_name="filesystem_write_text_file",
            path=".freeact/sessions/abc/main.jsonl",
            content="data",
        )
        assert permission_manager.is_allowed(tc)

    def test_double_star_slash_star_dot_py_matches_any_depth(self, permission_manager: PermissionManager) -> None:
        permission_manager.allow_session(FileEdit(tool_name="filesystem_*", path="**/*.py", old_text="", new_text=""))
        assert permission_manager.is_allowed(
            FileEdit(
                tool_name="filesystem_edit_text_file",
                path="main.py",
                old_text="a",
                new_text="b",
            )
        )
        assert permission_manager.is_allowed(
            FileEdit(
                tool_name="filesystem_edit_text_file",
                path="src/deep/nested/file.py",
                old_text="a",
                new_text="b",
            )
        )


class TestDefaultRules:
    """Tests for the built-in DEFAULT_ALLOW_RULES and DEFAULT_ASK_RULES."""

    def _read(self, path: str, tool_name: str = "filesystem_read_text_file") -> FileRead:
        return FileRead(tool_name=tool_name, path=path, offset=None, limit=None)

    def _shell(self, command: str) -> ShellAction:
        return ShellAction(tool_name="bash", command=command)

    # FileRead defaults

    def test_workspace_text_read_allowed(self, permission_manager: PermissionManager) -> None:
        assert permission_manager.is_allowed(self._read("README.md"))
        assert permission_manager.is_allowed(self._read("src/main.py"))
        assert permission_manager.is_allowed(self._read("a/b/c/d.txt"))

    def test_workspace_media_read_allowed(self, permission_manager: PermissionManager) -> None:
        assert permission_manager.is_allowed(self._read("docs/image.png", tool_name="filesystem_read_media_file"))

    def test_absolute_workspace_path_normalized_and_allowed(
        self, working_dir: Path, permission_manager: PermissionManager
    ) -> None:
        absolute_path = str(working_dir / "src" / "main.py")
        assert permission_manager.is_allowed(self._read(absolute_path))

    def test_freeact_subtree_still_allowed(self, permission_manager: PermissionManager) -> None:
        assert permission_manager.is_allowed(self._read(".freeact/permissions.json"))
        assert permission_manager.is_allowed(self._read(".freeact/sessions/abc/main.jsonl"))

    def test_dotenv_at_root_blocked(self, permission_manager: PermissionManager) -> None:
        assert not permission_manager.is_allowed(self._read(".env"))

    def test_dotenv_nested_blocked(self, permission_manager: PermissionManager) -> None:
        assert not permission_manager.is_allowed(self._read("sub/.env"))
        assert not permission_manager.is_allowed(self._read("a/b/.env"))

    def test_absolute_dotenv_under_workdir_blocked(
        self, working_dir: Path, permission_manager: PermissionManager
    ) -> None:
        assert not permission_manager.is_allowed(self._read(str(working_dir / ".env")))
        assert not permission_manager.is_allowed(self._read(str(working_dir / "sub" / ".env")))

    def test_absolute_path_outside_workspace_blocked(self, permission_manager: PermissionManager) -> None:
        # The broad relative `**` allow rule must NOT match absolute paths
        # outside working_dir. This pins the `_path_matches` guard.
        assert not permission_manager.is_allowed(self._read("/etc/passwd"))
        assert not permission_manager.is_allowed(self._read("/etc/hosts"))
        assert not permission_manager.is_allowed(self._read("/Users/someone/.ssh/id_rsa"))

    # GenericCall defaults

    def test_pytools_introspection_allowed(self, permission_manager: PermissionManager) -> None:
        for name in ("pytools_list_categories", "pytools_list_tools", "pytools_search_tools"):
            assert permission_manager.is_allowed(GenericCall(tool_name=name, tool_args={}, ptc=False))

    def test_unrelated_generic_call_blocked(self, permission_manager: PermissionManager) -> None:
        assert not permission_manager.is_allowed(GenericCall(tool_name="github_create_issue", tool_args={}, ptc=False))

    # ShellAction defaults — bare and with-args coverage

    def test_introspection_commands_allowed(self, permission_manager: PermissionManager) -> None:
        for cmd in ("pwd", "whoami", "uptime", "hostname", "date", "uname", "uname -a", "id", "id user"):
            assert permission_manager.is_allowed(self._shell(cmd)), cmd

    def test_listing_and_metadata_commands_allowed(self, permission_manager: PermissionManager) -> None:
        for cmd in ("ls", "ls -la /tmp", "tree", "tree -L 2", "stat README.md", "file foo", "wc -l README.md"):
            assert permission_manager.is_allowed(self._shell(cmd)), cmd

    def test_text_reading_commands_allowed(self, permission_manager: PermissionManager) -> None:
        for cmd in ("cat README.md", "head -n 5 file", "tail -n 20 log.txt"):
            assert permission_manager.is_allowed(self._shell(cmd)), cmd

    def test_process_info_allowed(self, permission_manager: PermissionManager) -> None:
        assert permission_manager.is_allowed(self._shell("ps"))
        assert permission_manager.is_allowed(self._shell("ps aux"))

    def test_git_readonly_bare_and_with_args_allowed(self, permission_manager: PermissionManager) -> None:
        cases = [
            "git status",
            "git status -s",
            "git log",
            "git log --oneline -n 5",
            "git diff",
            "git diff HEAD~1 HEAD",
            "git show",
            "git show HEAD",
            "git blame README.md",
            "git ls-files",
            "git ls-files src/",
            "git rev-parse HEAD",
            "git describe",
            "git describe --tags",
            "git config --list",
            "git config --get user.name",
            "git remote",
            "git remote -v",
            "git remote show origin",
            "git tag",
            "git branch",
            "git stash list",
            "git worktree list",
        ]
        for cmd in cases:
            assert permission_manager.is_allowed(self._shell(cmd)), cmd

    # ShellAction defaults — destructive variants must NOT be allowed

    def test_git_destructive_variants_blocked(self, permission_manager: PermissionManager) -> None:
        cases = [
            "git push",
            "git push origin main",
            "git pull",
            "git checkout main",
            "git reset --hard",
            "git rm file.txt",
            "git commit -m msg",
            "git branch -D feature",
            "git tag -d v1",
            "git remote add origin url",
            "git remote remove origin",
            "git stash drop",
            "git stash pop",
            "git worktree add ../foo branch",
            "git config user.name foo",
        ]
        for cmd in cases:
            assert not permission_manager.is_allowed(self._shell(cmd)), cmd

    def test_filesystem_mutation_commands_blocked(self, permission_manager: PermissionManager) -> None:
        cases = [
            "rm -rf /",
            "rm file.txt",
            "mv a b",
            "cp a b",
            "mkdir x",
            "touch foo",
            "chmod 777 a",
            "chown root a",
            "kill 1",
            "pkill python",
        ]
        for cmd in cases:
            assert not permission_manager.is_allowed(self._shell(cmd)), cmd

    def test_find_blocked(self, permission_manager: PermissionManager) -> None:
        # `find` is intentionally excluded from defaults regardless of args.
        for cmd in ("find", "find .", "find . -name '*.py'", "find . -delete", "find . -exec rm {} ;"):
            assert not permission_manager.is_allowed(self._shell(cmd)), cmd

    def test_env_executor_form_blocked(self, permission_manager: PermissionManager) -> None:
        # `env` and `env *` are excluded because `env CMD args` runs arbitrary
        # commands; e.g. `env -i bash` reseeds and execs bash.
        for cmd in ("env", "env -i bash", "env FOO=bar python"):
            assert not permission_manager.is_allowed(self._shell(cmd)), cmd

    def test_shell_magic_not_covered_by_bash_defaults(self, permission_manager: PermissionManager) -> None:
        # Defaults target tool_name="bash"; shell_magic must still prompt.
        assert not permission_manager.is_allowed(ShellAction(tool_name="shell_magic", command="ls"))
        assert not permission_manager.is_allowed(ShellAction(tool_name="shell_magic", command="git status"))

    # Persistence smoke test

    def test_defaults_round_trip_via_init(self, freeact_dir: Path, working_dir: Path) -> None:
        # First manager writes defaults to disk; second manager reloads them.
        m1 = PermissionManager(working_dir, freeact_dir)
        m1.init()

        m2 = PermissionManager(working_dir, freeact_dir)
        m2.init()

        assert m2.is_allowed(self._shell("git status"))
        assert m2.is_allowed(self._shell("ls -la"))
        assert m2.is_allowed(GenericCall(tool_name="pytools_search_tools", tool_args={}, ptc=False))
        assert m2.is_allowed(self._read("README.md"))
        assert not m2.is_allowed(self._read(".env"))
        assert not m2.is_allowed(self._read("/etc/passwd"))
