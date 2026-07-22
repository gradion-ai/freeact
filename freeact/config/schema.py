import copy
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MODEL_NAME = "google-gla:gemini-3.6-flash"
DEFAULT_MODEL_SETTINGS: dict[str, Any] = {
    "google_thinking_config": {
        "thinking_level": "medium",
        "include_thoughts": True,
    }
}


class ToolPresets(BaseModel):
    """One-line opt-ins for bundled tool servers (`[agent.tools]`).

    Minimal defaults: everything is off except the built-ins code actions
    require (code execution and filesystem, which are always on).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    search: bool = False
    """Google search via Gemini grounding (code mode). Needs `GEMINI_API_KEY`."""

    fetch: bool = False
    """Web fetch (code mode)."""

    discovery: Literal["basic", "hybrid", "off"] = "basic"
    """Tool discovery mode. `"hybrid"` needs the `freeact[search]` extra.

    Defaults to `"basic"`: without a discovery server the agent cannot
    enumerate its generated tool APIs and falls back to ad-hoc code.
    """


class AgentSection(BaseModel):
    """Agent configuration (`[agent]`). Pure data; resolution is separate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = DEFAULT_MODEL_NAME
    model_settings: dict[str, Any] = Field(default_factory=lambda: copy.deepcopy(DEFAULT_MODEL_SETTINGS))
    provider_settings: dict[str, Any] | None = None
    tools: ToolPresets = Field(default_factory=ToolPresets)

    execution_timeout: float = Field(default=300, ge=0)
    """Code execution timeout in seconds; `0` disables the timeout."""

    approval_timeout: float = Field(default=0, ge=0)
    """Approval wait timeout in seconds; `0` waits forever."""

    tool_result_inline_max_bytes: int = Field(default=32768, ge=1)
    tool_result_preview_chars: int = Field(default=2048, ge=1)
    enable_persistence: bool = True
    enable_subagents: bool = True
    max_subagents: int = Field(default=5, ge=1)
    images_dir: Path | None = None
    kernel_env: dict[str, str] = Field(default_factory=dict)

    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    """User-defined MCP servers for JSON tool calling."""

    ptc_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    """User-defined MCP servers for programmatic tool calling (code mode)."""


class TerminalSection(BaseModel):
    """Terminal UI configuration (`[terminal]`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    collapse_thoughts_on_complete: bool = True
    collapse_exec_output_on_complete: bool = True
    collapse_approved_code_actions: bool = False
    collapse_approved_tool_calls: bool = True
    collapse_completed_subagent_tasks: bool = True
    collapse_tool_outputs: bool = True
    keep_rejected_actions_expanded: bool = True
    pin_pending_approval_action_expanded: bool = True
    expand_all_toggle_key: str = Field(default="ctrl+o", min_length=1)


class FreeactConfig(BaseModel):
    """Root configuration model mirroring `.freeact/config.toml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent: AgentSection = Field(default_factory=AgentSection)
    terminal: TerminalSection = Field(default_factory=TerminalSection)
