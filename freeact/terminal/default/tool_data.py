from dataclasses import dataclass
from typing import Any, TypeAlias


@dataclass(frozen=True)
class TextEditData:
    """Canonical representation of one text replacement edit."""

    old_text: str
    new_text: str


@dataclass(frozen=True)
class CodeActionData:
    """Canonical data for IPython code execution approval."""

    code: str


@dataclass(frozen=True)
class FileReadData:
    """Canonical data for file read approvals."""

    paths: tuple[str, ...]
    head: int | None
    tail: int | None


@dataclass(frozen=True)
class FileWriteData:
    """Canonical data for file write approvals."""

    path: str
    content: str


@dataclass(frozen=True)
class FileEditData:
    """Canonical data for file edit approvals."""

    path: str
    edits: tuple[TextEditData, ...]


@dataclass(frozen=True)
class GenericToolCallData:
    """Canonical fallback data for tool approvals."""

    tool_name: str
    tool_args: dict[str, Any]


ActionData: TypeAlias = CodeActionData | FileReadData | FileWriteData | FileEditData | GenericToolCallData


@dataclass(frozen=True)
class ReadOutputData:
    """Canonical tool output for file read responses."""

    title: str
    filenames: tuple[str, ...]
    content: str
    lexer: str | None = None


@dataclass(frozen=True)
class GenericToolOutputData:
    """Canonical fallback output for tool responses."""

    content: str


ToolOutputData: TypeAlias = ReadOutputData | GenericToolOutputData
