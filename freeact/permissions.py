from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

import tomli_w
import tomllib
from pydantic import BaseModel, ConfigDict, Field

from freeact.toolcalls import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    ToolCall,
)


def _path_matches(path: str, pattern: str) -> bool:
    # A relative pattern must not match an absolute path. `PurePosixPath.full_match`
    # treats `**` as matching any path including absolute ones, which would let
    # broad relative patterns like `**` leak reads of arbitrary host files.
    if pattern.startswith("/") != path.startswith("/"):
        return False
    return PurePosixPath(path).full_match(pattern)  # type: ignore[attr-defined]


def _normalize_path(path_str: str, working_dir: Path) -> str:
    # If absolute and under working_dir, make relative so workspace-relative
    # rules apply; paths outside the working dir stay absolute.
    p = Path(path_str)
    if p.is_absolute():
        try:
            return str(p.relative_to(working_dir))
        except ValueError:
            return path_str
    return path_str


class _Rule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str

    def matches(self, call: ToolCall, working_dir: Path) -> bool:
        """Check whether this rule matches a concrete tool call."""
        return False


class GenericCallRule(_Rule):
    """Rule matching generic tool calls by tool name glob."""

    type: Literal["GenericCall"] = "GenericCall"

    def matches(self, call: ToolCall, working_dir: Path) -> bool:
        match call:
            case GenericCall():
                return fnmatch(call.tool_name, self.tool_name)
            case _:
                return False


class ShellActionRule(_Rule):
    """Rule matching shell commands by tool name and command globs."""

    type: Literal["ShellAction"] = "ShellAction"
    command: str

    def matches(self, call: ToolCall, working_dir: Path) -> bool:
        match call:
            case ShellAction():
                return fnmatch(call.tool_name, self.tool_name) and fnmatch(call.command, self.command)
            case _:
                return False


class CodeActionRule(_Rule):
    """Rule matching code actions by tool name glob."""

    type: Literal["CodeAction"] = "CodeAction"

    def matches(self, call: ToolCall, working_dir: Path) -> bool:
        match call:
            case CodeAction():
                return fnmatch(call.tool_name, self.tool_name)
            case _:
                return False


class _FileRule(_Rule):
    path: str

    def _matches_file(self, call_tool_name: str, call_path: str, working_dir: Path) -> bool:
        if not fnmatch(call_tool_name, self.tool_name):
            return False
        if not self.path:
            return False
        normalized = _normalize_path(call_path, working_dir)
        return _path_matches(normalized, self.path)


class FileReadRule(_FileRule):
    """Rule matching file reads by tool name glob and path pattern."""

    type: Literal["FileRead"] = "FileRead"

    def matches(self, call: ToolCall, working_dir: Path) -> bool:
        match call:
            case FileRead():
                return self._matches_file(call.tool_name, call.path, working_dir)
            case _:
                return False


class FileWriteRule(_FileRule):
    """Rule matching file writes by tool name glob and path pattern."""

    type: Literal["FileWrite"] = "FileWrite"

    def matches(self, call: ToolCall, working_dir: Path) -> bool:
        match call:
            case FileWrite():
                return self._matches_file(call.tool_name, call.path, working_dir)
            case _:
                return False


class FileEditRule(_FileRule):
    """Rule matching file edits by tool name glob and path pattern."""

    type: Literal["FileEdit"] = "FileEdit"

    def matches(self, call: ToolCall, working_dir: Path) -> bool:
        match call:
            case FileEdit():
                return self._matches_file(call.tool_name, call.path, working_dir)
            case _:
                return False


PermissionRule = Annotated[
    GenericCallRule | ShellActionRule | CodeActionRule | FileReadRule | FileWriteRule | FileEditRule,
    Field(discriminator="type"),
]


def rule_from_call(tool_call: ToolCall) -> PermissionRule:
    """Build a permission rule from a (possibly wildcarded) tool call.

    Args:
        tool_call: Tool call whose pattern-relevant fields become the rule.

    Returns:
        Typed permission rule matching calls like `tool_call`.
    """
    match tool_call:
        case ShellAction():
            return ShellActionRule(tool_name=tool_call.tool_name, command=tool_call.command)
        case CodeAction():
            return CodeActionRule(tool_name=tool_call.tool_name)
        case FileRead():
            return FileReadRule(tool_name=tool_call.tool_name, path=tool_call.path)
        case FileWrite():
            return FileWriteRule(tool_name=tool_call.tool_name, path=tool_call.path)
        case FileEdit():
            return FileEditRule(tool_name=tool_call.tool_name, path=tool_call.path)
        case GenericCall():
            return GenericCallRule(tool_name=tool_call.tool_name)
        case _:
            raise ValueError(f"unsupported tool call type: {type(tool_call).__name__}")


def _shell(command: str) -> ShellActionRule:
    return ShellActionRule(tool_name="bash", command=command)


def _generic(tool_name: str) -> GenericCallRule:
    return GenericCallRule(tool_name=tool_name)


def _file_read(path: str, tool_name: str = "filesystem_*") -> FileReadRule:
    return FileReadRule(tool_name=tool_name, path=path)


# Ask rules are evaluated before allow rules; an ask match overrides any allow
# match. Reads of `.env` files always prompt, even though `**` is allowed.
DEFAULT_ASK_RULES: list[PermissionRule] = [
    _file_read("**/.env"),
]

DEFAULT_ALLOW_RULES: list[PermissionRule] = [
    # FileRead: any text/media file inside the working directory. The relative
    # pattern is intentional; `_path_matches` rejects absolute paths outside
    # `working_dir`, so reads of e.g. /etc/passwd still prompt.
    _file_read("**"),
    # GenericCall: read-only pytools introspection across basic and hybrid modes.
    _generic("pytools_list_categories"),
    _generic("pytools_list_tools"),
    _generic("pytools_search_tools"),
    # ShellAction: pure introspection commands. No flags can mutate state, and
    # no shell-redirect-into-write is feasible from the command alone.
    _shell("pwd"),
    _shell("whoami"),
    _shell("id"),
    _shell("id *"),
    _shell("hostname"),
    _shell("uname"),
    _shell("uname *"),
    _shell("date"),
    _shell("uptime"),
    _shell("which *"),
    _shell("whereis *"),
    # ShellAction: file/dir listing and metadata.
    _shell("ls"),
    _shell("ls *"),
    _shell("tree"),
    _shell("tree *"),
    _shell("stat *"),
    _shell("file *"),
    _shell("du *"),
    _shell("df"),
    _shell("df *"),
    _shell("wc *"),
    # ShellAction: text reading.
    _shell("cat *"),
    _shell("head *"),
    _shell("tail *"),
    # ShellAction: process info.
    _shell("ps"),
    _shell("ps *"),
    # ShellAction: git read-only subcommands. Each non-trivial form needs both
    # the bare and `<cmd> *` entry because fnmatch's `*` requires a literal
    # space (so `git status *` does NOT match `git status`).
    _shell("git status"),
    _shell("git status *"),
    _shell("git log"),
    _shell("git log *"),
    _shell("git diff"),
    _shell("git diff *"),
    _shell("git show"),
    _shell("git show *"),
    _shell("git blame *"),
    _shell("git ls-files"),
    _shell("git ls-files *"),
    _shell("git ls-tree *"),
    _shell("git cat-file *"),
    _shell("git rev-parse *"),
    _shell("git describe"),
    _shell("git describe *"),
    _shell("git shortlog"),
    _shell("git shortlog *"),
    # `git reflog` lists the reflog; the `*` form is intentionally excluded
    # because it would match `git reflog expire ...` / `git reflog delete ...`.
    _shell("git reflog"),
    _shell("git for-each-ref *"),
    _shell("git symbolic-ref *"),
    _shell("git config --get *"),
    _shell("git config --list"),
    _shell("git remote"),
    _shell("git remote -v"),
    _shell("git remote show *"),
    # `git tag`/`git branch` no-args list refs; the `*` form is intentionally
    # excluded because it would match `git tag -d v1` / `git branch -D foo`.
    _shell("git tag"),
    _shell("git branch"),
    _shell("git stash list"),
    _shell("git stash show *"),
    _shell("git worktree list"),
]


class PermissionsConfig(BaseModel):
    """Data container for permission rules."""

    model_config = ConfigDict(extra="forbid")

    ask: list[PermissionRule] = []
    allow: list[PermissionRule] = []

    @classmethod
    def with_defaults(cls) -> "PermissionsConfig":
        """Create an instance with default ask and allow rules."""
        return cls(
            ask=list(DEFAULT_ASK_RULES),
            allow=list(DEFAULT_ALLOW_RULES),
        )

    @classmethod
    def empty(cls) -> "PermissionsConfig":
        """Create an instance with no rules."""
        return cls()


class PermissionManager:
    """Tool call permission gating with type-specific pattern rules.

    Rules are typed patterns whose fields may contain glob wildcards
    (`*`, `?`). Path fields use path-aware matching where `*` matches
    within a single directory and `**` matches across directory
    boundaries. Non-path fields (`tool_name`, `command`) use simple glob
    matching.

    Use [`allow_always`][freeact.permissions.PermissionManager.allow_always]
    and [`allow_session`][freeact.permissions.PermissionManager.allow_session]
    to store pattern rules. Use
    [`is_allowed`][freeact.permissions.PermissionManager.is_allowed] to check
    concrete (no wildcards) tool calls against stored rules.

    Evaluation order: ask-session, ask-always, allow-session, allow-always.
    First match wins. Ask takes priority over allow.
    """

    def __init__(self, working_dir: Path | None = None, freeact_dir: Path = Path(".freeact")):
        self._freeact_dir = freeact_dir.resolve()
        self._permissions_file = self._freeact_dir / "permissions.toml"
        self._working_dir = (working_dir or Path.cwd()).resolve()

        self._always: PermissionsConfig = PermissionsConfig.with_defaults()
        self._session: PermissionsConfig = PermissionsConfig.empty()

    def init(self) -> None:
        """Load permissions when present, otherwise save defaults."""
        if self._permissions_file.exists():
            self.load()
        else:
            self.save()

    def load(self) -> None:
        """Load permissions from `.freeact/permissions.toml`."""
        if not self._permissions_file.exists():
            return

        data = tomllib.loads(self._permissions_file.read_text())
        self._always = PermissionsConfig.model_validate(data)

    def save(self) -> None:
        """Persist always-tier permissions to `.freeact/permissions.toml`."""
        self._freeact_dir.mkdir(parents=True, exist_ok=True)
        content = tomli_w.dumps(self._always.model_dump())
        self._permissions_file.write_text(content)

    def is_allowed(self, tool_call: ToolCall) -> bool:
        """Check if a concrete tool call is pre-approved.

        The tool call should contain literal values (no wildcards).
        Its fields are matched against the glob patterns in stored rules.

        Args:
            tool_call: Concrete tool call to check.

        Returns:
            `True` if an allow rule matches and no ask rule takes
            precedence, `False` otherwise.
        """
        return self._check_all(tool_call) == "allow"

    def allow_always(self, tool_call: ToolCall) -> None:
        """Add a pattern rule to the always-allow list and persist.

        The tool call's fields may contain glob wildcards. For example,
        `ShellAction(tool_name="bash", command="git *")` allows all git
        subcommands, and `FileRead(tool_name="filesystem_*", path="src/**",
        offset=None, limit=None)` allows reading any file under `src/`.
        """
        rule = rule_from_call(tool_call)
        if rule not in self._always.allow:
            self._always.allow.append(rule)
        self.save()

    def allow_session(self, tool_call: ToolCall) -> None:
        """Add a pattern rule to the session-allow list (not persisted).

        The tool call's fields may contain glob wildcards, same as
        [`allow_always`][freeact.permissions.PermissionManager.allow_always].
        Session rules are cleared when the process ends.
        """
        rule = rule_from_call(tool_call)
        if rule not in self._session.allow:
            self._session.allow.append(rule)

    def _check_all(self, tool_call: ToolCall) -> str | None:
        # Evaluate all permission lists in order. First match wins.
        for rule in self._session.ask:
            if rule.matches(tool_call, self._working_dir):
                return "ask"
        for rule in self._always.ask:
            if rule.matches(tool_call, self._working_dir):
                return "ask"
        for rule in self._session.allow:
            if rule.matches(tool_call, self._working_dir):
                return "allow"
        for rule in self._always.allow:
            if rule.matches(tool_call, self._working_dir):
                return "allow"
        return None
