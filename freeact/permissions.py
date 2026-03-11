import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from freeact.agent.call import ToolCall

DEFAULT_ALLOW_RULES: list[dict[str, Any]] = [
    {"type": "GenericCall", "tool_name": "pytools_list_categories"},
    {"type": "GenericCall", "tool_name": "pytools_list_tools"},
    {"type": "FileRead", "tool_name": "filesystem_read_text_file", "paths": [".freeact/**"]},
    {"type": "FileRead", "tool_name": "filesystem_read_multiple_files", "paths": [".freeact/**"]},
]


class PermissionsConfig(BaseModel):
    """Data container for permission rules."""

    model_config = ConfigDict(extra="forbid")

    ask: list[dict[str, Any]] = []
    allow: list[dict[str, Any]] = []

    @classmethod
    def with_defaults(cls) -> "PermissionsConfig":
        """Create an instance with default allow rules."""
        return cls(allow=[rule.copy() for rule in DEFAULT_ALLOW_RULES])

    @classmethod
    def empty(cls) -> "PermissionsConfig":
        """Create an instance with no rules."""
        return cls()


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

    def __init__(self, working_dir: Path | None = None, freeact_dir: Path = Path(".freeact")):
        self._freeact_dir = freeact_dir.resolve()
        self._permissions_file = self._freeact_dir / "permissions.json"
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
        """Load permissions from `.freeact/permissions.json`."""
        if not self._permissions_file.exists():
            return

        text = self._permissions_file.read_text()
        data = json.loads(text)

        self._always = PermissionsConfig.model_validate(data)

    def save(self) -> None:
        """Persist always-tier permissions to `.freeact/permissions.json`."""
        self._freeact_dir.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._always.model_dump(), indent=2)
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
        result = self._check_all(tool_call)
        return result == "allow"

    def allow_always(self, tool_call: ToolCall) -> None:
        """Add a pattern rule to the always-allow list and persist.

        The tool call's fields may contain glob wildcards. For example,
        `ShellAction(tool_name="bash", command="git *")` allows all git
        subcommands, and `FileRead(tool_name="filesystem_*",
        paths=("src/**",))` allows reading any file under `src/`.
        """
        entry = tool_call.to_entry()
        if entry not in self._always.allow:
            self._always.allow.append(entry)
        self.save()

    def allow_session(self, tool_call: ToolCall) -> None:
        """Add a pattern rule to the session-allow list (not persisted).

        The tool call's fields may contain glob wildcards, same as
        [`allow_always`][freeact.permissions.PermissionManager.allow_always].
        Session rules are cleared when the process ends.
        """
        entry = tool_call.to_entry()
        if entry not in self._session.allow:
            self._session.allow.append(entry)

    def _check_all(self, tool_call: ToolCall) -> str | None:
        """Evaluate all permission lists in order. First match wins."""
        for entry in self._session.ask:
            if tool_call.matches_entry(entry, self._working_dir):
                return "ask"
        for entry in self._always.ask:
            if tool_call.matches_entry(entry, self._working_dir):
                return "ask"
        for entry in self._session.allow:
            if tool_call.matches_entry(entry, self._working_dir):
                return "allow"
        for entry in self._always.allow:
            if tool_call.matches_entry(entry, self._working_dir):
                return "allow"
        return None
