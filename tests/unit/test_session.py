# Covers behavior-inventory.md sections: 8 (tool result overflow), 10 (session persistence & resume)
import json
import re
from pathlib import Path

import pytest
from pydantic_ai.messages import BinaryContent, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_core import to_jsonable_python

from freeact.agent.session import Session, SessionStore, ToolResultMaterializer


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(sessions_root=tmp_path, session_id="session-1")


def _session_file(tmp_path: Path) -> Path:
    return tmp_path / "session-1" / "main.jsonl"


def _sample_messages() -> list[ModelRequest | ModelResponse]:
    return [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="world")]),
    ]


def _jsonable_messages(messages: list[ModelRequest | ModelResponse]) -> list[dict[str, object]]:
    return [to_jsonable_python(message, bytes_mode="base64") for message in messages]


def _write_session_file(tmp_path: Path, content: str) -> None:
    session_file = _session_file(tmp_path)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(content)


def _valid_envelope_line(meta_extra: dict[str, str] | None = None) -> str:
    message = to_jsonable_python(ModelRequest(parts=[UserPromptPart(content="hello")]), bytes_mode="base64")
    meta: dict[str, str] = {"ts": "2026-02-11T10:22:08.423090Z", **(meta_extra or {})}
    return json.dumps({"v": 1, "message": message, "meta": meta})


class TestSessionStore:
    def test_append_load_round_trip_model_messages(self, store: SessionStore) -> None:
        messages = _sample_messages()

        store.append_messages(agent_id="main", messages=messages)
        loaded = store.load_messages(agent_id="main")

        assert _jsonable_messages(loaded) == _jsonable_messages(messages)

    def test_append_writes_envelope_without_agent_id(self, store: SessionStore, tmp_path: Path) -> None:
        messages = _sample_messages()

        store.append_messages(agent_id="main", messages=messages)

        lines = [json.loads(line) for line in _session_file(tmp_path).read_text().splitlines()]

        assert len(lines) == len(messages)
        for line in lines:
            assert set(line.keys()) == {"v", "message", "meta"}
            assert line["v"] == 1
            assert isinstance(line["message"], dict)
            assert isinstance(line["meta"], dict)
            assert "ts" in line["meta"]
            assert "agent_id" not in line["meta"]

    def test_load_rejects_meta_agent_id(self, store: SessionStore, tmp_path: Path) -> None:
        _write_session_file(tmp_path, _valid_envelope_line({"agent_id": "main"}) + "\n")

        with pytest.raises(ValueError, match="meta.agent_id"):
            store.load_messages(agent_id="main")

    def test_append_writes_one_line_per_message(self, store: SessionStore, tmp_path: Path) -> None:
        messages = _sample_messages() + _sample_messages()

        store.append_messages(agent_id="main", messages=messages)

        assert len(_session_file(tmp_path).read_text().splitlines()) == len(messages)

    def test_load_ignores_malformed_trailing_line(self, store: SessionStore, tmp_path: Path) -> None:
        messages = _sample_messages()
        store.append_messages(agent_id="main", messages=messages)

        with _session_file(tmp_path).open("a", encoding="utf-8") as f:
            f.write('{"v": 1, "message": ')

        loaded = store.load_messages(agent_id="main")
        assert _jsonable_messages(loaded) == _jsonable_messages(messages)

    def test_load_raises_on_non_tail_malformed_line(self, store: SessionStore, tmp_path: Path) -> None:
        valid_line = _valid_envelope_line()
        _write_session_file(tmp_path, f"{valid_line}\n{{bad-json}}\n{valid_line}\n")

        with pytest.raises(ValueError, match="Malformed JSONL"):
            store.load_messages(agent_id="main")

    def test_delete_last_messages_truncates_persisted_tail(self, store: SessionStore) -> None:
        messages = _sample_messages() + _sample_messages()

        store.append_messages(agent_id="main", messages=messages)
        store.delete_last_messages(agent_id="main", count=2)

        loaded = store.load_messages(agent_id="main")
        assert _jsonable_messages(loaded) == _jsonable_messages(messages[:2])

    def test_delete_last_messages_rejects_excess_count(self, store: SessionStore) -> None:
        store.append_messages(agent_id="main", messages=_sample_messages())

        with pytest.raises(ValueError, match="Cannot delete 3 messages"):
            store.delete_last_messages(agent_id="main", count=3)

    @pytest.mark.parametrize("flush_after_append", [True, False])
    def test_flush_after_append(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flush_after_append: bool
    ) -> None:
        store = SessionStore(sessions_root=tmp_path, session_id="session-1", flush_after_append=flush_after_append)
        fake_file = _FakeFile()

        def fake_open(self: Path, mode: str = "r", encoding: str | None = None) -> _FakeFile:
            return fake_file

        monkeypatch.setattr(Path, "open", fake_open)
        store.append_messages(agent_id="main", messages=_sample_messages())

        assert fake_file.flush_called is flush_after_append

    def test_save_tool_result_writes_payload_file(self, store: SessionStore) -> None:
        stored = store.save_tool_result(payload=b"tool-output", extension="txt")

        assert stored.exists()
        assert stored.read_bytes() == b"tool-output"

    def test_save_tool_result_filename_format(self, store: SessionStore) -> None:
        stored = store.save_tool_result(payload=b"x", extension="json")

        assert re.fullmatch(r"[0-9a-f]{8}\.json", stored.name)

    def test_save_tool_result_sanitizes_extension(self, store: SessionStore) -> None:
        stored = store.save_tool_result(payload=b"x", extension="../bad")

        assert stored.suffix == ".bin"


class _FakeFile:
    def __init__(self) -> None:
        self.flush_called = False

    def write(self, _: str) -> int:
        return 0

    def flush(self) -> None:
        self.flush_called = True

    def __enter__(self) -> "_FakeFile":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _make_overflow_store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / ".freeact" / "sessions", "session-1")


def _make_materializer(tmp_path: Path, inline_max_bytes: int, preview_chars: int) -> ToolResultMaterializer:
    return ToolResultMaterializer(
        session_store=_make_overflow_store(tmp_path),
        inline_max_bytes=inline_max_bytes,
        preview_chars=preview_chars,
        working_dir=tmp_path,
    )


def _stored_path_from_notice(notice: str, working_dir: Path) -> Path:
    match = re.search(r"^Full content saved to: (.+)$", notice, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("missing saved-file reference line")
    return working_dir / match.group(1)


class TestToolResultMaterializer:
    def test_inline_result_under_threshold_is_kept(self, tmp_path: Path) -> None:
        manager = _make_materializer(tmp_path, inline_max_bytes=10_000, preview_chars=1000)
        content = {"status": "ok"}

        result = manager.materialize(content)

        assert result == content

    def test_large_string_result_is_saved_with_preview(self, tmp_path: Path) -> None:
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

    def test_structured_result_is_saved_as_json(self, tmp_path: Path) -> None:
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
        self, tmp_path: Path, inline_max_bytes: int, payload: bytes, media_type: str, suffix: str
    ) -> None:
        manager = _make_materializer(tmp_path, inline_max_bytes=inline_max_bytes, preview_chars=1000)
        content = BinaryContent(data=payload, media_type=media_type)

        result = manager.materialize(content)

        assert isinstance(result, str)
        assert "Preview" not in result

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
    def test_preview_respects_character_limit(self, tmp_path: Path, preview_chars: int, omitted_message: str) -> None:
        manager = _make_materializer(tmp_path, inline_max_bytes=10, preview_chars=preview_chars)
        content = "X" * 100

        result = manager.materialize(content)

        assert isinstance(result, str)
        assert f"Preview (~{preview_chars} characters):" in result
        assert omitted_message in result
        assert result.count("X") == preview_chars

    def test_large_result_stays_inline_when_store_write_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        overflow_store = _make_overflow_store(tmp_path)
        manager = ToolResultMaterializer(
            session_store=overflow_store,
            inline_max_bytes=1,
            preview_chars=1000,
            working_dir=tmp_path,
        )
        content = "too-large"

        def fail_save_tool_result(payload: bytes, extension: str) -> Path:
            _ = payload, extension
            raise OSError("disk full")

        monkeypatch.setattr(overflow_store, "save_tool_result", fail_save_tool_result)

        result = manager.materialize(content)

        assert result == content

    def test_structured_result_has_no_preview(self, tmp_path: Path) -> None:
        manager = _make_materializer(tmp_path, inline_max_bytes=20, preview_chars=1000)
        content = {"content": "x" * 5000, "status": "ok"}

        result = manager.materialize(content)

        assert isinstance(result, str)
        assert "Preview" not in result


def _make_session(
    tmp_path: Path,
    store: SessionStore | None,
    agent_id: str = "main",
    inline_max_bytes: int = 32768,
    preview_chars: int = 100,
) -> Session:
    return Session(
        agent_id=agent_id,
        store=store,
        working_dir=tmp_path,
        inline_max_bytes=inline_max_bytes,
        preview_chars=preview_chars,
    )


class TestSession:
    @pytest.mark.asyncio
    async def test_append_extends_messages_and_persists(self, tmp_path: Path, store: SessionStore) -> None:
        session = _make_session(tmp_path, store)
        messages = _sample_messages()

        await session.append(messages)

        assert _jsonable_messages(session.messages) == _jsonable_messages(messages)
        assert len(session) == len(messages)
        assert _jsonable_messages(store.load_messages(agent_id="main")) == _jsonable_messages(messages)

    @pytest.mark.asyncio
    async def test_rollback_truncates_history_and_store(self, tmp_path: Path, store: SessionStore) -> None:
        session = _make_session(tmp_path, store)
        messages = _sample_messages() + _sample_messages()
        await session.append(messages)

        await session.rollback(2)

        assert _jsonable_messages(session.messages) == _jsonable_messages(messages[:2])
        assert _jsonable_messages(store.load_messages(agent_id="main")) == _jsonable_messages(messages[:2])

    @pytest.mark.asyncio
    async def test_rollback_rejects_excess_count(self, tmp_path: Path, store: SessionStore) -> None:
        session = _make_session(tmp_path, store)
        await session.append(_sample_messages())

        with pytest.raises(ValueError, match="Cannot rollback 3 messages"):
            await session.rollback(3)

    @pytest.mark.asyncio
    async def test_load_restores_main_history(self, tmp_path: Path, store: SessionStore) -> None:
        messages = _sample_messages()
        store.append_messages(agent_id="main", messages=messages)
        session = _make_session(tmp_path, store, agent_id="main")

        await session.load()

        assert _jsonable_messages(session.messages) == _jsonable_messages(messages)

    @pytest.mark.asyncio
    async def test_load_is_noop_for_subagents(self, tmp_path: Path, store: SessionStore) -> None:
        store.append_messages(agent_id="main", messages=_sample_messages())
        store.append_messages(agent_id="sub-1", messages=_sample_messages())
        session = _make_session(tmp_path, store, agent_id="sub-1")

        await session.load()

        assert session.messages == []

    @pytest.mark.asyncio
    async def test_history_id_is_main_unless_agent_id_starts_with_sub(
        self, tmp_path: Path, store: SessionStore
    ) -> None:
        messages = _sample_messages()
        store.append_messages(agent_id="main", messages=messages)
        session = _make_session(tmp_path, store, agent_id="root")

        await session.load()

        assert _jsonable_messages(session.messages) == _jsonable_messages(messages)

    @pytest.mark.asyncio
    async def test_materialize_passthrough_without_store(self, tmp_path: Path) -> None:
        session = _make_session(tmp_path, store=None, inline_max_bytes=1)
        content = "x" * 1000

        result = await session.materialize(content)

        assert result == content

    @pytest.mark.asyncio
    async def test_materialize_text_returns_text_and_truncation_flag(self, tmp_path: Path, store: SessionStore) -> None:
        session = _make_session(tmp_path, store, inline_max_bytes=10)

        small_text, small_truncated = await session.materialize_text("short")
        assert small_text == "short"
        assert small_truncated is False

        large = "y" * 1000
        large_text, large_truncated = await session.materialize_text(large)
        assert large_text != large
        assert "inline threshold" in large_text
        assert large_truncated is True
