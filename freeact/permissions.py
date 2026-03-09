import json
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any

import aiofiles

from freeact.agent.call import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    ToolCall,
)


class PermissionManager:
    """Tool call permission gating with type-specific pattern rules.

    Rules are `ToolCall` instances whose fields may contain glob wildcards
    (`*`, `?`). Path fields (`path`, `paths`) use path-aware matching
    where `*` matches within a single directory and `**` matches across
    directory boundaries. Non-path fields (`tool_name`, `command`) use
    simple glob matching.

    Use [`allow_always`][freeact.permissions.PermissionManager.allow_always]
    and [`allow_session`][freeact.permissions.PermissionManager.allow_session]
    to store pattern rules. Use
    [`is_allowed`][freeact.permissions.PermissionManager.is_allowed] to check
    concrete (no wildcards) tool calls against stored rules.

    Evaluation order: ask-session, ask-always, allow-session, allow-always.
    First match wins. Ask takes priority over allow.
    """

    def __init__(self, freeact_dir: Path = Path(".freeact"), *, working_dir: Path | None = None):
        self._freeact_dir = freeact_dir.resolve()
        self._permissions_file = self._freeact_dir / "permissions.json"
        self._working_dir = (working_dir or Path.cwd()).resolve()

        self._ask_always: list[dict[str, Any]] = []
        self._allow_always: list[dict[str, Any]] = []
        self._ask_session: list[dict[str, Any]] = []
        self._allow_session: list[dict[str, Any]] = []

    async def load(self) -> None:
        """Load permissions from `.freeact/permissions.json`."""
        if not self._permissions_file.exists():
            return

        async with aiofiles.open(self._permissions_file) as f:
            text = await f.read()
        data = json.loads(text)

        self._ask_always = list(data.get("ask", []))
        self._allow_always = list(data.get("allow", []))

    async def save(self) -> None:
        """Persist always-tier permissions to `.freeact/permissions.json`."""
        self._freeact_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "ask": self._ask_always,
            "allow": self._allow_always,
        }
        content = json.dumps(data, indent=2)
        async with aiofiles.open(self._permissions_file, "w") as f:
            await f.write(content)

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
        result = self._check_all(tool_call)
        return result == "allow"

    async def allow_always(self, tool_call: ToolCall) -> None:
        """Add a pattern rule to the always-allow list and persist.

        The tool call's fields may contain glob wildcards. For example,
        `ShellAction(tool_name="bash", command="git *")` allows all git
        subcommands, and `FileRead(tool_name="filesystem_*",
        paths=("src/**",))` allows reading any file under `src/`.
        """
        entry = _tool_call_to_entry(tool_call)
        if entry not in self._allow_always:
            self._allow_always.append(entry)
        await self.save()

    def allow_session(self, tool_call: ToolCall) -> None:
        """Add a pattern rule to the session-allow list (not persisted).

        The tool call's fields may contain glob wildcards, same as
        [`allow_always`][freeact.permissions.PermissionManager.allow_always].
        Session rules are cleared when the process ends.
        """
        entry = _tool_call_to_entry(tool_call)
        if entry not in self._allow_session:
            self._allow_session.append(entry)

    def _check_all(self, tool_call: ToolCall) -> str | None:
        """Evaluate all permission lists in order. First match wins."""
        for entry in self._ask_session:
            if _matches(entry, tool_call, self._working_dir):
                return "ask"
        for entry in self._ask_always:
            if _matches(entry, tool_call, self._working_dir):
                return "ask"
        for entry in self._allow_session:
            if _matches(entry, tool_call, self._working_dir):
                return "allow"
        for entry in self._allow_always:
            if _matches(entry, tool_call, self._working_dir):
                return "allow"
        return None


def _path_matches(path: str, pattern: str) -> bool:
    return PurePosixPath(path).full_match(pattern)  # type: ignore[attr-defined]


def _normalize_path(path_str: str, working_dir: Path) -> str:
    """Normalize a path: if absolute and under working_dir, make relative."""
    p = Path(path_str)
    if p.is_absolute():
        try:
            return str(p.relative_to(working_dir))
        except ValueError:
            return path_str
    return path_str


def _matches(entry: dict[str, Any], tool_call: ToolCall, working_dir: Path) -> bool:
    """Check if a permission entry matches a tool call."""
    entry_type = entry.get("type")

    match tool_call:
        case GenericCall(tool_name=name):
            if entry_type != "GenericCall":
                return False
            return fnmatch(name, entry.get("tool_name", ""))

        case ShellAction(tool_name=name, command=command):
            if entry_type != "ShellAction":
                return False
            return fnmatch(name, entry.get("tool_name", "")) and fnmatch(command, entry.get("command", ""))

        case CodeAction(tool_name=name):
            if entry_type != "CodeAction":
                return False
            return fnmatch(name, entry.get("tool_name", ""))

        case FileRead(tool_name=name, paths=paths):
            if entry_type != "FileRead":
                return False
            if not fnmatch(name, entry.get("tool_name", "")):
                return False
            entry_patterns = entry.get("paths", [])
            if not entry_patterns:
                return False
            normalized_paths = [_normalize_path(p, working_dir) for p in paths]
            return all(any(_path_matches(np, pattern) for pattern in entry_patterns) for np in normalized_paths)

        case FileWrite(tool_name=name, path=path):
            if entry_type != "FileWrite":
                return False
            if not fnmatch(name, entry.get("tool_name", "")):
                return False
            normalized = _normalize_path(path, working_dir)
            return _path_matches(normalized, entry.get("path", ""))

        case FileEdit(tool_name=name, path=path):
            if entry_type != "FileEdit":
                return False
            if not fnmatch(name, entry.get("tool_name", "")):
                return False
            normalized = _normalize_path(path, working_dir)
            return _path_matches(normalized, entry.get("path", ""))

        case _:
            return False


def _tool_call_to_entry(tool_call: ToolCall) -> dict[str, Any]:
    """Serialize a ToolCall's pattern-relevant fields to a dict entry."""
    match tool_call:
        case GenericCall(tool_name=name):
            return {"type": "GenericCall", "tool_name": name}
        case ShellAction(tool_name=name, command=command):
            return {"type": "ShellAction", "tool_name": name, "command": command}
        case CodeAction(tool_name=name):
            return {"type": "CodeAction", "tool_name": name}
        case FileRead(tool_name=name, paths=paths):
            return {"type": "FileRead", "tool_name": name, "paths": list(paths)}
        case FileWrite(tool_name=name, path=path):
            return {"type": "FileWrite", "tool_name": name, "path": path}
        case FileEdit(tool_name=name, path=path):
            return {"type": "FileEdit", "tool_name": name, "path": path}
        case _:
            return {"type": "ToolCall", "tool_name": tool_call.tool_name}
