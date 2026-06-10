import json
import re
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_core import to_jsonable_python

from freeact.agent.store import SessionStore


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


def test_append_load_round_trip_model_messages(store: SessionStore):
    messages = _sample_messages()

    store.append_messages(agent_id="main", messages=messages)
    loaded = store.load_messages(agent_id="main")

    assert _jsonable_messages(loaded) == _jsonable_messages(messages)


def test_append_writes_envelope_without_agent_id(store: SessionStore, tmp_path: Path):
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


def test_load_rejects_meta_agent_id(store: SessionStore, tmp_path: Path):
    _write_session_file(tmp_path, _valid_envelope_line({"agent_id": "main"}) + "\n")

    with pytest.raises(ValueError, match="meta.agent_id"):
        store.load_messages(agent_id="main")


def test_append_writes_one_line_per_message(store: SessionStore, tmp_path: Path):
    messages = _sample_messages() + _sample_messages()

    store.append_messages(agent_id="main", messages=messages)

    assert len(_session_file(tmp_path).read_text().splitlines()) == len(messages)


def test_load_ignores_malformed_trailing_line(store: SessionStore, tmp_path: Path):
    messages = _sample_messages()
    store.append_messages(agent_id="main", messages=messages)

    with _session_file(tmp_path).open("a", encoding="utf-8") as f:
        f.write('{"v": 1, "message": ')

    loaded = store.load_messages(agent_id="main")
    assert _jsonable_messages(loaded) == _jsonable_messages(messages)


def test_load_raises_on_non_tail_malformed_line(store: SessionStore, tmp_path: Path):
    valid_line = _valid_envelope_line()
    _write_session_file(tmp_path, f"{valid_line}\n{{bad-json}}\n{valid_line}\n")

    with pytest.raises(ValueError, match="Malformed JSONL"):
        store.load_messages(agent_id="main")


def test_delete_last_messages_truncates_persisted_tail(store: SessionStore) -> None:
    messages = _sample_messages() + _sample_messages()

    store.append_messages(agent_id="main", messages=messages)
    store.delete_last_messages(agent_id="main", count=2)

    loaded = store.load_messages(agent_id="main")
    assert _jsonable_messages(loaded) == _jsonable_messages(messages[:2])


def test_delete_last_messages_rejects_excess_count(store: SessionStore) -> None:
    store.append_messages(agent_id="main", messages=_sample_messages())

    with pytest.raises(ValueError, match="Cannot delete 3 messages"):
        store.delete_last_messages(agent_id="main", count=3)


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


@pytest.mark.parametrize("flush_after_append", [True, False])
def test_flush_after_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flush_after_append: bool):
    store = SessionStore(sessions_root=tmp_path, session_id="session-1", flush_after_append=flush_after_append)
    fake_file = _FakeFile()

    def fake_open(self: Path, mode: str = "r", encoding: str | None = None) -> _FakeFile:
        return fake_file

    monkeypatch.setattr(Path, "open", fake_open)
    store.append_messages(agent_id="main", messages=_sample_messages())

    assert fake_file.flush_called is flush_after_append


def test_save_tool_result_writes_payload_file(store: SessionStore) -> None:
    stored = store.save_tool_result(payload=b"tool-output", extension="txt")

    assert stored.exists()
    assert stored.read_bytes() == b"tool-output"


def test_save_tool_result_filename_format(store: SessionStore) -> None:
    stored = store.save_tool_result(payload=b"x", extension="json")

    assert re.fullmatch(r"[0-9a-f]{8}\.json", stored.name)


def test_save_tool_result_sanitizes_extension(store: SessionStore) -> None:
    stored = store.save_tool_result(payload=b"x", extension="../bad")

    assert stored.suffix == ".bin"
