import json
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any

from freeact.agent.shell import suggest_shell_pattern


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


@dataclass(frozen=True)
class ToolCall:
    """Base class for typed tool call representations."""

    tool_name: str

    @classmethod
    def from_raw(cls, tool_name: str, tool_args: dict[str, Any]) -> "ToolCall":
        """Construct the appropriate ToolCall subclass from raw API data.

        Args:
            tool_name: Tool identifier from the agent event stream.
            tool_args: Raw tool argument payload.

        Returns:
            Typed ToolCall instance.
        """
        match tool_name:
            case "ipybox_execute_ipython_cell":
                return CodeAction(
                    tool_name=tool_name,
                    code=_to_str(tool_args.get("code", "")),
                )
            case "filesystem_read_text_file" | "filesystem_read_media_file":
                return FileRead(
                    tool_name=tool_name,
                    path=_to_str(tool_args.get("path", "unknown")),
                    offset=_to_int_or_none(tool_args.get("offset")),
                    limit=_to_int_or_none(tool_args.get("limit")),
                )
            case "filesystem_write_text_file":
                return FileWrite(
                    tool_name=tool_name,
                    path=_to_str(tool_args.get("path", "unknown")),
                    content=_to_str(tool_args.get("content", "")),
                )
            case "filesystem_edit_text_file":
                return FileEdit(
                    tool_name=tool_name,
                    path=_to_str(tool_args.get("path", "unknown")),
                    old_text=_to_str(tool_args.get("old_text", "")),
                    new_text=_to_str(tool_args.get("new_text", "")),
                )
            case _:
                return GenericCall(
                    tool_name=tool_name,
                    tool_args=dict(tool_args),
                    ptc=False,
                )

    def to_pattern(self) -> str:
        """Suggest a permission pattern string for this tool call."""
        return self.tool_name

    def from_pattern(self, pattern: str) -> "ToolCall":
        """Reconstruct a ToolCall from a user-edited pattern string."""
        return GenericCall(tool_name=pattern, tool_args={}, ptc=False)

    def to_entry(self) -> dict[str, Any]:
        """Serialize this tool call's pattern-relevant fields to a dict entry."""
        return {"type": "ToolCall", "tool_name": self.tool_name}

    def matches_entry(self, entry: dict[str, Any], working_dir: Path) -> bool:
        """Check if a permission entry matches this tool call."""
        return False


@dataclass(frozen=True)
class GenericCall(ToolCall):
    """Fallback for tool calls without specialized handling."""

    tool_args: dict[str, Any]
    ptc: bool = False

    def to_entry(self) -> dict[str, Any]:
        return {"type": "GenericCall", "tool_name": self.tool_name}

    def matches_entry(self, entry: dict[str, Any], working_dir: Path) -> bool:
        if entry.get("type") != "GenericCall":
            return False
        return fnmatch(self.tool_name, entry.get("tool_name", ""))


@dataclass(frozen=True)
class ShellAction(ToolCall):
    """Shell command extracted from a code cell."""

    command: str

    def to_pattern(self) -> str:
        return suggest_shell_pattern(self.command)

    def from_pattern(self, pattern: str) -> "ToolCall":
        return ShellAction(tool_name="bash", command=pattern)

    def to_entry(self) -> dict[str, Any]:
        return {"type": "ShellAction", "tool_name": self.tool_name, "command": self.command}

    def matches_entry(self, entry: dict[str, Any], working_dir: Path) -> bool:
        if entry.get("type") != "ShellAction":
            return False
        return fnmatch(self.tool_name, entry.get("tool_name", "")) and fnmatch(self.command, entry.get("command", ""))


@dataclass(frozen=True)
class CodeAction(ToolCall):
    """Code execution action."""

    code: str

    def from_pattern(self, pattern: str) -> "ToolCall":
        return CodeAction(tool_name=pattern, code="")

    def to_entry(self) -> dict[str, Any]:
        return {"type": "CodeAction", "tool_name": self.tool_name}

    def matches_entry(self, entry: dict[str, Any], working_dir: Path) -> bool:
        if entry.get("type") != "CodeAction":
            return False
        return fnmatch(self.tool_name, entry.get("tool_name", ""))


@dataclass(frozen=True)
class FileRead(ToolCall):
    """File read action."""

    path: str
    offset: int | None
    limit: int | None

    def to_pattern(self) -> str:
        return f"{self.tool_name} {self.path}"

    def from_pattern(self, pattern: str) -> "ToolCall":
        parts = pattern.split(None, 1)
        name = parts[0] if parts else self.tool_name
        path = parts[1] if len(parts) > 1 else self.path
        return FileRead(tool_name=name, path=path, offset=None, limit=None)

    def to_entry(self) -> dict[str, Any]:
        return {"type": "FileRead", "tool_name": self.tool_name, "path": self.path}

    def matches_entry(self, entry: dict[str, Any], working_dir: Path) -> bool:
        if entry.get("type") != "FileRead":
            return False
        if not fnmatch(self.tool_name, entry.get("tool_name", "")):
            return False
        entry_pattern = entry.get("path", "")
        if not entry_pattern:
            return False
        normalized = _normalize_path(self.path, working_dir)
        return _path_matches(normalized, entry_pattern)


@dataclass(frozen=True)
class FileWrite(ToolCall):
    """File write action."""

    path: str
    content: str

    def to_pattern(self) -> str:
        return f"{self.tool_name} {self.path}"

    def from_pattern(self, pattern: str) -> "ToolCall":
        parts = pattern.split(None, 1)
        name = parts[0] if parts else self.tool_name
        path = parts[1] if len(parts) > 1 else self.path
        return FileWrite(tool_name=name, path=path, content="")

    def to_entry(self) -> dict[str, Any]:
        return {"type": "FileWrite", "tool_name": self.tool_name, "path": self.path}

    def matches_entry(self, entry: dict[str, Any], working_dir: Path) -> bool:
        if entry.get("type") != "FileWrite":
            return False
        if not fnmatch(self.tool_name, entry.get("tool_name", "")):
            return False
        normalized = _normalize_path(self.path, working_dir)
        return _path_matches(normalized, entry.get("path", ""))


@dataclass(frozen=True)
class FileEdit(ToolCall):
    """File edit action."""

    path: str
    old_text: str
    new_text: str

    def to_pattern(self) -> str:
        return f"{self.tool_name} {self.path}"

    def from_pattern(self, pattern: str) -> "ToolCall":
        parts = pattern.split(None, 1)
        name = parts[0] if parts else self.tool_name
        path = parts[1] if len(parts) > 1 else self.path
        return FileEdit(tool_name=name, path=path, old_text="", new_text="")

    def to_entry(self) -> dict[str, Any]:
        return {"type": "FileEdit", "tool_name": self.tool_name, "path": self.path}

    def matches_entry(self, entry: dict[str, Any], working_dir: Path) -> bool:
        if entry.get("type") != "FileEdit":
            return False
        if not fnmatch(self.tool_name, entry.get("tool_name", "")):
            return False
        normalized = _normalize_path(self.path, working_dir)
        return _path_matches(normalized, entry.get("path", ""))


def suggest_pattern(tool_call: ToolCall) -> str:
    """Suggest a permission pattern string for a tool call.

    Args:
        tool_call: The tool call to suggest a pattern for.

    Returns:
        Pattern string suitable for the approval bar.
    """
    return tool_call.to_pattern()


def parse_pattern(pattern: str, template: ToolCall) -> ToolCall:
    """Reconstruct a ToolCall from a user-edited pattern string and an original type.

    Args:
        pattern: User-edited pattern string from the approval bar.
        template: Original ToolCall that determines the reconstructed type.

    Returns:
        A ToolCall with pattern fields from the edited string.
    """
    return template.from_pattern(pattern)


def extract_tool_output_text(content: object) -> str:
    """Extract readable text from heterogeneous tool result payloads.

    Args:
        content: Raw tool result payload.

    Returns:
        Displayable text representation of the payload.
    """
    match content:
        case str():
            return content
        case {"content": str(text)}:
            return text
        case {"text": str(text)}:
            return text
        case dict():
            return json.dumps(content, indent=2)
        case list():
            return "\n".join(extract_tool_output_text(item) for item in content)
        case _:
            return str(content)


def _to_str(value: object) -> str:
    match value:
        case str():
            return value
        case _:
            return str(value)


def _to_int_or_none(value: object) -> int | None:
    match value:
        case int():
            return value
        case _:
            return None
