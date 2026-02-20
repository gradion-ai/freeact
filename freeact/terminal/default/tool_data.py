from dataclasses import dataclass
from typing import Any, TypeAlias


@dataclass(frozen=True)
class TextEditData:
    """Canonical text replacement used by file edit actions."""

    old_text: str
    new_text: str


@dataclass(frozen=True)
class CodeActionData:
    """Canonical payload for a code execution action."""

    code: str


@dataclass(frozen=True)
class FileReadData:
    """Canonical payload for a file read action."""

    paths: tuple[str, ...]
    head: int | None
    tail: int | None


@dataclass(frozen=True)
class FileWriteData:
    """Canonical payload for a file write action."""

    path: str
    content: str


@dataclass(frozen=True)
class FileEditData:
    """Canonical payload for a file edit action."""

    path: str
    edits: tuple[TextEditData, ...]


@dataclass(frozen=True)
class GenericToolCallData:
    """Canonical fallback payload for tool call actions."""

    tool_name: str
    tool_args: dict[str, Any]


ActionData: TypeAlias = CodeActionData | FileReadData | FileWriteData | FileEditData | GenericToolCallData


@dataclass(frozen=True)
class ToolOutputData:
    """Canonical fallback payload for tool output content."""

    content: str
