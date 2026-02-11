import argparse
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import freeact.cli as cli


def test_parser_accepts_valid_session_id_uuid():
    parser = cli.create_parser()
    expected = uuid.uuid4()

    namespace = parser.parse_args(["--session-id", str(expected)])

    assert namespace.session_id == expected


def test_parser_rejects_invalid_session_id():
    parser = cli.create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--session-id", "not-a-uuid"])


@pytest.mark.asyncio
async def test_run_uses_provided_session_id_for_session_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    provided = uuid.uuid4()
    captured: dict[str, object] = {}
    sessions_dir = tmp_path / "sessions-from-config"

    class FakeSessionStore:
        def __init__(self, sessions_root: Path, session_id: str, flush_after_append: bool = False):
            captured["sessions_root"] = sessions_root
            captured["session_id"] = session_id
            captured["flush_after_append"] = flush_after_append

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent_kwargs"] = kwargs

    class FakeTerminal:
        def __init__(self, agent, console=None):
            captured["terminal_agent"] = agent

        async def run(self) -> None:
            captured["terminal_run"] = True

    async def fake_create_config(namespace: argparse.Namespace):
        return SimpleNamespace(
            sessions_dir=sessions_dir,
            ptc_servers={},
        )

    monkeypatch.setattr(cli, "create_config", fake_create_config)
    monkeypatch.setattr(cli, "SessionStore", FakeSessionStore)
    monkeypatch.setattr(cli, "Agent", FakeAgent)
    monkeypatch.setattr(cli, "Terminal", FakeTerminal)
    monkeypatch.setattr(cli, "generate_mcp_sources", AsyncMock())

    namespace = argparse.Namespace(
        sandbox=False,
        sandbox_config=None,
        record=False,
        record_dir=Path("output"),
        record_title="Conversation",
        session_id=provided,
    )
    await cli.run(namespace)

    assert captured["session_id"] == str(provided)
    assert captured["sessions_root"] == sessions_dir
    assert captured["terminal_run"] is True


@pytest.mark.asyncio
async def test_run_generates_uuid_when_session_id_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    generated = uuid.uuid4()
    captured: dict[str, object] = {}
    sessions_dir = tmp_path / "sessions-from-config"

    class FakeSessionStore:
        def __init__(self, sessions_root: Path, session_id: str, flush_after_append: bool = False):
            captured["session_id"] = session_id

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent_kwargs"] = kwargs

    class FakeTerminal:
        def __init__(self, agent, console=None):
            pass

        async def run(self) -> None:
            return None

    async def fake_create_config(namespace: argparse.Namespace):
        return SimpleNamespace(
            sessions_dir=sessions_dir,
            ptc_servers={},
        )

    monkeypatch.setattr(cli, "create_config", fake_create_config)
    monkeypatch.setattr(cli, "SessionStore", FakeSessionStore)
    monkeypatch.setattr(cli, "Agent", FakeAgent)
    monkeypatch.setattr(cli, "Terminal", FakeTerminal)
    monkeypatch.setattr(cli, "generate_mcp_sources", AsyncMock())
    monkeypatch.setattr(cli.uuid, "uuid4", lambda: generated)

    namespace = argparse.Namespace(
        sandbox=False,
        sandbox_config=None,
        record=False,
        record_dir=Path("output"),
        record_title="Conversation",
        session_id=None,
    )
    await cli.run(namespace)

    assert captured["session_id"] == str(generated)
