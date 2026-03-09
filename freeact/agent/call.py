import json
from dataclasses import dataclass
from typing import Any


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
            case "filesystem_read_file" | "filesystem_read_text_file":
                return FileRead(
                    tool_name=tool_name,
                    paths=(_to_str(tool_args.get("path", "unknown")),),
                    head=_to_int_or_none(tool_args.get("head")),
                    tail=_to_int_or_none(tool_args.get("tail")),
                )
            case "filesystem_read_multiple_files":
                return FileRead(
                    tool_name=tool_name,
                    paths=_to_paths(tool_args.get("paths")),
                    head=None,
                    tail=None,
                )
            case "filesystem_write_file":
                return FileWrite(
                    tool_name=tool_name,
                    path=_to_str(tool_args.get("path", "unknown")),
                    content=_to_str(tool_args.get("content", "")),
                )
            case "filesystem_edit_file":
                return FileEdit(
                    tool_name=tool_name,
                    path=_to_str(tool_args.get("path", "unknown")),
                    edits=_to_edits(tool_args.get("edits")),
                )
            case _:
                return GenericCall(
                    tool_name=tool_name,
                    tool_args=dict(tool_args),
                    ptc=False,
                )


@dataclass(frozen=True)
class GenericCall(ToolCall):
    """Fallback for tool calls without specialized handling."""

    tool_args: dict[str, Any]
    ptc: bool = False


@dataclass(frozen=True)
class ShellAction(ToolCall):
    """Shell command extracted from a code cell."""

    command: str


@dataclass(frozen=True)
class CodeAction(ToolCall):
    """Code execution action."""

    code: str


@dataclass(frozen=True)
class FileRead(ToolCall):
    """File read action (single or multiple files)."""

    paths: tuple[str, ...]
    head: int | None
    tail: int | None


@dataclass(frozen=True)
class FileWrite(ToolCall):
    """File write action."""

    path: str
    content: str


@dataclass
class TextEdit:
    """A single text replacement within a file edit."""

    old_text: str
    new_text: str


@dataclass(frozen=True)
class FileEdit(ToolCall):
    """File edit action with one or more text replacements."""

    path: str
    edits: tuple[TextEdit, ...]


def suggest_pattern(tool_call: ToolCall) -> str:
    """Suggest a permission pattern string for a tool call.

    Args:
        tool_call: The tool call to suggest a pattern for.

    Returns:
        Pattern string suitable for the approval bar.
    """
    match tool_call:
        case ShellAction(command=command):
            from freeact.shell import suggest_shell_pattern

            return suggest_shell_pattern(command)
        case FileRead(tool_name=name, paths=paths):
            return f"{name} {' '.join(paths)}"
        case FileWrite(tool_name=name, path=path):
            return f"{name} {path}"
        case FileEdit(tool_name=name, path=path):
            return f"{name} {path}"
        case _:
            return tool_call.tool_name


def parse_pattern(pattern: str, template: ToolCall) -> ToolCall:
    """Reconstruct a ToolCall from a user-edited pattern string and an original type.

    Args:
        pattern: User-edited pattern string from the approval bar.
        template: Original ToolCall that determines the reconstructed type.

    Returns:
        A ToolCall with pattern fields from the edited string.
    """
    match template:
        case ShellAction():
            return ShellAction(tool_name="bash", command=pattern)
        case CodeAction():
            return CodeAction(tool_name=pattern, code="")
        case FileRead():
            parts = pattern.split(None, 1)
            name = parts[0] if parts else template.tool_name
            paths = tuple(parts[1].split()) if len(parts) > 1 else template.paths
            return FileRead(tool_name=name, paths=paths, head=None, tail=None)
        case FileWrite():
            parts = pattern.split(None, 1)
            name = parts[0] if parts else template.tool_name
            path = parts[1] if len(parts) > 1 else template.path
            return FileWrite(tool_name=name, path=path, content="")
        case FileEdit():
            parts = pattern.split(None, 1)
            name = parts[0] if parts else template.tool_name
            path = parts[1] if len(parts) > 1 else template.path
            return FileEdit(tool_name=name, path=path, edits=())
        case _:
            return GenericCall(tool_name=pattern, tool_args={}, ptc=False)


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


def _to_paths(value: object) -> tuple[str, ...]:
    match value:
        case list() | tuple():
            return tuple(_to_str(item) for item in value)
        case _:
            return ()


def _to_edits(value: object) -> tuple[TextEdit, ...]:
    match value:
        case list() | tuple():
            edits: list[TextEdit] = []
            for raw_edit in value:
                match raw_edit:
                    case {"oldText": old_text, "newText": new_text}:
                        edits.append(TextEdit(old_text=_to_str(old_text), new_text=_to_str(new_text)))
                    case {"old_text": old_text, "new_text": new_text}:
                        edits.append(TextEdit(old_text=_to_str(old_text), new_text=_to_str(new_text)))
                    case {"oldText": old_text, "new_text": new_text}:
                        edits.append(TextEdit(old_text=_to_str(old_text), new_text=_to_str(new_text)))
                    case {"old_text": old_text, "newText": new_text}:
                        edits.append(TextEdit(old_text=_to_str(old_text), new_text=_to_str(new_text)))
                    case _:
                        continue
            return tuple(edits)
        case _:
            return ()
