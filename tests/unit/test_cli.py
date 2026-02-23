import argparse
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import freeact.cli as cli


@pytest.fixture(autouse=True)
def _set_gemini_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")


def test_parser_accepts_valid_session_id_uuid():
    parser = cli.create_parser()
    expected = uuid.uuid4()

    namespace = parser.parse_args(["--session-id", str(expected)])

    assert namespace.session_id == expected


def test_parser_rejects_invalid_session_id():
    parser = cli.create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--session-id", "not-a-uuid"])


@pytest.mark.parametrize("removed_flag", ["--legacy-ui", "--record"])
def test_parser_rejects_removed_legacy_flags(removed_flag: str):
    parser = cli.create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([removed_flag])


@pytest.mark.asyncio
async def test_create_config_saves_defaults_when_freeact_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    config, terminal_config = await cli.create_config()

    assert config.freeact_dir == tmp_path / ".freeact"
    assert (config.freeact_dir / "agent.json").exists()
    assert (config.freeact_dir / "terminal.json").exists()
    assert terminal_config.expand_all_toggle_key == "ctrl+o"


@pytest.mark.asyncio
async def test_create_config_loads_existing_without_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)

    (freeact_dir / "agent.json").write_text(json.dumps({"model": "test-model", "ptc_servers": {}}))
    (freeact_dir / "terminal.json").write_text(json.dumps({"expand_all_toggle_key": "ctrl+p"}))

    config, terminal_config = await cli.create_config()

    assert config.model == "test-model"
    assert terminal_config.expand_all_toggle_key == "ctrl+p"


@pytest.mark.asyncio
async def test_create_config_creates_terminal_json_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    (freeact_dir / "agent.json").write_text(json.dumps({"model": "test-model", "ptc_servers": {}}))

    _, terminal_config = await cli.create_config()

    terminal_json = freeact_dir / "terminal.json"
    assert terminal_json.exists()
    assert terminal_config.expand_all_toggle_key == "ctrl+o"


def test_main_init_does_not_overwrite_existing_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    terminal_json = freeact_dir / "terminal.json"
    terminal_json.write_text('{"expand_all_toggle_key": "ctrl+p"}')

    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        cli,
        "parse_args",
        lambda: argparse.Namespace(command="init", log_level="info"),
    )
    monkeypatch.setattr(cli, "configure_logging", lambda _: None)

    cli.main()

    data = json.loads(terminal_json.read_text())
    assert data["expand_all_toggle_key"] == "ctrl+p"


@pytest.mark.asyncio
async def test_run_passes_provided_session_id_to_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    provided = uuid.uuid4()
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent_kwargs"] = kwargs

    class FakeTerminal:
        def __init__(self, agent, console=None, config=None):
            captured["terminal_agent"] = agent

        async def run(self) -> None:
            captured["terminal_run"] = True

    async def fake_create_config():
        config = SimpleNamespace(
            enable_persistence=True,
            ptc_servers={},
            generated_dir=tmp_path / "generated",
        )
        terminal_config = object()
        return config, terminal_config

    monkeypatch.setattr(cli, "create_config", fake_create_config)
    monkeypatch.setattr(cli, "Agent", FakeAgent)
    monkeypatch.setattr(cli, "TerminalInterface", FakeTerminal)
    monkeypatch.setattr(cli, "generate_mcp_sources", AsyncMock())

    namespace = argparse.Namespace(
        sandbox=False,
        sandbox_config=None,
        session_id=provided,
    )
    await cli.run(namespace)

    agent_kwargs = captured["agent_kwargs"]
    assert isinstance(agent_kwargs, dict)
    assert agent_kwargs["session_id"] == str(provided)
    assert captured["terminal_run"] is True


@pytest.mark.asyncio
async def test_run_passes_none_session_id_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent_kwargs"] = kwargs

    class FakeTerminal:
        def __init__(self, agent, console=None, config=None):
            pass

        async def run(self) -> None:
            return None

    async def fake_create_config():
        config = SimpleNamespace(
            enable_persistence=True,
            ptc_servers={},
            generated_dir=tmp_path / "generated",
        )
        terminal_config = object()
        return config, terminal_config

    monkeypatch.setattr(cli, "create_config", fake_create_config)
    monkeypatch.setattr(cli, "Agent", FakeAgent)
    monkeypatch.setattr(cli, "TerminalInterface", FakeTerminal)
    monkeypatch.setattr(cli, "generate_mcp_sources", AsyncMock())

    namespace = argparse.Namespace(
        sandbox=False,
        sandbox_config=None,
        session_id=None,
    )
    await cli.run(namespace)

    agent_kwargs = captured["agent_kwargs"]
    assert isinstance(agent_kwargs, dict)
    assert agent_kwargs["session_id"] is None


@pytest.mark.asyncio
async def test_run_rejects_session_id_when_persistence_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    provided = uuid.uuid4()

    async def fake_create_config():
        config = SimpleNamespace(
            enable_persistence=False,
            ptc_servers={},
            generated_dir=tmp_path / "generated",
        )
        terminal_config = object()
        return config, terminal_config

    monkeypatch.setattr(cli, "create_config", fake_create_config)
    monkeypatch.setattr(cli, "Agent", object)
    monkeypatch.setattr(cli, "TerminalInterface", object)
    monkeypatch.setattr(cli, "generate_mcp_sources", AsyncMock())

    namespace = argparse.Namespace(
        sandbox=False,
        sandbox_config=None,
        session_id=provided,
    )

    with pytest.raises(SystemExit, match="--session-id requires enable_persistence=true"):
        await cli.run(namespace)
