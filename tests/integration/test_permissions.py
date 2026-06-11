from pathlib import Path
from typing import Any

import pytest
import tomli_w
import tomllib

from freeact.permissions import (
    DEFAULT_ALLOW_RULES,
    DEFAULT_ASK_RULES,
    GenericCallRule,
    PermissionManager,
    PermissionRule,
    PermissionsConfig,
)
from freeact.toolcalls import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    ToolCall,
)


def _read(path: str, tool_name: str = "filesystem_read_text_file") -> FileRead:
    return FileRead(tool_name=tool_name, path=path, offset=None, limit=None)


def _write(path: str, tool_name: str = "filesystem_write_text_file", content: str = "") -> FileWrite:
    return FileWrite(tool_name=tool_name, path=path, content=content)


def _edit(path: str, tool_name: str = "filesystem_edit_text_file") -> FileEdit:
    return FileEdit(tool_name=tool_name, path=path, old_text="a", new_text="b")


def _shell(command: str, tool_name: str = "bash") -> ShellAction:
    return ShellAction(tool_name=tool_name, command=command)


def _generic(tool_name: str, **tool_args: str) -> GenericCall:
    return GenericCall(tool_name=tool_name, tool_args=dict(tool_args), ptc=False)


def _rule_dicts(rules: list[PermissionRule]) -> list[dict[str, Any]]:
    return [rule.model_dump() for rule in rules]


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


# Type-specific ToolCall matching and path pattern semantics for session rules


@pytest.mark.parametrize(
    ("rule", "call", "allowed"),
    [
        pytest.param(
            _generic("github_*"),
            _generic("github_search_repositories", q="test"),
            True,
            id="generic-call-wildcard",
        ),
        pytest.param(
            _generic("github_search_repositories"),
            _generic("github_search_repositories", q="test"),
            True,
            id="generic-call-exact",
        ),
        pytest.param(
            _generic("github_*"),
            _generic("filesystem_read_text_file"),
            False,
            id="generic-call-no-match",
        ),
        pytest.param(
            ShellAction(tool_name="bash", command="git *"),
            _shell("git status"),
            True,
            id="shell-tool-name-and-command",
        ),
        pytest.param(
            ShellAction(tool_name="bash", command="git *"),
            _shell("rm -rf /"),
            False,
            id="shell-command-mismatch",
        ),
        pytest.param(
            CodeAction(tool_name="ipybox_*", code=""),
            CodeAction(tool_name="ipybox_execute_ipython_cell", code="print(1)"),
            True,
            id="code-action-tool-name-only",
        ),
        pytest.param(
            FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None),
            _read("src/main.py"),
            True,
            id="file-read-path-match",
        ),
        pytest.param(
            FileWrite(tool_name="filesystem_*", path="src/**", content=""),
            _write("src/main.py", content="print(1)"),
            True,
            id="file-write-path-match",
        ),
        pytest.param(
            FileWrite(tool_name="filesystem_*", path="src/**", content=""),
            _write("tests/test.py", content="pass"),
            False,
            id="file-write-path-mismatch",
        ),
        pytest.param(
            FileEdit(tool_name="filesystem_*", path="src/**", old_text="", new_text=""),
            _edit("src/main.py"),
            True,
            id="file-edit-path-match",
        ),
        pytest.param(
            FileEdit(tool_name="filesystem_*", path="src/**", old_text="", new_text=""),
            _edit("tests/test.py"),
            False,
            id="file-edit-path-mismatch",
        ),
        pytest.param(
            FileRead(tool_name="filesystem_*", path="src/*", offset=None, limit=None),
            _read("src/main.py"),
            True,
            id="single-star-matches-direct-child",
        ),
        pytest.param(
            FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None),
            _read("src/sub/main.py"),
            True,
            id="double-star-matches-nested",
        ),
        pytest.param(
            FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None),
            _read("src/a/b/c.py"),
            True,
            id="double-star-matches-any-depth",
        ),
        pytest.param(
            FileWrite(tool_name="filesystem_*", path=".freeact/**", content=""),
            _write(".freeact/sessions/abc/main.jsonl", content="data"),
            True,
            id="freeact-double-star-matches-nested",
        ),
        pytest.param(
            FileEdit(tool_name="filesystem_*", path="**/*.py", old_text="", new_text=""),
            _edit("main.py"),
            True,
            id="double-star-slash-star-dot-py-matches-root",
        ),
        pytest.param(
            FileEdit(tool_name="filesystem_*", path="**/*.py", old_text="", new_text=""),
            _edit("src/deep/nested/file.py"),
            True,
            id="double-star-slash-star-dot-py-matches-nested",
        ),
    ],
)
def test_session_rule_matching(
    permission_manager: PermissionManager, rule: ToolCall, call: ToolCall, allowed: bool
) -> None:
    permission_manager.allow_session(rule)
    assert permission_manager.is_allowed(call) is allowed


@pytest.mark.parametrize(
    ("rule", "call"),
    [
        pytest.param(
            FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None),
            _read("tests/test_foo.py"),
            id="file-read-path-mismatch",
        ),
        pytest.param(
            FileRead(tool_name="filesystem_*", path="src/*", offset=None, limit=None),
            _read("src/sub/main.py"),
            id="single-star-does-not-cross-slash",
        ),
    ],
)
def test_session_rule_no_match_without_defaults(
    empty_permission_manager: PermissionManager, rule: ToolCall, call: ToolCall
) -> None:
    empty_permission_manager.allow_session(rule)
    assert not empty_permission_manager.is_allowed(call)


# Evaluation order: ask-session, ask-always, allow-session, allow-always


def test_ask_overrides_allow(permission_manager: PermissionManager) -> None:
    permission_manager.allow_session(_generic("my_tool"))
    permission_manager._always.ask.append(GenericCallRule(tool_name="my_tool"))
    assert not permission_manager.is_allowed(_generic("my_tool"))


def test_ask_session_overrides_allow_always(permission_manager: PermissionManager) -> None:
    permission_manager._always.allow.append(GenericCallRule(tool_name="my_tool"))
    permission_manager._session.ask.append(GenericCallRule(tool_name="my_tool"))
    assert not permission_manager.is_allowed(_generic("my_tool"))


def test_allow_session_before_allow_always(permission_manager: PermissionManager) -> None:
    permission_manager.allow_session(_generic("my_tool"))
    assert permission_manager.is_allowed(_generic("my_tool"))


def test_no_match_returns_false(permission_manager: PermissionManager) -> None:
    assert not permission_manager.is_allowed(_generic("unknown"))


# Absolute -> relative path normalization


def test_absolute_path_normalized_to_relative(working_dir: Path, permission_manager: PermissionManager) -> None:
    permission_manager.allow_session(FileRead(tool_name="filesystem_*", path="src/**", offset=None, limit=None))
    assert permission_manager.is_allowed(_read(str(working_dir / "src" / "main.py")))


def test_path_outside_workspace_stays_absolute(permission_manager: PermissionManager) -> None:
    permission_manager.allow_session(FileRead(tool_name="filesystem_*", path="/etc/**", offset=None, limit=None))
    assert permission_manager.is_allowed(_read("/etc/hosts"))


# Save/load with typed rule format (TOML)


def test_save_new_format(freeact_dir: Path, working_dir: Path) -> None:
    manager = PermissionManager(working_dir, freeact_dir)
    manager.allow_always(_generic("github_*"))
    manager.allow_always(ShellAction(tool_name="bash", command="git *"))

    data = tomllib.loads((freeact_dir / "permissions.toml").read_text())
    assert data == {
        "ask": _rule_dicts(DEFAULT_ASK_RULES),
        "allow": _rule_dicts(DEFAULT_ALLOW_RULES)
        + [
            {"type": "GenericCall", "tool_name": "github_*"},
            {"type": "ShellAction", "tool_name": "bash", "command": "git *"},
        ],
    }


def test_load_new_format(freeact_dir: Path, working_dir: Path) -> None:
    freeact_dir.mkdir(parents=True)
    data = {
        "ask": [{"type": "ShellAction", "tool_name": "bash", "command": "rm *"}],
        "allow": [
            {"type": "GenericCall", "tool_name": "safe_*"},
            {"type": "ShellAction", "tool_name": "bash", "command": "git *"},
        ],
    }
    (freeact_dir / "permissions.toml").write_text(tomli_w.dumps(data))

    manager = PermissionManager(working_dir, freeact_dir)
    manager.load()

    assert manager.is_allowed(_generic("safe_tool"))
    assert manager.is_allowed(_shell("git status"))
    assert not manager.is_allowed(_shell("rm -rf /"))


def test_roundtrip(freeact_dir: Path, working_dir: Path) -> None:
    m1 = PermissionManager(working_dir, freeact_dir)
    m1.allow_always(_generic("github_*"))
    m1.allow_always(ShellAction(tool_name="bash", command="git *"))

    m2 = PermissionManager(working_dir, freeact_dir)
    m2.load()

    assert m2.is_allowed(_generic("github_search"))
    assert m2.is_allowed(_shell("git status"))


def test_load_missing_file_keeps_defaults(freeact_dir: Path, working_dir: Path) -> None:
    manager = PermissionManager(working_dir, freeact_dir)
    manager.load()
    assert manager._always.ask == DEFAULT_ASK_RULES
    assert manager._always.allow == DEFAULT_ALLOW_RULES


# allow_always() and allow_session() with deduplication


def test_allow_session_not_persisted(freeact_dir: Path, working_dir: Path) -> None:
    m1 = PermissionManager(working_dir, freeact_dir)
    m1.allow_session(_generic("temp_tool"))

    m2 = PermissionManager(working_dir, freeact_dir)
    assert not m2.is_allowed(_generic("temp_tool"))


def test_allow_always_deduplicates(freeact_dir: Path, working_dir: Path) -> None:
    manager = PermissionManager(working_dir, freeact_dir)
    manager.allow_always(_generic("github_*"))
    manager.allow_always(_generic("github_*"))

    data = tomllib.loads((freeact_dir / "permissions.toml").read_text())
    github_entries = [e for e in data["allow"] if e.get("tool_name") == "github_*"]
    assert len(github_entries) == 1


def test_allow_session_deduplicates(permission_manager: PermissionManager) -> None:
    tc = _generic("github_*")
    permission_manager.allow_session(tc)
    permission_manager.allow_session(tc)
    assert len(permission_manager._session.allow) == 1


# Initialization behavior


def test_constructor_does_not_create_freeact_directory(freeact_dir: Path, working_dir: Path) -> None:
    assert not freeact_dir.exists()
    PermissionManager(working_dir, freeact_dir)
    assert not freeact_dir.exists()


def test_save_creates_freeact_directory(freeact_dir: Path, working_dir: Path) -> None:
    manager = PermissionManager(working_dir, freeact_dir)
    assert not freeact_dir.exists()
    manager.save()
    assert freeact_dir.exists()


def test_init_saves_defaults_when_no_file(freeact_dir: Path, working_dir: Path) -> None:
    manager = PermissionManager(working_dir, freeact_dir)
    manager.init()
    assert (freeact_dir / "permissions.toml").exists()
    data = tomllib.loads((freeact_dir / "permissions.toml").read_text())
    assert data == {"ask": _rule_dicts(DEFAULT_ASK_RULES), "allow": _rule_dicts(DEFAULT_ALLOW_RULES)}


def test_init_loads_from_file_when_exists(freeact_dir: Path, working_dir: Path) -> None:
    freeact_dir.mkdir(parents=True)
    custom_rules = {
        "ask": [],
        "allow": [{"type": "GenericCall", "tool_name": "custom_*"}],
    }
    (freeact_dir / "permissions.toml").write_text(tomli_w.dumps(custom_rules))

    manager = PermissionManager(working_dir, freeact_dir)
    manager.init()
    assert manager._always.allow == [GenericCallRule(tool_name="custom_*")]


def test_init_restores_defaults_after_file_deleted(freeact_dir: Path, working_dir: Path) -> None:
    manager = PermissionManager(working_dir, freeact_dir)
    manager.init()
    (freeact_dir / "permissions.toml").unlink()

    manager2 = PermissionManager(working_dir, freeact_dir)
    manager2.init()
    assert manager2._always.ask == DEFAULT_ASK_RULES
    assert manager2._always.allow == DEFAULT_ALLOW_RULES


def test_defaults_active_without_load(freeact_dir: Path, working_dir: Path) -> None:
    manager = PermissionManager(working_dir, freeact_dir)
    assert manager.is_allowed(_generic("pytools_list_categories"))


# Built-in DEFAULT_ALLOW_RULES and DEFAULT_ASK_RULES — FileRead defaults


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "src/main.py",
        "a/b/c/d.txt",
        ".freeact/permissions.toml",
        ".freeact/sessions/abc/main.jsonl",
    ],
)
def test_default_workspace_text_read_allowed(permission_manager: PermissionManager, path: str) -> None:
    assert permission_manager.is_allowed(_read(path))


def test_default_workspace_media_read_allowed(permission_manager: PermissionManager) -> None:
    assert permission_manager.is_allowed(_read("docs/image.png", tool_name="filesystem_read_media_file"))


def test_absolute_workspace_path_normalized_and_allowed(
    working_dir: Path, permission_manager: PermissionManager
) -> None:
    assert permission_manager.is_allowed(_read(str(working_dir / "src" / "main.py")))


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "sub/.env",
        "a/b/.env",
        # The broad relative `**` allow rule must NOT match absolute paths
        # outside working_dir. This pins the `_path_matches` guard.
        "/etc/passwd",
        "/etc/hosts",
        "/Users/someone/.ssh/id_rsa",
    ],
)
def test_default_read_blocked(permission_manager: PermissionManager, path: str) -> None:
    assert not permission_manager.is_allowed(_read(path))


def test_absolute_dotenv_under_workdir_blocked(working_dir: Path, permission_manager: PermissionManager) -> None:
    assert not permission_manager.is_allowed(_read(str(working_dir / ".env")))
    assert not permission_manager.is_allowed(_read(str(working_dir / "sub" / ".env")))


# Built-in defaults — GenericCall


@pytest.mark.parametrize(
    ("tool_name", "allowed"),
    [
        ("pytools_list_categories", True),
        ("pytools_list_tools", True),
        ("pytools_search_tools", True),
        ("github_create_issue", False),
    ],
)
def test_default_generic_call_rules(permission_manager: PermissionManager, tool_name: str, allowed: bool) -> None:
    assert permission_manager.is_allowed(_generic(tool_name)) is allowed


# Built-in defaults — ShellAction, bare and with-args coverage


@pytest.mark.parametrize(
    "command",
    [
        # introspection
        "pwd",
        "whoami",
        "uptime",
        "hostname",
        "date",
        "uname",
        "uname -a",
        "id",
        "id user",
        # listing and metadata
        "ls",
        "ls -la /tmp",
        "tree",
        "tree -L 2",
        "stat README.md",
        "file foo",
        "wc -l README.md",
        # text reading
        "cat README.md",
        "head -n 5 file",
        "tail -n 20 log.txt",
        # process info
        "ps",
        "ps aux",
        # git read-only
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
    ],
)
def test_default_shell_command_allowed(permission_manager: PermissionManager, command: str) -> None:
    assert permission_manager.is_allowed(_shell(command))


@pytest.mark.parametrize(
    "command",
    [
        # git destructive variants
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
        "git reflog expire --expire=now --all",
        "git reflog delete HEAD@{0}",
        "git stash drop",
        "git stash pop",
        "git worktree add ../foo branch",
        "git config user.name foo",
        # filesystem mutation and process control
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
        # `find` is intentionally excluded from defaults regardless of args.
        "find",
        "find .",
        "find . -name '*.py'",
        "find . -delete",
        "find . -exec rm {} ;",
        # `env` and `env *` are excluded because `env CMD args` runs arbitrary
        # commands; e.g. `env -i bash` reseeds and execs bash.
        "env",
        "env -i bash",
        "env FOO=bar python",
    ],
)
def test_default_shell_command_blocked(permission_manager: PermissionManager, command: str) -> None:
    assert not permission_manager.is_allowed(_shell(command))


def test_shell_magic_not_covered_by_bash_defaults(permission_manager: PermissionManager) -> None:
    # Defaults target tool_name="bash"; shell_magic must still prompt.
    assert not permission_manager.is_allowed(_shell("ls", tool_name="shell_magic"))
    assert not permission_manager.is_allowed(_shell("git status", tool_name="shell_magic"))


def test_defaults_round_trip_via_init(freeact_dir: Path, working_dir: Path) -> None:
    # First manager writes defaults to disk; second manager reloads them.
    m1 = PermissionManager(working_dir, freeact_dir)
    m1.init()

    m2 = PermissionManager(working_dir, freeact_dir)
    m2.init()

    assert m2.is_allowed(_shell("git status"))
    assert m2.is_allowed(_shell("ls -la"))
    assert m2.is_allowed(_generic("pytools_search_tools"))
    assert m2.is_allowed(_read("README.md"))
    assert not m2.is_allowed(_read(".env"))
    assert not m2.is_allowed(_read("/etc/passwd"))
