import json
import mimetypes
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ipybox.utils import arun
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

    def delete_last_messages(self, agent_id: str, count: int) -> None:
        """Delete the last persisted messages for an agent.

        Args:
            agent_id: Logical agent stream name used to locate the JSONL file.
            count: Number of trailing messages to remove.

        Raises:
            ValueError: If `count` is negative or exceeds the persisted line count.
        """
        if count < 0:
            raise ValueError("count must be >= 0")
        if count == 0:
            return

        session_file = self._sessions_root / self._session_id / f"{agent_id}.jsonl"
        if not session_file.exists():
            return

        lines = session_file.read_text(encoding="utf-8").splitlines()
        if count > len(lines):
            raise ValueError(f"Cannot delete {count} messages from {session_file}: only {len(lines)} persisted")

        remaining = lines[:-count]
        session_file.write_text("".join(f"{line}\n" for line in remaining), encoding="utf-8")

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
    preview: str | None


class ToolResultMaterializer:
    """Materialize tool results with file-based overflow storage."""

    def __init__(
        self,
        *,
        session_store: SessionStore,
        inline_max_bytes: int,
        preview_chars: int,
        working_dir: Path,
    ) -> None:
        self._session_store = session_store
        self._inline_max_bytes = inline_max_bytes
        self._preview_chars = preview_chars
        self._working_dir = working_dir

    def materialize(self, content: ToolResult) -> ToolResult:
        """Return content inline or replace it with an overflow notice.

        Results at or below the inline threshold pass through unchanged.
        Larger results are written to the session's `tool-results/`
        directory and replaced by a notice with size, optional preview,
        and the saved file path. If saving fails, the content stays
        inline.
        """
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
        if canonical.preview:
            lines.append(f"Preview (~{self._preview_chars} characters):")
            lines.append(canonical.preview)
        lines.append(f"Full content saved to: {stored_path.relative_to(self._working_dir).as_posix()}")
        return "\n".join(lines)

    def _canonicalize(self, content: ToolResult) -> _CanonicalToolResult:
        match content:
            case str() as text:
                return _CanonicalToolResult(
                    payload=text.encode("utf-8"),
                    extension="txt",
                    preview=self._take_preview(text),
                )
            case BinaryContent(data=data, media_type=media_type):
                return _CanonicalToolResult(
                    payload=data,
                    extension=self._media_type_to_ext(media_type),
                    preview=None,
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
                    preview=None,
                )

    def _take_preview(self, text: str) -> str | None:
        if self._preview_chars <= 0:
            return None

        if not text:
            return "<empty>"

        if len(text) <= self._preview_chars:
            return text

        half_chars = self._preview_chars // 2
        suffix_chars = self._preview_chars - half_chars
        prefix = text[:half_chars]
        suffix = text[-suffix_chars:]
        return f"{prefix} ... ({len(text) - self._preview_chars} chars omitted) ... {suffix}"

    @staticmethod
    def _media_type_to_ext(media_type: str) -> str:
        guessed = mimetypes.guess_extension(media_type, strict=False)
        ext = (guessed or ".bin").lstrip(".").lower()
        return ext if ext and ext.isalnum() else "bin"


class Session:
    """Single source of truth for an agent's message history.

    Owns the in-memory history and keeps the persistent store (when
    present) in sync on every mutation; callers never write to both.
    Also owns tool-result overflow materialization, which stores
    oversized results in the session directory.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        store: SessionStore | None,
        working_dir: Path,
        inline_max_bytes: int,
        preview_chars: int,
    ) -> None:
        self._history_id = agent_id if agent_id.startswith("sub-") else "main"
        self._store = store
        self._messages: list[ModelMessage] = []
        self._materializer: ToolResultMaterializer | None = None
        if store is not None:
            self._materializer = ToolResultMaterializer(
                session_store=store,
                inline_max_bytes=inline_max_bytes,
                preview_chars=preview_chars,
                working_dir=working_dir,
            )

    @property
    def messages(self) -> list[ModelMessage]:
        """Current message history (live view, do not mutate)."""
        return self._messages

    def __len__(self) -> int:
        return len(self._messages)

    async def load(self) -> None:
        """Restore persisted history.

        Only the main agent's history is rehydrated; subagent histories
        are an audit record. No-op when persistence is disabled or
        history was already loaded.
        """
        if self._store is None or self._history_id != "main" or self._messages:
            return
        self._messages = await arun(self._store.load_messages, agent_id="main")

    async def append(self, messages: list[ModelMessage]) -> None:
        """Append messages to history (and the store, when persistent)."""
        if not messages:
            return

        self._messages.extend(messages)
        if self._store is not None:
            await arun(self._store.append_messages, agent_id=self._history_id, messages=messages)

    async def rollback(self, count: int) -> None:
        """Remove the last `count` messages from history (and the store)."""
        if count <= 0:
            return
        if count > len(self._messages):
            raise ValueError(f"Cannot rollback {count} messages from history of size {len(self._messages)}")

        del self._messages[-count:]
        if self._store is not None:
            await arun(self._store.delete_last_messages, agent_id=self._history_id, count=count)

    async def materialize(self, content: ToolResult) -> ToolResult:
        """Apply overflow handling to a tool result.

        Pass-through when persistence is disabled.
        """
        if self._materializer is None:
            return content
        return await arun(self._materializer.materialize, content)

    async def materialize_text(self, text: str) -> tuple[str, bool]:
        """Apply overflow handling to text output.

        Returns:
            The (possibly replaced) text and whether it was truncated.
        """
        materialized = str(await self.materialize(text))
        return materialized, materialized != text
