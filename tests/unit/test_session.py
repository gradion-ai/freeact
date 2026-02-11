import json
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_core import to_jsonable_python

from freeact.agent.session import SessionStore


def _sample_messages() -> list[ModelRequest | ModelResponse]:
    return [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="world")]),
    ]


def _jsonable_messages(messages: list[ModelRequest | ModelResponse]) -> list[dict[str, object]]:
    return [to_jsonable_python(message, bytes_mode="base64") for message in messages]


def test_append_load_round_trip_model_messages(tmp_path: Path):
    store = SessionStore(sessions_root=tmp_path, session_id="session-1")
    messages = _sample_messages()

    store.append(agent_id="main", messages=messages)
    loaded = store.load(agent_id="main")

    assert _jsonable_messages(loaded) == _jsonable_messages(messages)


def test_append_writes_envelope_without_agent_id(tmp_path: Path):
    store = SessionStore(sessions_root=tmp_path, session_id="session-1")
    messages = _sample_messages()

    store.append(agent_id="main", messages=messages)

    session_file = tmp_path / "session-1" / "main.jsonl"
    lines = [json.loads(line) for line in session_file.read_text().splitlines()]

    assert len(lines) == len(messages)
    for line in lines:
        assert set(line.keys()) == {"v", "message", "meta"}
        assert line["v"] == 1
        assert isinstance(line["message"], dict)
        assert isinstance(line["meta"], dict)
        assert "ts" in line["meta"]
        assert "agent_id" not in line["meta"]


def test_load_rejects_meta_agent_id(tmp_path: Path):
    session_dir = tmp_path / "session-1"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "main.jsonl"
    message = to_jsonable_python(ModelRequest(parts=[UserPromptPart(content="hello")]), bytes_mode="base64")
    session_file.write_text(
        json.dumps(
            {
                "v": 1,
                "message": message,
                "meta": {
                    "ts": "2026-02-11T10:22:08.423090Z",
                    "agent_id": "main",
                },
            }
        )
        + "\n"
    )

    store = SessionStore(sessions_root=tmp_path, session_id="session-1")

    with pytest.raises(ValueError, match="meta.agent_id"):
        store.load(agent_id="main")


def test_append_writes_one_line_per_message(tmp_path: Path):
    store = SessionStore(sessions_root=tmp_path, session_id="session-1")
    messages = _sample_messages() + _sample_messages()

    store.append(agent_id="main", messages=messages)

    session_file = tmp_path / "session-1" / "main.jsonl"
    assert len(session_file.read_text().splitlines()) == len(messages)


def test_load_ignores_malformed_trailing_line(tmp_path: Path):
    store = SessionStore(sessions_root=tmp_path, session_id="session-1")
    messages = _sample_messages()
    store.append(agent_id="main", messages=messages)

    session_file = tmp_path / "session-1" / "main.jsonl"
    with session_file.open("a", encoding="utf-8") as f:
        f.write('{"v": 1, "message": ')

    loaded = store.load(agent_id="main")
    assert _jsonable_messages(loaded) == _jsonable_messages(messages)


def test_load_raises_on_non_tail_malformed_line(tmp_path: Path):
    session_dir = tmp_path / "session-1"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "main.jsonl"
    message = to_jsonable_python(ModelRequest(parts=[UserPromptPart(content="hello")]), bytes_mode="base64")
    valid_line = json.dumps({"v": 1, "message": message, "meta": {"ts": "2026-02-11T10:22:08.423090Z"}})
    session_file.write_text(f"{valid_line}\n{{bad-json}}\n{valid_line}\n")

    store = SessionStore(sessions_root=tmp_path, session_id="session-1")

    with pytest.raises(ValueError, match="Malformed JSONL"):
        store.load(agent_id="main")


def test_flush_after_append_true_calls_flush(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = SessionStore(sessions_root=tmp_path, session_id="session-1", flush_after_append=True)
    flush_called = False

    class _FakeFile:
        def write(self, _: str) -> int:
            return 0

        def flush(self) -> None:
            nonlocal flush_called
            flush_called = True

        def __enter__(self) -> "_FakeFile":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_open(self: Path, mode: str = "r", encoding: str | None = None) -> _FakeFile:
        return _FakeFile()

    monkeypatch.setattr(Path, "open", fake_open)
    store.append(agent_id="main", messages=_sample_messages())

    assert flush_called is True


def test_flush_after_append_false_does_not_force_flush(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = SessionStore(sessions_root=tmp_path, session_id="session-1", flush_after_append=False)
    flush_called = False

    class _FakeFile:
        def write(self, _: str) -> int:
            return 0

        def flush(self) -> None:
            nonlocal flush_called
            flush_called = True

        def __enter__(self) -> "_FakeFile":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_open(self: Path, mode: str = "r", encoding: str | None = None) -> _FakeFile:
        return _FakeFile()

    monkeypatch.setattr(Path, "open", fake_open)
    store.append(agent_id="main", messages=_sample_messages())

    assert flush_called is False
