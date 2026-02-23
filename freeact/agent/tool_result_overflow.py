import hashlib
import json
import logging
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai.mcp import ToolResult
from pydantic_ai.messages import BinaryContent
from pydantic_core import to_jsonable_python

from freeact.agent.store import SessionStore, StoredToolResultFile

logger = logging.getLogger("freeact")

_MAX_PREVIEW_LINE_CHARS = 240
_MAX_PREVIEW_TOTAL_BYTES = 4096


@dataclass(frozen=True)
class MaterializedToolResult:
    """Tool result after applying inline-size overflow handling."""

    content: ToolResult
    overflowed: bool
    actual_size_bytes: int


@dataclass(frozen=True)
class _CanonicalToolResult:
    payload: bytes
    ext: str
    preview_header: str
    preview_lines: list[str]


class ToolResultOverflowManager:
    """Materialize tool results with optional file-based overflow storage."""

    def __init__(
        self,
        *,
        session_store: SessionStore | None,
        inline_max_bytes: int,
        preview_lines: int,
        working_dir: Path,
    ) -> None:
        self._session_store = session_store
        self._inline_max_bytes = inline_max_bytes
        self._preview_lines = preview_lines
        self._working_dir = working_dir

    def materialize(self, content: ToolResult) -> MaterializedToolResult:
        """Return inline content or an overflow notice when above size threshold."""
        canonical = self._canonicalize(content)
        actual_size_bytes = len(canonical.payload)

        if actual_size_bytes <= self._inline_max_bytes:
            return MaterializedToolResult(
                content=content,
                overflowed=False,
                actual_size_bytes=actual_size_bytes,
            )

        if self._session_store is None:
            logger.warning(
                "tool result exceeded inline threshold but no session store is configured (size=%s, threshold=%s)",
                actual_size_bytes,
                self._inline_max_bytes,
            )
            return MaterializedToolResult(
                content=content,
                overflowed=False,
                actual_size_bytes=actual_size_bytes,
            )

        try:
            stored_file = self._session_store.save_tool_result(canonical.payload, canonical.ext)
        except Exception:
            logger.exception(
                "failed to persist large tool result; keeping inline payload (size=%s, threshold=%s)",
                actual_size_bytes,
                self._inline_max_bytes,
            )
            return MaterializedToolResult(
                content=content,
                overflowed=False,
                actual_size_bytes=actual_size_bytes,
            )

        relative_path = self._relative_path(stored_file)
        notice = self._build_notice(
            preview_header=canonical.preview_header,
            preview_lines=canonical.preview_lines,
            actual_size_bytes=actual_size_bytes,
            relative_path=relative_path,
        )
        return MaterializedToolResult(
            content=notice,
            overflowed=True,
            actual_size_bytes=actual_size_bytes,
        )

    def _canonicalize(self, content: ToolResult) -> _CanonicalToolResult:
        match content:
            case str() as text:
                return _CanonicalToolResult(
                    payload=text.encode("utf-8"),
                    ext="txt",
                    preview_header=f"Preview (first and last {self._preview_lines} lines):",
                    preview_lines=self._take_preview_lines(text),
                )
            case BinaryContent(data=data, media_type=media_type):
                ext = _media_type_to_ext(media_type)
                match media_type:
                    case str(mt) if mt.startswith("text/"):
                        decoded = data.decode("utf-8", errors="replace")
                        return _CanonicalToolResult(
                            payload=data,
                            ext=ext,
                            preview_header=f"Preview (first and last {self._preview_lines} lines):",
                            preview_lines=self._take_preview_lines(decoded),
                        )
                    case _:
                        digest = hashlib.sha256(data).hexdigest()[:12]
                        preview = [
                            "Binary content preview unavailable.",
                            f"media_type: {media_type}",
                            f"size_bytes: {len(data)}",
                            f"sha256: {digest}",
                        ]
                        return _CanonicalToolResult(
                            payload=data,
                            ext=ext,
                            preview_header="Preview:",
                            preview_lines=preview,
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
                    ext="json",
                    preview_header=f"Preview (first and last {self._preview_lines} lines):",
                    preview_lines=self._take_preview_lines(rendered),
                )

    def _take_preview_lines(self, text: str) -> list[str]:
        lines = text.splitlines()
        if not lines:
            return ["<empty>"]

        boundary = self._preview_lines
        if len(lines) <= boundary * 2:
            selected = lines
        else:
            omitted = len(lines) - (boundary * 2)
            selected = [
                *lines[:boundary],
                f"... ({omitted} lines omitted) ...",
                *lines[-boundary:],
            ]

        capped_lines = [self._cap_preview_line(line) for line in selected]
        return self._cap_preview_total_bytes(capped_lines)

    def _cap_preview_line(self, line: str) -> str:
        if len(line) <= _MAX_PREVIEW_LINE_CHARS:
            return line

        omitted = len(line) - _MAX_PREVIEW_LINE_CHARS
        return f"{line[:_MAX_PREVIEW_LINE_CHARS]}... [truncated {omitted} chars]"

    def _cap_preview_total_bytes(self, lines: list[str]) -> list[str]:
        kept: list[str] = []
        used = 0

        for line in lines:
            extra_sep = 1 if kept else 0
            budget = _MAX_PREVIEW_TOTAL_BYTES - used - extra_sep
            if budget <= 0:
                break

            encoded = line.encode("utf-8")
            if len(encoded) <= budget:
                kept.append(line)
                used += extra_sep + len(encoded)
                continue

            trimmed = self._trim_to_byte_budget(line, budget)
            if trimmed:
                kept.append(trimmed)
            break

        return kept if kept else ["<preview truncated>"]

    @staticmethod
    def _trim_to_byte_budget(text: str, budget: int) -> str:
        if budget <= 0:
            return ""
        trimmed = text
        while trimmed and len(trimmed.encode("utf-8")) > budget:
            trimmed = trimmed[:-1]
        return trimmed

    def _build_notice(
        self,
        *,
        preview_header: str,
        preview_lines: list[str],
        actual_size_bytes: int,
        relative_path: Path,
    ) -> str:
        lines = [
            f"Tool result exceeded configured inline threshold ({self._inline_max_bytes} bytes).",
            f"Actual size: {actual_size_bytes} bytes.",
            preview_header,
            *preview_lines,
            f"Full content saved to: {relative_path.as_posix()}",
        ]
        return "\n".join(lines)

    def _relative_path(self, stored_file: StoredToolResultFile) -> Path:
        try:
            return stored_file.absolute_path.relative_to(self._working_dir)
        except ValueError:
            return stored_file.relative_path


def _media_type_to_ext(media_type: str) -> str:
    known_ext: dict[str, str] = {
        "text/plain": "txt",
        "text/markdown": "md",
        "text/csv": "csv",
        "application/json": "json",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "application/pdf": "pdf",
    }
    if media_type in known_ext:
        return known_ext[media_type]

    guessed = mimetypes.guess_extension(media_type, strict=False)
    if not guessed:
        return "bin"
    ext = guessed.lstrip(".").lower()
    return ext if ext.isalnum() else "bin"
