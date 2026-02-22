import json
from pathlib import Path

from ipybox.utils import arun
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

FREEACT_DIR_NAME = ".freeact"


class ExpandCollapseBehavior(BaseModel):
    """Lifecycle behavior for expanding and collapsing terminal widgets."""

    model_config = ConfigDict(extra="forbid")

    collapse_thoughts_on_complete: StrictBool = True
    collapse_exec_output_on_complete: StrictBool = True
    collapse_approved_code_actions: StrictBool = True
    collapse_approved_tool_calls: StrictBool = True
    collapse_tool_outputs: StrictBool = True
    keep_rejected_actions_expanded: StrictBool = True
    pin_pending_approval_action_expanded: StrictBool = True


class TerminalKeyConfig(BaseModel):
    """Keybinding configuration for terminal UI actions."""

    model_config = ConfigDict(extra="forbid")

    toggle_expand_all: str = "ctrl+o"

    @field_validator("toggle_expand_all")
    @classmethod
    def _validate_toggle_expand_all(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("toggle_expand_all must be a non-empty string")
        return value


class TerminalUiConfig(BaseModel):
    """Top-level terminal UI settings loaded from JSON."""

    model_config = ConfigDict(extra="forbid")

    expand_collapse: ExpandCollapseBehavior = Field(default_factory=ExpandCollapseBehavior)
    keys: TerminalKeyConfig = Field(default_factory=TerminalKeyConfig)


DEFAULT_TERMINAL_UI_CONFIG = TerminalUiConfig()


class Config(BaseModel):
    """Terminal config."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, frozen=True)

    working_dir: Path = Field(default_factory=Path.cwd, exclude=True)

    expand_collapse: ExpandCollapseBehavior = Field(default_factory=ExpandCollapseBehavior)
    keys: TerminalKeyConfig = Field(default_factory=TerminalKeyConfig)

    def model_post_init(self, __context: object) -> None:
        object.__setattr__(self, "working_dir", self.working_dir.resolve())

    @property
    def freeact_dir(self) -> Path:
        return self.working_dir / FREEACT_DIR_NAME

    @property
    def ui_config(self) -> TerminalUiConfig:
        return TerminalUiConfig(
            expand_collapse=self.expand_collapse,
            keys=self.keys,
        )

    async def save(self) -> None:
        """Persist terminal config to `.freeact/terminal.json`."""
        await arun(self._save_sync)

    @classmethod
    async def load(cls, working_dir: Path | None = None) -> "Config":
        """Load persisted terminal config or return defaults when missing."""
        config = cls(working_dir=working_dir or Path.cwd())
        config_path = config.freeact_dir / "terminal.json"
        if not config_path.exists():
            return config

        data = await arun(lambda: json.loads(config_path.read_text()))
        ui_config = TerminalUiConfig.model_validate(data)
        return cls(
            working_dir=config.working_dir,
            expand_collapse=ui_config.expand_collapse,
            keys=ui_config.keys,
        )

    @classmethod
    async def init(cls, working_dir: Path | None = None) -> "Config":
        """Load terminal config when present, otherwise save defaults."""
        config = cls(working_dir=working_dir or Path.cwd())
        config_path = config.freeact_dir / "terminal.json"
        if config_path.exists():
            return await cls.load(working_dir=config.working_dir)

        await config.save()
        return config

    def _save_sync(self) -> None:
        config_path = self.freeact_dir / "terminal.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.ui_config.model_dump(mode="json")
        config_path.write_text(json.dumps(payload, indent=2) + "\n")
