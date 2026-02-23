import json
import mimetypes
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_ai.mcp import ToolResult
from pydantic_ai.messages import BinaryContent, ModelMessage, ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python


class SessionStore:
    """Persist and restore per-agent pydantic-ai message history as JSONL."""

    def __init__(
        self,
        sessions_root: Path,
        session_id: str,
        flush_after_append: bool = False,
    ):
        self._sessions_root = sessions_root
        self._session_id = session_id
        self._flush_after_append = flush_after_append

    def append_messages(self, agent_id: str, messages: list[ModelMessage]) -> None:
        """Append serialized messages to an agent-specific session log.

        Each message is written as a versioned JSONL envelope with a UTC
        timestamp. The session file is created on demand.

        Args:
            agent_id: Logical agent stream name (for example, `"main"` or
                `"sub-1234"`), used as the JSONL filename stem.
            messages: Messages to append in order.
        """
        session_dir = self._sessions_root / self._session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / f"{agent_id}.jsonl"

        with session_file.open("a", encoding="utf-8") as f:
            for message in messages:
                envelope = {
                    "v": 1,
                    "message": to_jsonable_python(message, bytes_mode="base64"),
                    "meta": {"ts": datetime.now(UTC).isoformat().replace("+00:00", "Z")},
                }
                f.write(json.dumps(envelope) + "\n")

            if self._flush_after_append:
                f.flush()

    def load_messages(self, agent_id: str) -> list[ModelMessage]:
        """Load and validate all persisted messages for an agent.

        Returns an empty list when no session file exists. If the final line is
        truncated (for example from an interrupted write), that line is ignored.
        Earlier malformed lines raise `ValueError`.

        Args:
            agent_id: Logical agent stream name used to locate the JSONL file.

        Returns:
            Deserialized message history in append order.
        """
        session_file = self._sessions_root / self._session_id / f"{agent_id}.jsonl"
        if not session_file.exists():
            return []

        lines = session_file.read_text(encoding="utf-8").splitlines()
        serialized_messages: list[Any] = []

        for index, line in enumerate(lines):
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError as e:
                if index == len(lines) - 1:
                    break
                raise ValueError(f"Malformed JSONL line {index + 1} in {session_file}") from e

            self._validate_envelope(envelope, index + 1, session_file)
            serialized_messages.append(envelope["message"])

        return ModelMessagesTypeAdapter.validate_python(serialized_messages)

    def save_tool_result(self, payload: bytes, extension: str) -> Path:
        """Persist a tool-result payload under the session's `tool-results/` directory."""
        safe_extension = self._sanitize_extension(extension)
        tool_results_dir = self._sessions_root / self._session_id / "tool-results"
        tool_results_dir.mkdir(parents=True, exist_ok=True)

        while True:
            file_id = uuid.uuid4().hex[:8]
            filename = f"{file_id}.{safe_extension}"
            path = tool_results_dir / filename
            if not path.exists():
                break

        path.write_bytes(payload)
        return path

    @staticmethod
    def _validate_envelope(envelope: Any, line_no: int, session_file: Path) -> None:
        if not isinstance(envelope, dict):
            raise ValueError(f"Malformed JSONL line {line_no} in {session_file}")

        required_keys = {"v", "message", "meta"}
        if not required_keys.issubset(envelope):
            raise ValueError(f"Malformed JSONL line {line_no} in {session_file}")

        if envelope["v"] != 1:
            raise ValueError(f"Unsupported session envelope version on line {line_no} in {session_file}")

        meta = envelope["meta"]
        if not isinstance(meta, dict):
            raise ValueError(f"Malformed JSONL line {line_no} in {session_file}")

        if "agent_id" in meta:
            raise ValueError(
                f"Invalid session envelope on line {line_no} in {session_file}: meta.agent_id is forbidden"
            )

        if "ts" not in meta:
            raise ValueError(f"Malformed JSONL line {line_no} in {session_file}")

    @staticmethod
    def _sanitize_extension(extension: str) -> str:
        raw = extension.lower().lstrip(".")

        if not raw:
            return "bin"

        if re.fullmatch(r"[a-z0-9]+", raw):
            return raw
        return "bin"


@dataclass(frozen=True)
class _CanonicalToolResult:
    payload: bytes
    extension: str
    preview_lines: list[str]


class ToolResultMaterializer:
    """Materialize tool results with file-based overflow storage."""

    def __init__(
        self,
        *,
        session_store: SessionStore,
        inline_max_bytes: int,
        preview_lines: int,
        working_dir: Path,
    ) -> None:
        self._session_store = session_store
        self._inline_max_bytes = inline_max_bytes
        self._preview_lines = preview_lines
        self._working_dir = working_dir

    def materialize(self, content: ToolResult) -> ToolResult:
        canonical = self._canonicalize(content)
        actual_size_bytes = len(canonical.payload)

        if actual_size_bytes <= self._inline_max_bytes:
            return content

        try:
            stored_path = self._session_store.save_tool_result(canonical.payload, canonical.extension)
        except Exception:
            return content

        lines = [
            f"Tool result exceeded configured inline threshold ({self._inline_max_bytes} bytes).",
            f"Actual size: {actual_size_bytes} bytes.",
        ]
        if canonical.preview_lines:
            lines.append(f"Preview (first and last {self._preview_lines} lines):")
            lines.extend(canonical.preview_lines)
        lines.append(f"Full content saved to: {stored_path.relative_to(self._working_dir).as_posix()}")
        return "\n".join(lines)

    def _canonicalize(self, content: ToolResult) -> _CanonicalToolResult:
        match content:
            case str() as text:
                return _CanonicalToolResult(
                    payload=text.encode("utf-8"),
                    extension="txt",
                    preview_lines=self._take_preview_lines(text),
                )
            case BinaryContent(data=data, media_type=media_type):
                return _CanonicalToolResult(
                    payload=data,
                    extension=self._media_type_to_ext(media_type),
                    preview_lines=[],
                )
            case _:
                normalized = to_jsonable_python(content, bytes_mode="base64")
                rendered = json.dumps(
                    normalized,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                return _CanonicalToolResult(
                    payload=rendered.encode("utf-8"),
                    extension="json",
                    preview_lines=[],
                )

    def _take_preview_lines(self, text: str) -> list[str]:
        if self._preview_lines <= 0:
            return []

        lines = text.splitlines()
        if not lines:
            return ["<empty>"]

        boundary = self._preview_lines
        if len(lines) <= boundary * 2:
            return lines

        omitted = len(lines) - (boundary * 2)
        return [
            *lines[:boundary],
            f"... ({omitted} lines omitted) ...",
            *lines[-boundary:],
        ]

    @staticmethod
    def _media_type_to_ext(media_type: str) -> str:
        guessed = mimetypes.guess_extension(media_type, strict=False)
        ext = (guessed or ".bin").lstrip(".").lower()
        return ext if ext and ext.isalnum() else "bin"
