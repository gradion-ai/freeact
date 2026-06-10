from dataclasses import dataclass
from pathlib import Path

import tomllib

from freeact.config.schema import FreeactConfig
from freeact.config.skills import materialize_bundled_skills

FREEACT_DIR_NAME = ".freeact"
CONFIG_FILENAME = "config.toml"

DEFAULT_CONFIG_TOML = """\
# freeact configuration. Created by `freeact init`; freeact never rewrites
# this file, so comments and formatting are yours to keep.

[agent]
model = "google-gla:gemini-3.5-flash"
# execution_timeout = 300.0     # seconds; 0 disables the timeout
# approval_timeout = 0.0        # seconds; 0 waits forever
# enable_persistence = true
# enable_subagents = true
# max_subagents = 5
# images_dir = "images"
# tool_result_inline_max_bytes = 32768
# tool_result_preview_chars = 2048

[agent.model_settings]
google_thinking_config = { thinking_level = "medium", include_thoughts = true }

# Provider options (api_key, base_url, ...). `${VAR}` reads environment variables.
# [agent.provider_settings]
# api_key = "${MY_PROVIDER_KEY}"

[agent.tools]
# One-line opt-ins for bundled tool servers. Code execution and filesystem
# tools are always available.
# search = true            # google search (code mode); needs GEMINI_API_KEY
# fetch = true             # web fetch (code mode)
# discovery = "basic"      # or "hybrid" (needs freeact[search]); omit for none

# Environment variables for the IPython kernel. `${VAR}` reads host env vars.
# [agent.kernel_env]
# MY_VAR = "${MY_VAR}"

# Custom MCP servers for JSON tool calling:
# [agent.mcp_servers.github]
# command = "docker"
# args = ["run", "-i", "--rm", "-e", "GITHUB_TOKEN", "ghcr.io/github/github-mcp-server"]
# env = { GITHUB_TOKEN = "${GITHUB_TOKEN}" }
# exclude_tools = []

# Custom MCP servers for programmatic tool calling (generated Python APIs):
# [agent.ptc_servers.github]
# command = "..."
# args = []

[terminal]
# collapse_thoughts_on_complete = true
# collapse_exec_output_on_complete = true
# collapse_approved_code_actions = false
# collapse_approved_tool_calls = true
# collapse_completed_subagent_tasks = true
# collapse_tool_outputs = true
# keep_rejected_actions_expanded = true
# pin_pending_approval_action_expanded = true
# expand_all_toggle_key = "ctrl+o"
"""


@dataclass(frozen=True)
class Workspace:
    """Filesystem layout of a freeact workspace."""

    working_dir: Path

    @property
    def freeact_dir(self) -> Path:
        return self.working_dir / FREEACT_DIR_NAME

    @property
    def config_file(self) -> Path:
        return self.freeact_dir / CONFIG_FILENAME

    @property
    def skills_dir(self) -> Path:
        return self.freeact_dir / "skills"

    @property
    def plans_dir(self) -> Path:
        return self.freeact_dir / "plans"

    @property
    def generated_dir(self) -> Path:
        return self.freeact_dir / "generated"

    @property
    def sessions_dir(self) -> Path:
        return self.freeact_dir / "sessions"

    @property
    def search_db_file(self) -> Path:
        return self.freeact_dir / "search.db"

    @property
    def project_instructions_file(self) -> Path:
        return self.working_dir / "AGENTS.md"

    @property
    def project_skills_dir(self) -> Path:
        return self.working_dir / ".agents" / "skills"

    @property
    def generated_rel_dir(self) -> Path:
        return self.relative_to_working_dir(self.generated_dir)

    @property
    def plans_rel_dir(self) -> Path:
        return self.relative_to_working_dir(self.plans_dir)

    def images_dir(self, configured: Path | None) -> Path:
        if configured is None:
            return self.working_dir / "images"
        if configured.is_absolute():
            return configured
        return self.working_dir / configured

    def relative_to_working_dir(self, path: Path) -> Path:
        try:
            return path.relative_to(self.working_dir)
        except ValueError:
            return path


def workspace(working_dir: Path | None = None) -> Workspace:
    """Create a [`Workspace`][freeact.config.Workspace] for a working directory.

    Args:
        working_dir: Workspace root; defaults to the current directory.

    Returns:
        Workspace with resolved root path.
    """
    return Workspace(working_dir=(working_dir or Path.cwd()).resolve())


def load(working_dir: Path | None = None) -> FreeactConfig:
    """Load `.freeact/config.toml`, returning defaults when missing.

    Args:
        working_dir: Workspace root; defaults to the current directory.

    Returns:
        Parsed configuration (pure data, nothing resolved).
    """
    ws = workspace(working_dir)
    if not ws.config_file.exists():
        return FreeactConfig()

    data = tomllib.loads(ws.config_file.read_text())
    return FreeactConfig.model_validate(data)


def init(working_dir: Path | None = None) -> FreeactConfig:
    """Initialize a workspace: write default config if missing, create runtime dirs.

    Writes the commented default `config.toml` when none exists (never
    overwrites), creates the runtime directories, and materializes bundled
    skills without overwriting user-modified ones.

    Args:
        working_dir: Workspace root; defaults to the current directory.

    Returns:
        The effective configuration after initialization.
    """
    ws = workspace(working_dir)

    ws.freeact_dir.mkdir(parents=True, exist_ok=True)
    if not ws.config_file.exists():
        ws.config_file.write_text(DEFAULT_CONFIG_TOML)

    ws.generated_dir.mkdir(parents=True, exist_ok=True)
    ws.plans_dir.mkdir(parents=True, exist_ok=True)
    ws.sessions_dir.mkdir(parents=True, exist_ok=True)

    materialize_bundled_skills(
        skills_dir=ws.skills_dir,
        generated_rel_dir=ws.generated_rel_dir,
        plans_rel_dir=ws.plans_rel_dir,
    )

    return load(ws.working_dir)
