import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from freeact.terminal.default.config import (
    DEFAULT_TERMINAL_UI_CONFIG,
    ExpandCollapsePolicy,
    TerminalKeyConfig,
    TerminalUiConfig,
    ensure_terminal_ui_config,
    load_terminal_ui_config,
)
from freeact.terminal.default.config import (
    Config as TerminalConfig,
)


def test_load_terminal_ui_config_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()

    loaded = load_terminal_ui_config(freeact_dir)

    assert loaded == DEFAULT_TERMINAL_UI_CONFIG


def test_load_terminal_ui_config_reads_valid_file(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()
    (freeact_dir / "terminal.json").write_text(
        json.dumps(
            {
                "expand-collapse": {
                    "collapse_thoughts_on_complete": False,
                    "collapse_exec_output_on_complete": True,
                    "collapse_approved_code_actions": False,
                    "collapse_approved_tool_calls": True,
                    "collapse_tool_outputs": False,
                    "keep_rejected_actions_expanded": False,
                    "pin_pending_approval_action_expanded": True,
                },
                "keys": {
                    "toggle_expand_all": "ctrl+p",
                },
                "unknown": {"ignored": True},
            }
        )
    )

    loaded = load_terminal_ui_config(freeact_dir)

    assert loaded == TerminalUiConfig(
        expand_collapse=ExpandCollapsePolicy(
            collapse_thoughts_on_complete=False,
            collapse_exec_output_on_complete=True,
            collapse_approved_code_actions=False,
            collapse_approved_tool_calls=True,
            collapse_tool_outputs=False,
            keep_rejected_actions_expanded=False,
            pin_pending_approval_action_expanded=True,
        ),
        keys=TerminalKeyConfig(toggle_expand_all="ctrl+p"),
    )


def test_load_terminal_ui_config_raises_on_invalid_json(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()
    (freeact_dir / "terminal.json").write_text("{not-json")

    with pytest.raises(json.JSONDecodeError):
        load_terminal_ui_config(freeact_dir)


def test_load_terminal_ui_config_raises_on_type_mismatch(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()
    (freeact_dir / "terminal.json").write_text(
        json.dumps(
            {
                "expand-collapse": {
                    "collapse_tool_outputs": "yes",
                }
            }
        )
    )

    with pytest.raises(ValidationError):
        load_terminal_ui_config(freeact_dir)


def test_ensure_terminal_ui_config_creates_file_when_missing(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()

    config_path = ensure_terminal_ui_config(freeact_dir)

    assert config_path == freeact_dir / "terminal.json"
    loaded = json.loads(config_path.read_text())
    assert loaded["expand-collapse"]["collapse_tool_outputs"] is True
    assert loaded["expand-collapse"]["collapse_approved_code_actions"] is True
    assert loaded["expand-collapse"]["collapse_approved_tool_calls"] is True
    assert loaded["keys"]["toggle_expand_all"] == "ctrl+o"


def test_ensure_terminal_ui_config_preserves_existing_file(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir()
    existing = freeact_dir / "terminal.json"
    existing.write_text('{"keys": {"toggle_expand_all": "ctrl+p"}}')

    config_path = ensure_terminal_ui_config(freeact_dir)

    assert config_path == existing
    assert existing.read_text() == '{"keys": {"toggle_expand_all": "ctrl+p"}}'


@pytest.mark.asyncio
async def test_terminal_config_init_accepts_freeact_dir(tmp_path: Path) -> None:
    freeact_dir = tmp_path / "custom-freeact"

    await TerminalConfig.init(freeact_dir=freeact_dir)

    assert (freeact_dir / "terminal.json").exists()


def test_terminal_config_constructor_accepts_freeact_dir(tmp_path: Path) -> None:
    freeact_dir = tmp_path / "custom-freeact"
    freeact_dir.mkdir(parents=True)
    (freeact_dir / "terminal.json").write_text(json.dumps({"keys": {"toggle_expand_all": "ctrl+p"}}))

    config = TerminalConfig(freeact_dir=freeact_dir)

    assert config.freeact_dir == freeact_dir
    assert config.ui_config.keys.toggle_expand_all == "ctrl+p"


def test_terminal_config_defaults_to_cwd_freeact_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    config = TerminalConfig()

    assert config.freeact_dir == tmp_path / ".freeact"
