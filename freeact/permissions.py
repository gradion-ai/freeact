import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Literal

import aiofiles


class PermissionManager:
    """Tool and shell command permission gating with pattern-based rules.

    Supports glob-style patterns (`*`, `?`) via `fnmatch` for both tool
    names and shell commands. Rules are organized into ask/allow tiers
    with session and always persistence scopes.

    Evaluation order: ask-session, ask-always, allow-session, allow-always.
    First match wins. Ask takes priority over allow.

    Filesystem tools targeting paths within `.freeact/` are auto-approved
    without explicit permission grants.
    """

    def __init__(self, freeact_dir: Path = Path(".freeact")):
        self._freeact_dir = freeact_dir.resolve()
        self._permissions_file = self._freeact_dir / "permissions.json"
        self._filesystem_tools = frozenset(
            {
                "filesystem_read_file",
                "filesystem_read_text_file",
                "filesystem_write_file",
                "filesystem_edit_file",
                "filesystem_create_directory",
                "filesystem_list_directory",
                "filesystem_directory_tree",
                "filesystem_search_files",
                "filesystem_read_multiple_files",
            }
        )

        self._tool_ask_always: list[str] = []
        self._tool_allow_always: list[str] = []
        self._tool_ask_session: list[str] = []
        self._tool_allow_session: list[str] = []

        self._shell_ask_always: list[str] = []
        self._shell_allow_always: list[str] = []
        self._shell_ask_session: list[str] = []
        self._shell_allow_session: list[str] = []

    async def load(self) -> None:
        """Load permissions from `.freeact/permissions.json`.

        Handles both old format (`allowed_tools`) and new format
        (`tool_permissions`/`shell_permissions`). Old format is
        auto-migrated on next `save()`.
        """
        if not self._permissions_file.exists():
            return

        async with aiofiles.open(self._permissions_file) as f:
            text = await f.read()
        data = json.loads(text)

        if "allowed_tools" in data:
            # Old format migration
            self._tool_allow_always = list(data["allowed_tools"])
            return

        tool_perms = data.get("tool_permissions", {})
        self._tool_ask_always = list(tool_perms.get("ask", []))
        self._tool_allow_always = list(tool_perms.get("allow", []))

        shell_perms = data.get("shell_permissions", {})
        self._shell_ask_always = list(shell_perms.get("ask", []))
        self._shell_allow_always = list(shell_perms.get("allow", []))

    async def save(self) -> None:
        """Persist always-tier permissions to `.freeact/permissions.json`."""
        self._freeact_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "tool_permissions": {
                "ask": self._tool_ask_always,
                "allow": self._tool_allow_always,
            },
            "shell_permissions": {
                "ask": self._shell_ask_always,
                "allow": self._shell_allow_always,
            },
        }
        content = json.dumps(data, indent=2)
        async with aiofiles.open(self._permissions_file, "w") as f:
            await f.write(content)

    def check_tool(self, tool_name: str) -> str | None:
        """Check tool permissions against pattern rules.

        Returns:
            `"allow"` if a matching allow rule is found,
            `"ask"` if a matching ask rule is found,
            `None` if no rule matches.
        """
        return self._check(
            tool_name,
            self._tool_ask_session,
            self._tool_ask_always,
            self._tool_allow_session,
            self._tool_allow_always,
        )

    def check_shell(self, command: str) -> str | None:
        """Check shell command permissions against pattern rules.

        Returns:
            `"allow"` if a matching allow rule is found,
            `"ask"` if a matching ask rule is found,
            `None` if no rule matches.
        """
        return self._check(
            command,
            self._shell_ask_session,
            self._shell_ask_always,
            self._shell_allow_session,
            self._shell_allow_always,
        )

    def is_allowed(self, tool_name: str, tool_args: dict[str, Any] | None = None) -> bool:
        """Check if a tool call is pre-approved.

        Returns `True` if `check_tool()` returns `"allow"` or if it's a
        filesystem tool operating within `.freeact/`.
        """
        result = self.check_tool(tool_name)
        if result == "allow":
            return True

        if tool_name in self._filesystem_tools and tool_args:
            match tool_args:
                case {"paths": paths}:
                    return all(self._is_within_freeact(p) for p in paths)
                case {"path": path}:
                    return self._is_within_freeact(path)

        return False

    async def allow_always(self, pattern: str, domain: Literal["tool", "shell"] = "tool") -> None:
        """Add a pattern to the always-allow list and persist."""
        target = self._tool_allow_always if domain == "tool" else self._shell_allow_always
        if pattern not in target:
            target.append(pattern)
        await self.save()

    def allow_session(self, pattern: str, domain: Literal["tool", "shell"] = "tool") -> None:
        """Add a pattern to the session-allow list (not persisted)."""
        target = self._tool_allow_session if domain == "tool" else self._shell_allow_session
        if pattern not in target:
            target.append(pattern)

    def suggest_tool_pattern(self, tool_name: str) -> str:
        """Suggest a permission pattern for a tool name.

        Returns the full tool name as the default pattern.
        """
        return tool_name

    def suggest_shell_pattern(self, command: str) -> str:
        """Suggest a permission pattern for a shell command.

        Delegates to [`suggest_shell_pattern()`][freeact.shell.suggest_shell_pattern].
        """
        from freeact.shell import suggest_shell_pattern

        return suggest_shell_pattern(command)

    def _is_within_freeact(self, path_str: str) -> bool:
        path = Path(path_str).resolve()
        return path == self._freeact_dir or self._freeact_dir in path.parents

    @staticmethod
    def _check(
        name: str,
        ask_session: list[str],
        ask_always: list[str],
        allow_session: list[str],
        allow_always: list[str],
    ) -> str | None:
        """Evaluate permission rules in order: ask-session, ask-always,
        allow-session, allow-always. First match wins."""
        for pattern in ask_session:
            if fnmatch(name, pattern):
                return "ask"
        for pattern in ask_always:
            if fnmatch(name, pattern):
                return "ask"
        for pattern in allow_session:
            if fnmatch(name, pattern):
                return "allow"
        for pattern in allow_always:
            if fnmatch(name, pattern):
                return "allow"
        return None
