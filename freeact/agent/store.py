import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
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

    def append(self, agent_id: str, messages: list[ModelMessage]) -> None:
        """Append serialized messages to an agent-specific session log.

        Each message is written as a versioned JSONL envelope with a UTC
        timestamp. The session file is created on demand.

        Args:
            agent_id: Logical agent stream name (for example, ``"main"`` or
                ``"sub-1234"``), used as the JSONL filename stem.
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

    def load(self, agent_id: str) -> list[ModelMessage]:
        """Load and validate all persisted messages for an agent.

        Returns an empty list when no session file exists. If the final line is
        truncated (for example from an interrupted write), that line is ignored.
        Earlier malformed lines raise ``ValueError``.

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
