import re
from pathlib import Path

import pytest
from pydantic_ai.messages import BinaryContent

from freeact.agent.store import SessionStore, ToolResultMaterializer


def _make_store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / ".freeact" / "sessions", "session-1")


def _make_materializer(tmp_path: Path, inline_max_bytes: int, preview_chars: int) -> ToolResultMaterializer:
    return ToolResultMaterializer(
        session_store=_make_store(tmp_path),
        inline_max_bytes=inline_max_bytes,
        preview_chars=preview_chars,
        working_dir=tmp_path,
    )


def _stored_path_from_notice(notice: str, working_dir: Path) -> Path:
    match = re.search(r"^Full content saved to: (.+)$", notice, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("missing saved-file reference line")
    return working_dir / match.group(1)


def test_inline_result_under_threshold_is_kept(tmp_path: Path) -> None:
    manager = _make_materializer(tmp_path, inline_max_bytes=10_000, preview_chars=1000)
    content = {"status": "ok"}

    result = manager.materialize(content)

    assert result == content


def test_large_string_result_is_saved_with_preview(tmp_path: Path) -> None:
    manager = _make_materializer(tmp_path, inline_max_bytes=20, preview_chars=40)
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
    manager = _make_materializer(tmp_path, inline_max_bytes=40, preview_chars=1000)
    content = [{"index": i, "value": "x" * 20} for i in range(5)]

    result = manager.materialize(content)

    assert isinstance(result, str)
    stored_path = _stored_path_from_notice(result, tmp_path)
    assert stored_path.suffix == ".json"
    assert '"index": 0' in stored_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("inline_max_bytes", "payload", "media_type", "suffix"),
    [
        (8, b"alpha\nbeta\ngamma\n", "text/plain", ".txt"),
        (4, b"\x89PNG\r\n\x1a\n" + (b"\x00" * 16), "image/png", ".png"),
    ],
)
def test_binary_result_has_no_preview(
    tmp_path: Path, inline_max_bytes: int, payload: bytes, media_type: str, suffix: str
) -> None:
    manager = _make_materializer(tmp_path, inline_max_bytes=inline_max_bytes, preview_chars=1000)
    content = BinaryContent(data=payload, media_type=media_type)

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "Preview (first and last" not in result

    stored_path = _stored_path_from_notice(result, tmp_path)
    assert stored_path.suffix == suffix
    assert stored_path.read_bytes() == payload


@pytest.mark.parametrize(
    ("preview_chars", "omitted_message"),
    [
        (20, "80 chars omitted"),
        (21, "79 chars omitted"),
    ],
)
def test_preview_respects_character_limit(tmp_path: Path, preview_chars: int, omitted_message: str) -> None:
    manager = _make_materializer(tmp_path, inline_max_bytes=10, preview_chars=preview_chars)
    content = "X" * 100

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert f"Preview (~{preview_chars} characters):" in result
    assert omitted_message in result
    assert result.count("X") == preview_chars


def test_large_result_stays_inline_when_store_write_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _make_store(tmp_path)
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
    manager = _make_materializer(tmp_path, inline_max_bytes=20, preview_chars=1000)
    content = {"content": "x" * 5000, "status": "ok"}

    result = manager.materialize(content)

    assert isinstance(result, str)
    assert "Preview (first and last" not in result
