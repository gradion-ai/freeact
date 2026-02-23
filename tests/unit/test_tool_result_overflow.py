import hashlib
import re
from pathlib import Path

from pydantic_ai.messages import BinaryContent

from freeact.agent.store import SessionStore
from freeact.agent.tool_result_overflow import ToolResultOverflowManager


def _stored_path_from_notice(notice: str, working_dir: Path) -> Path:
    match = re.search(r"^Full content saved to: (.+)$", notice, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("missing saved-file reference line")
    return working_dir / match.group(1)


def test_inline_result_under_threshold_is_kept(tmp_path: Path) -> None:
    manager = ToolResultOverflowManager(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=10_000,
        preview_lines=10,
        working_dir=tmp_path,
    )
    content = {"status": "ok"}

    result = manager.materialize(content)

    assert result.overflowed is False
    assert result.content == content


def test_large_string_result_is_saved_with_preview(tmp_path: Path) -> None:
    manager = ToolResultOverflowManager(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=20,
        preview_lines=2,
        working_dir=tmp_path,
    )
    content = "line-1\nline-2\nline-3\n" + ("x" * 200)

    result = manager.materialize(content)

    assert result.overflowed is True
    assert isinstance(result.content, str)
    assert "configured inline threshold (20 bytes)" in result.content
    assert "Preview (first and last 2 lines):" in result.content
    assert "line-1" in result.content
    assert "line-2" in result.content
    assert "line-3" in result.content
    assert ".freeact/sessions/session-1/tool-results/" in result.content

    stored_path = _stored_path_from_notice(result.content, tmp_path)
    assert stored_path.suffix == ".txt"
    assert stored_path.read_text(encoding="utf-8") == content


def test_structured_result_is_saved_as_json(tmp_path: Path) -> None:
    manager = ToolResultOverflowManager(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=40,
        preview_lines=3,
        working_dir=tmp_path,
    )
    content = [{"index": i, "value": "x" * 20} for i in range(5)]

    result = manager.materialize(content)

    assert result.overflowed is True
    assert isinstance(result.content, str)
    stored_path = _stored_path_from_notice(result.content, tmp_path)
    assert stored_path.suffix == ".json"
    assert '"index": 0' in stored_path.read_text(encoding="utf-8")


def test_text_binary_result_uses_text_preview(tmp_path: Path) -> None:
    manager = ToolResultOverflowManager(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=8,
        preview_lines=2,
        working_dir=tmp_path,
    )
    content = BinaryContent(data=b"alpha\nbeta\ngamma\n", media_type="text/plain")

    result = manager.materialize(content)

    assert result.overflowed is True
    assert isinstance(result.content, str)
    assert "alpha" in result.content
    assert "beta" in result.content
    assert "gamma" in result.content

    stored_path = _stored_path_from_notice(result.content, tmp_path)
    assert stored_path.suffix == ".txt"
    assert stored_path.read_bytes() == b"alpha\nbeta\ngamma\n"


def test_non_text_binary_preview_is_metadata(tmp_path: Path) -> None:
    manager = ToolResultOverflowManager(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=4,
        preview_lines=10,
        working_dir=tmp_path,
    )
    payload = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 16)
    content = BinaryContent(data=payload, media_type="image/png")

    result = manager.materialize(content)

    digest = hashlib.sha256(payload).hexdigest()[:12]
    assert result.overflowed is True
    assert isinstance(result.content, str)
    assert "Binary content preview unavailable." in result.content
    assert "media_type: image/png" in result.content
    assert f"size_bytes: {len(payload)}" in result.content
    assert f"sha256: {digest}" in result.content

    stored_path = _stored_path_from_notice(result.content, tmp_path)
    assert stored_path.suffix == ".png"
    assert stored_path.read_bytes() == payload


def test_large_result_stays_inline_when_session_store_missing(tmp_path: Path) -> None:
    manager = ToolResultOverflowManager(
        session_store=None,
        inline_max_bytes=1,
        preview_lines=10,
        working_dir=tmp_path,
    )
    content = "too-large"

    result = manager.materialize(content)

    assert result.overflowed is False
    assert result.content == content


def test_structured_preview_truncates_long_content_field(tmp_path: Path) -> None:
    manager = ToolResultOverflowManager(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=20,
        preview_lines=2,
        working_dir=tmp_path,
    )
    content = {"content": "x" * 5000, "status": "ok"}

    result = manager.materialize(content)

    assert result.overflowed is True
    assert isinstance(result.content, str)
    assert "Preview (first and last 2 lines):" in result.content
    assert '"status": "ok"' in result.content
    assert "[truncated" in result.content
    assert ("x" * 1000) not in result.content
