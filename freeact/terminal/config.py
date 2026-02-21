import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class ExpandCollapseBehavior(BaseModel):
    """Lifecycle behavior for expanding and collapsing terminal widgets."""

    model_config = ConfigDict(extra="ignore")

    collapse_thoughts_on_complete: StrictBool = True
    collapse_exec_output_on_complete: StrictBool = True
    collapse_approved_code_actions: StrictBool = True
    collapse_approved_tool_calls: StrictBool = True
    collapse_tool_outputs: StrictBool = True
    keep_rejected_actions_expanded: StrictBool = True
    pin_pending_approval_action_expanded: StrictBool = True


class TerminalKeyConfig(BaseModel):
    """Keybinding configuration for terminal UI actions."""

    model_config = ConfigDict(extra="ignore")

    toggle_expand_all: str = "ctrl+o"

    @field_validator("toggle_expand_all")
    @classmethod
    def _validate_toggle_expand_all(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("toggle_expand_all must be a non-empty string")
        return value


class TerminalUiConfig(BaseModel):
    """Top-level terminal UI settings loaded from JSON."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    expand_collapse: ExpandCollapseBehavior = Field(default_factory=ExpandCollapseBehavior, alias="expand-collapse")
    keys: TerminalKeyConfig = Field(default_factory=TerminalKeyConfig)


DEFAULT_TERMINAL_UI_CONFIG = TerminalUiConfig()
DEFAULT_TERMINAL_JSON: dict[str, Any] = DEFAULT_TERMINAL_UI_CONFIG.model_dump(by_alias=True)


class Config:
    """Loader and scaffolder for `.freeact/terminal.json`."""

    def __init__(self, freeact_dir: Path | None = None) -> None:
        self.freeact_dir = freeact_dir or (Path.cwd() / ".freeact")
        self.ui_config = load_terminal_ui_config(self.freeact_dir)

    @classmethod
    async def init(cls, freeact_dir: Path | None = None) -> None:
        """Create `.freeact/terminal.json` in the target directory when missing.

        Args:
            freeact_dir: Base `.freeact` directory. Uses `Path.cwd() / ".freeact"`
                when omitted.
        """
        target_dir = freeact_dir or (Path.cwd() / ".freeact")
        await asyncio.to_thread(ensure_terminal_ui_config, target_dir)


def load_terminal_ui_config(freeact_dir: Path) -> TerminalUiConfig:
    """Load terminal UI settings from `.freeact/terminal.json`.

    Args:
        freeact_dir: Base `.freeact` directory that may contain `terminal.json`.

    Returns:
        Parsed terminal UI settings. Returns defaults when the file is absent.
    """
    config_path = freeact_dir / "terminal.json"
    if not config_path.exists():
        return DEFAULT_TERMINAL_UI_CONFIG

    raw = json.loads(config_path.read_text())
    return TerminalUiConfig.model_validate(raw)


def ensure_terminal_ui_config(freeact_dir: Path) -> Path:
    """Ensure `.freeact/terminal.json` exists and return its path.

    Args:
        freeact_dir: Base `.freeact` directory that should contain `terminal.json`.

    Returns:
        Path to the existing or newly created `terminal.json` file.
    """
    config_path = freeact_dir / "terminal.json"
    if config_path.exists():
        return config_path

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(DEFAULT_TERMINAL_JSON, indent=2) + "\n")
    return config_path
