# Covers behavior-inventory.md section: 18 (CLI commands & flags)
import argparse
import uuid
from pathlib import Path
from typing import Any

import pytest

import freeact.cli as cli


@pytest.fixture(autouse=True)
def _set_gemini_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test")


def test_parser_accepts_valid_session_id_uuid() -> None:
    parser = cli.create_parser()
    expected = uuid.uuid4()

    namespace = parser.parse_args(["--session-id", str(expected)])

    assert namespace.session_id == expected


def test_parser_rejects_invalid_session_id() -> None:
    parser = cli.create_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--session-id", "not-a-uuid"])


def test_parser_run_is_default_command() -> None:
    parser = cli.create_parser()
    assert parser.parse_args([]).command == "run"
    assert parser.parse_args(["run"]).command == "run"
    assert parser.parse_args(["init"]).command == "init"


def test_parser_flags() -> None:
    parser = cli.create_parser()
    namespace = parser.parse_args(["--sandbox", "--sandbox-config", "/tmp/sb.json", "--skip-permissions"])
    assert namespace.sandbox is True
    assert namespace.sandbox_config == Path("/tmp/sb.json")
    assert namespace.skip_permissions is True
    assert namespace.log_level == "info"


def test_initialize_creates_workspace(tmp_path: Path) -> None:
    cfg = cli.initialize(tmp_path)

    freeact_dir = tmp_path / ".freeact"
    assert (freeact_dir / "config.toml").exists()
    assert (freeact_dir / "permissions.toml").exists()
    assert (freeact_dir / "sessions").is_dir()
    assert cfg.terminal.expand_all_toggle_key == "ctrl+o"


def test_initialize_loads_existing_without_overwrite(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    (freeact_dir / "config.toml").write_text('[terminal]\nexpand_all_toggle_key = "ctrl+p"\n')

    cfg = cli.initialize(tmp_path)

    assert cfg.terminal.expand_all_toggle_key == "ctrl+p"
    assert 'expand_all_toggle_key = "ctrl+p"' in (freeact_dir / "config.toml").read_text()


def test_main_init_does_not_overwrite_existing_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    config_file = freeact_dir / "config.toml"
    config_file.write_text('[terminal]\nexpand_all_toggle_key = "ctrl+p"\n')

    monkeypatch.setattr(cli, "find_dotenv", lambda **kwargs: "")
    monkeypatch.setattr(cli, "load_dotenv", lambda *args: None)
    monkeypatch.setattr(cli, "parse_args", lambda: argparse.Namespace(command="init", log_level="info"))
    monkeypatch.setattr(cli, "configure_logging", lambda _: None)

    cli.main()

    assert 'expand_all_toggle_key = "ctrl+p"' in config_file.read_text()


class _RunHarness:
    """Captures arguments passed to Agent and TerminalApp during cli.run()."""

    def __init__(self) -> None:
        self.captured: dict[str, Any] = {}

    def install(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, enable_persistence: bool = True) -> None:
        captured = self.captured
        monkeypatch.chdir(tmp_path)

        class FakeAgent:
            def __init__(self, runtime: Any, **kwargs: Any):
                captured["agent_runtime"] = runtime
                captured["agent_kwargs"] = kwargs
                self.agent_id = "main"

            async def __aenter__(self) -> "FakeAgent":
                return self

            async def __aexit__(self, *args: object) -> None:
                return None

            async def stream(self, prompt: str) -> Any:
                raise NotImplementedError

            def cancel(self) -> None:
                pass

        class FakeApp:
            def __init__(self, **kwargs: Any):
                captured["app_kwargs"] = kwargs

            async def run_async(self) -> None:
                captured["app_ran"] = True

        def fake_initialize(working_dir: Path) -> Any:
            from freeact.config import FreeactConfig

            return FreeactConfig.model_validate({"agent": {"enable_persistence": enable_persistence}})

        monkeypatch.setattr(cli, "initialize", fake_initialize)
        monkeypatch.setattr(cli, "Agent", FakeAgent)
        monkeypatch.setattr(cli, "TerminalApp", FakeApp)

    def namespace(self, **overrides: Any) -> argparse.Namespace:
        defaults: dict[str, Any] = {
            "sandbox": False,
            "sandbox_config": None,
            "session_id": None,
            "skip_permissions": False,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)


@pytest.fixture
def run_harness() -> _RunHarness:
    return _RunHarness()


@pytest.mark.asyncio
@pytest.mark.parametrize("session_id", [uuid.uuid4(), None])
async def test_run_passes_session_id_to_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_harness: _RunHarness, session_id: uuid.UUID | None
) -> None:
    run_harness.install(monkeypatch, tmp_path)

    await cli.run(run_harness.namespace(session_id=session_id))

    agent_kwargs = run_harness.captured["agent_kwargs"]
    assert agent_kwargs["session_id"] == (str(session_id) if session_id is not None else None)
    assert run_harness.captured["app_ran"] is True
    assert run_harness.captured["app_kwargs"]["skip_permissions"] is False


@pytest.mark.asyncio
async def test_run_passes_skip_permissions_to_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_harness: _RunHarness
) -> None:
    run_harness.install(monkeypatch, tmp_path)

    await cli.run(run_harness.namespace(skip_permissions=True))

    assert run_harness.captured["app_kwargs"]["skip_permissions"] is True


@pytest.mark.asyncio
async def test_run_passes_sandbox_settings_to_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_harness: _RunHarness
) -> None:
    run_harness.install(monkeypatch, tmp_path)

    await cli.run(run_harness.namespace(sandbox=True, sandbox_config=Path("/tmp/sb.json")))

    agent_kwargs = run_harness.captured["agent_kwargs"]
    assert agent_kwargs["sandbox"] is True
    assert agent_kwargs["sandbox_config"] == Path("/tmp/sb.json")


@pytest.mark.asyncio
async def test_run_rejects_session_id_when_persistence_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_harness: _RunHarness
) -> None:
    run_harness.install(monkeypatch, tmp_path, enable_persistence=False)

    with pytest.raises(SystemExit, match="--session-id requires enable_persistence"):
        await cli.run(run_harness.namespace(session_id=uuid.uuid4()))
