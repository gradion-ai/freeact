import re
from pathlib import Path

import pytest
from pydantic_ai.messages import BinaryContent

from freeact.agent.store import SessionStore, ToolResultMaterializer


def _stored_path_from_notice(notice: str, working_dir: Path) -> Path:
    match = re.search(r"^Full content saved to: (.+)$", notice, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("missing saved-file reference line")
    return working_dir / match.group(1)


def test_inline_result_under_threshold_is_kept(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=10_000,
        preview_chars=1000,
        working_dir=tmp_path,
    )
    content = {"status": "ok"}

    result = manager.materialize(content)

    assert result == content


def test_large_string_result_is_saved_with_preview(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=20,
        preview_chars=40,
        working_dir=tmp_path,
    )
    content = "line-1\nline-2\nline-3\n" + ("x" * 200)

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "configured inline threshold (20 bytes)" in result
    assert "Preview (~40 characters):" in result
    assert "line-1" in result
    assert ".freeact/sessions/session-1/tool-results/" in result

    stored_path = _stored_path_from_notice(result, tmp_path)
    assert stored_path.suffix == ".txt"
    assert stored_path.read_text(encoding="utf-8") == content


def test_structured_result_is_saved_as_json(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=40,
        preview_chars=1000,
        working_dir=tmp_path,
    )
    content = [{"index": i, "value": "x" * 20} for i in range(5)]

    result = manager.materialize(content)

    assert isinstance(result, str)
    stored_path = _stored_path_from_notice(result, tmp_path)
    assert stored_path.suffix == ".json"
    assert '"index": 0' in stored_path.read_text(encoding="utf-8")


def test_text_binary_result_has_no_preview(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=8,
        preview_chars=1000,
        working_dir=tmp_path,
    )
    content = BinaryContent(data=b"alpha\nbeta\ngamma\n", media_type="text/plain")

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "Preview (first and last" not in result

    stored_path = _stored_path_from_notice(result, tmp_path)
    assert stored_path.suffix == ".txt"
    assert stored_path.read_bytes() == b"alpha\nbeta\ngamma\n"


def test_preview_respects_character_limit(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=10,
        preview_chars=20,
        working_dir=tmp_path,
    )
    # Long line that stays within preview_lines but exceeds preview_chars
    content = "X" * 100

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "Preview (~20 characters):" in result
    # It should show character-based truncation message
    assert "chars omitted" in result
    # Total chars in preview should be 20
    assert result.count("X") == 20


def test_preview_respects_odd_character_limit(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=10,
        preview_chars=21,
        working_dir=tmp_path,
    )
    # 100 characters total
    content = "X" * 100

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "Preview (~21 characters):" in result
    # Should show exactly 21 'X' characters (10 prefix, 11 suffix)
    assert result.count("X") == 21
    assert "79 chars omitted" in result


def test_non_text_binary_result_has_no_preview(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=4,
        preview_chars=1000,
        working_dir=tmp_path,
    )
    payload = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 16)
    content = BinaryContent(data=payload, media_type="image/png")

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "Preview (first and last" not in result

    stored_path = _stored_path_from_notice(result, tmp_path)
    assert stored_path.suffix == ".png"
    assert stored_path.read_bytes() == payload


def test_large_result_stays_inline_when_store_write_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = SessionStore(tmp_path / ".freeact" / "sessions", "session-1")
    manager = ToolResultMaterializer(
        session_store=store,
        inline_max_bytes=1,
        preview_chars=1000,
        working_dir=tmp_path,
    )
    content = "too-large"

    def fail_save_tool_result(payload: bytes, extension: str) -> Path:
        _ = payload, extension
        raise OSError("disk full")

    monkeypatch.setattr(store, "save_tool_result", fail_save_tool_result)

    result = manager.materialize(content)

    assert result == content


def test_structured_result_has_no_preview(tmp_path: Path) -> None:
    manager = ToolResultMaterializer(
        session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
        inline_max_bytes=20,
        preview_chars=1000,
        working_dir=tmp_path,
    )
    content = {"content": "x" * 5000, "status": "ok"}

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "Preview (first and last" not in result
