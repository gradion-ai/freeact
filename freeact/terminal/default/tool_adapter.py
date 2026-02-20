import json
from typing import Any

from freeact.terminal.default.tool_data import (
    ActionData,
    CodeActionData,
    FileEditData,
    FileReadData,
    FileWriteData,
    GenericToolCallData,
    TextEditData,
    ToolOutputData,
)


class ToolAdapter:
    """Normalize tool calls and outputs into terminal UI data models."""

    def map_action(self, tool_name: str, tool_args: dict[str, Any]) -> ActionData:
        """Convert a raw tool call into canonical action data.

        Args:
            tool_name: Tool identifier from the agent event stream.
            tool_args: Raw tool argument payload.

        Returns:
            Canonical action payload used by terminal widgets.
        """
        match tool_name:
            case "ipybox_execute_ipython_cell":
                return CodeActionData(code=self._to_str(tool_args.get("code", "")))
            case "filesystem_read_file" | "filesystem_read_text_file":
                return FileReadData(
                    paths=(self._to_str(tool_args.get("path", "unknown")),),
                    head=self._to_int_or_none(tool_args.get("head")),
                    tail=self._to_int_or_none(tool_args.get("tail")),
                )
            case "filesystem_read_multiple_files":
                return FileReadData(
                    paths=self._to_paths(tool_args.get("paths")),
                    head=None,
                    tail=None,
                )
            case "filesystem_write_file":
                return FileWriteData(
                    path=self._to_str(tool_args.get("path", "unknown")),
                    content=self._to_str(tool_args.get("content", "")),
                )
            case "filesystem_edit_file":
                return FileEditData(
                    path=self._to_str(tool_args.get("path", "unknown")),
                    edits=self._to_edits(tool_args.get("edits")),
                )
            case _:
                return GenericToolCallData(tool_name=tool_name, tool_args=dict(tool_args))

    def map_output(self, action: ActionData | None, tool_content: object) -> ToolOutputData:
        """Convert raw tool output content into canonical output data.

        Args:
            action: Action data that produced this output. Currently unused.
            tool_content: Raw tool result payload from agent events.

        Returns:
            Canonical output payload for tool output widgets.
        """
        text = self._extract_tool_text(tool_content)
        _ = action
        return ToolOutputData(content=text)

    def _extract_tool_text(self, content: object) -> str:
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
                return "\n".join(self._extract_tool_text(item) for item in content)
            case _:
                return str(content)

    def _to_paths(self, value: object) -> tuple[str, ...]:
        """Convert a list-like value to a tuple of path strings."""
        match value:
            case list() | tuple():
                return tuple(self._to_str(item) for item in value)
            case _:
                return ()

    def _to_edits(self, value: object) -> tuple[TextEditData, ...]:
        """Convert list-like edit payloads into canonical text edits."""
        match value:
            case list() | tuple():
                edits: list[TextEditData] = []
                for raw_edit in value:
                    match raw_edit:
                        case {"oldText": old_text, "newText": new_text}:
                            edits.append(TextEditData(old_text=self._to_str(old_text), new_text=self._to_str(new_text)))
                        case {"old_text": old_text, "new_text": new_text}:
                            edits.append(TextEditData(old_text=self._to_str(old_text), new_text=self._to_str(new_text)))
                        case {"oldText": old_text, "new_text": new_text}:
                            edits.append(TextEditData(old_text=self._to_str(old_text), new_text=self._to_str(new_text)))
                        case {"old_text": old_text, "newText": new_text}:
                            edits.append(TextEditData(old_text=self._to_str(old_text), new_text=self._to_str(new_text)))
                        case _:
                            continue
                return tuple(edits)
            case _:
                return ()

    def _to_str(self, value: object) -> str:
        """Convert a value to `str` without raising."""
        match value:
            case str():
                return value
            case _:
                return str(value)

    def _to_int_or_none(self, value: object) -> int | None:
        """Return an integer value or `None` when conversion is not possible."""
        match value:
            case int():
                return value
            case _:
                return None
