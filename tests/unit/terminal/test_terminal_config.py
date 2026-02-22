import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from freeact.terminal.config import (
    Config as TerminalConfig,
)


@pytest.mark.asyncio
async def test_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    config = await TerminalConfig.load(working_dir=tmp_path)

    assert config.freeact_dir == tmp_path / ".freeact"
    assert config.collapse_tool_outputs is True
    assert config.expand_all_toggle_key == "ctrl+o"


@pytest.mark.asyncio
async def test_init_saves_defaults_when_file_missing(tmp_path: Path) -> None:
    config = await TerminalConfig.init(working_dir=tmp_path)

    config_path = tmp_path / ".freeact" / "terminal.json"
    assert config_path.exists()
    loaded = json.loads(config_path.read_text())
    assert loaded["expand_all_toggle_key"] == "ctrl+o"
    assert config.collapse_tool_outputs is True
    assert config.expand_all_toggle_key == "ctrl+o"


@pytest.mark.asyncio
async def test_load_reads_valid_file(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    (freeact_dir / "terminal.json").write_text(
        json.dumps(
            {
                "collapse_thoughts_on_complete": False,
                "collapse_exec_output_on_complete": True,
                "collapse_approved_code_actions": False,
                "collapse_approved_tool_calls": True,
                "collapse_tool_outputs": False,
                "keep_rejected_actions_expanded": False,
                "pin_pending_approval_action_expanded": True,
                "expand_all_toggle_key": "ctrl+p",
            }
        )
    )

    config = await TerminalConfig.load(working_dir=tmp_path)

    assert config.collapse_thoughts_on_complete is False
    assert config.collapse_exec_output_on_complete is True
    assert config.collapse_approved_code_actions is False
    assert config.collapse_approved_tool_calls is True
    assert config.collapse_tool_outputs is False
    assert config.keep_rejected_actions_expanded is False
    assert config.pin_pending_approval_action_expanded is True
    assert config.expand_all_toggle_key == "ctrl+p"


@pytest.mark.asyncio
async def test_init_loads_existing_file_without_overwrite(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    config_path = freeact_dir / "terminal.json"
    config_path.write_text(json.dumps({"expand_all_toggle_key": "ctrl+p"}))

    config = await TerminalConfig.init(working_dir=tmp_path)

    assert config.expand_all_toggle_key == "ctrl+p"
    persisted = json.loads(config_path.read_text())
    assert persisted["expand_all_toggle_key"] == "ctrl+p"


@pytest.mark.asyncio
async def test_load_rejects_kebab_case_schema(tmp_path: Path) -> None:
    freeact_dir = tmp_path / ".freeact"
    freeact_dir.mkdir(parents=True)
    (freeact_dir / "terminal.json").write_text(
        json.dumps(
            {
                "expand-collapse": {
                    "collapse_tool_outputs": False,
                }
            }
        )
    )

    with pytest.raises(ValidationError):
        await TerminalConfig.load(working_dir=tmp_path)


@pytest.mark.asyncio
async def test_save_creates_file_when_missing(tmp_path: Path) -> None:
    config = TerminalConfig(working_dir=tmp_path)

    await config.save()

    config_path = tmp_path / ".freeact" / "terminal.json"
    assert config_path.exists()
    loaded = json.loads(config_path.read_text())
    assert loaded["collapse_tool_outputs"] is True
    assert loaded["collapse_approved_code_actions"] is True
    assert loaded["collapse_approved_tool_calls"] is True
    assert loaded["expand_all_toggle_key"] == "ctrl+o"


@pytest.mark.asyncio
async def test_save_updates_existing_file(tmp_path: Path) -> None:
    config = TerminalConfig(
        working_dir=tmp_path,
        expand_all_toggle_key="ctrl+p",
    )

    await config.save()

    loaded = json.loads((tmp_path / ".freeact" / "terminal.json").read_text())
    assert loaded["expand_all_toggle_key"] == "ctrl+p"


@pytest.mark.asyncio
async def test_terminal_config_freeact_dir_is_derived_from_working_dir(tmp_path: Path) -> None:
    config = TerminalConfig(working_dir=tmp_path)
    await config.save()

    assert (tmp_path / ".freeact" / "terminal.json").exists()


def test_expand_all_toggle_key_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        TerminalConfig(expand_all_toggle_key="")


def test_terminal_config_is_immutable(tmp_path: Path) -> None:
    config = TerminalConfig(working_dir=tmp_path)

    with pytest.raises(ValidationError):
        setattr(config, "expand_all_toggle_key", "ctrl+p")
