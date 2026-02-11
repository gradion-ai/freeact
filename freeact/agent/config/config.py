import copy
import json
import os
import shutil
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import yaml
from ipybox.utils import arun
from ipybox.vars import replace_variables
from pydantic_ai.models import Model, ModelSettings
from pydantic_ai.models.google import GoogleModelSettings

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_MODEL_SETTINGS = GoogleModelSettings(
    google_thinking_config={
        "thinking_level": "high",
        "include_thoughts": True,
    },
)

PYTOOLS_BASIC_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.agent.tools.pytools.search.basic"],
    "env": {
        "PYTOOLS_DIR": "${PYTOOLS_DIR}",
    },
}

PYTOOLS_HYBRID_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.agent.tools.pytools.search.hybrid"],
    "env": {
        "GEMINI_API_KEY": "${GEMINI_API_KEY}",
        "PYTOOLS_DIR": "${PYTOOLS_DIR}",
        "PYTOOLS_DB_PATH": "${PYTOOLS_DB_PATH}",
        "PYTOOLS_EMBEDDING_MODEL": "${PYTOOLS_EMBEDDING_MODEL}",
        "PYTOOLS_EMBEDDING_DIM": "${PYTOOLS_EMBEDDING_DIM}",
        "PYTOOLS_SYNC": "${PYTOOLS_SYNC}",
        "PYTOOLS_WATCH": "${PYTOOLS_WATCH}",
        "PYTOOLS_BM25_WEIGHT": "${PYTOOLS_BM25_WEIGHT}",
        "PYTOOLS_VEC_WEIGHT": "${PYTOOLS_VEC_WEIGHT}",
    },
}

_HYBRID_ENV_DEFAULTS: dict[str, str] = {
    "PYTOOLS_EMBEDDING_MODEL": "google-gla:gemini-embedding-001",
    "PYTOOLS_EMBEDDING_DIM": "3072",
    "PYTOOLS_SYNC": "true",
    "PYTOOLS_WATCH": "true",
    "PYTOOLS_BM25_WEIGHT": "1.0",
    "PYTOOLS_VEC_WEIGHT": "1.0",
}

FILESYSTEM_CONFIG: dict[str, Any] = {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
    "excluded_tools": [
        "create_directory",
        "list_directory",
        "list_directory_with_sizes",
        "directory_tree",
        "move_file",
        "search_files",
        "list_allowed_directories",
        "read_file",
    ],
}


@dataclass
class SkillMetadata:
    """Metadata parsed from a skill's SKILL.md frontmatter."""

    name: str
    description: str
    path: Path


@dataclass
class _ConfigPaths:
    """All paths derived from the working directory.

    Centralizes path construction used by both ``Config.__init__()``
    and ``Config.init()``.
    """

    working_dir: Path

    @property
    def freeact_dir(self) -> Path:
        return self.working_dir / ".freeact"

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
    def generated_rel_dir(self) -> Path:
        return self.generated_dir.relative_to(self.working_dir)

    @property
    def plans_rel_dir(self) -> Path:
        return self.plans_dir.relative_to(self.working_dir)


class Config:
    """Configuration loader for the `.freeact/` directory structure.

    Loads and parses all configuration on instantiation: skills metadata,
    system prompts, MCP servers (JSON tool calls), and PTC servers
    (programmatic tool calling).

    Internal MCP servers (pytools, filesystem) are defined as constants in
    this module. User-defined servers from `config.json` override internal
    configs when they share the same key.

    Attributes:
        working_dir: Agent's working directory.
        freeact_dir: Path to `.freeact/` configuration directory.
        model: LLM model name or instance.
        model_settings: Model-specific settings (e.g., thinking config).
        tool_search: Tool discovery mode read from `config.json`.
        images_dir: Directory for saving generated images.
        execution_timeout: Maximum time in seconds for code execution.
        approval_timeout: Timeout in seconds for PTC approval requests.
        enable_subagents: Whether to enable subagent delegation.
        max_subagents: Maximum number of concurrent subagents.
        kernel_env: Environment variables passed to the IPython kernel.
        skills_metadata: Parsed skill definitions from `.freeact/skills/*/SKILL.md`.
        system_prompt: Rendered system prompt loaded from package resources.
        mcp_servers: Merged and resolved MCP server configs.
        ptc_servers: Raw PTC server configs loaded from `config.json`.
        sessions_dir: Session trace storage directory.
    """

    def __init__(
        self,
        working_dir: Path | None = None,
        model: str | Model = DEFAULT_MODEL,
        model_settings: ModelSettings = DEFAULT_MODEL_SETTINGS,
    ):
        self._config_paths = _ConfigPaths(working_dir or Path.cwd())
        self._config_data = self._load_config_json()

        self.model = model
        self.model_settings = model_settings
        self.tool_search: str = self._config_data.get("tool-search", "basic")

        self._ensure_pytools_env_defaults()
        if self.tool_search == "hybrid":
            self._ensure_hybrid_env_defaults()

        self.images_dir: Path | None = Path(d) if (d := self._config_data.get("images-dir")) else None
        self.execution_timeout: float | None = self._config_data.get("execution-timeout", 300)
        self.approval_timeout: float | None = self._config_data.get("approval-timeout")
        self.enable_subagents: bool = self._config_data.get("enable-subagents", True)
        self.max_subagents: int = self._config_data.get("max-subagents", 5)
        self.kernel_env: dict[str, str] = self._load_kernel_env()

        self.skills_metadata = self._load_skills_metadata()
        self.mcp_servers = self._load_mcp_servers()
        self.ptc_servers = self._load_ptc_servers()
        self.system_prompt = self._load_system_prompt()

    @classmethod
    async def init(cls, working_dir: Path | None = None) -> None:
        """Scaffold `.freeact/` directory from bundled templates.

        Copies template files that don't already exist, preserving user
        modifications. Runs blocking I/O in a separate thread.

        Args:
            working_dir: Base directory. Defaults to current working directory.
        """
        paths = _ConfigPaths(working_dir or Path.cwd())
        await arun(cls._scaffold, paths)

    @staticmethod
    def _scaffold(paths: _ConfigPaths) -> None:
        skill_placeholders = {
            "generated_rel_dir": str(paths.generated_rel_dir),
            "plans_rel_dir": str(paths.plans_rel_dir),
        }

        template_files = files("freeact.agent.config").joinpath("templates")

        with as_file(template_files) as template_dir:
            skills_template_dir = template_dir / "skills"

            for template_file in template_dir.rglob("*"):
                if not template_file.is_file():
                    continue

                relative = template_file.relative_to(template_dir)
                target = paths.freeact_dir / relative

                if target.exists():
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)

                if template_file.is_relative_to(skills_template_dir):
                    content = template_file.read_text()
                    target.write_text(content.format(**skill_placeholders))
                else:
                    shutil.copy2(template_file, target)

        paths.plans_dir.mkdir(parents=True, exist_ok=True)
        paths.generated_dir.mkdir(parents=True, exist_ok=True)
        paths.sessions_dir.mkdir(parents=True, exist_ok=True)

    @property
    def working_dir(self) -> Path:
        """Agent's working directory."""
        return self._config_paths.working_dir

    @property
    def freeact_dir(self) -> Path:
        """Path to `.freeact/` configuration directory."""
        return self._config_paths.freeact_dir

    @property
    def plans_dir(self) -> Path:
        """Plan storage directory."""
        return self._config_paths.plans_dir

    @property
    def generated_dir(self) -> Path:
        """Generated MCP tool sources directory."""
        return self._config_paths.generated_dir

    @property
    def sessions_dir(self) -> Path:
        """Session trace storage directory."""
        return self._config_paths.sessions_dir

    @property
    def search_db_file(self) -> Path:
        """Hybrid search database path."""
        return self._config_paths.search_db_file

    def for_subagent(self) -> "Config":
        """Create a subagent configuration from this config.

        Returns a shallow copy with subagent-specific overrides:
        subagents disabled, mcp_servers deep-copied with pytools
        sync/watch disabled, and kernel_env shallow-copied for
        independence.
        """
        config = copy.copy(self)
        config.enable_subagents = False
        config.mcp_servers = self._subagent_mcp_servers()
        config.kernel_env = dict(self.kernel_env)
        return config

    def _subagent_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Create MCP server config copy for subagents with pytools sync/watch disabled."""
        servers = copy.deepcopy(self.mcp_servers)
        if "pytools" in servers and "env" in servers["pytools"]:
            servers["pytools"]["env"]["PYTOOLS_SYNC"] = "false"
            servers["pytools"]["env"]["PYTOOLS_WATCH"] = "false"
        return servers

    def _ensure_pytools_env_defaults(self) -> None:
        """Set path-related env var defaults for pytools (basic and hybrid).

        Sets `PYTOOLS_DIR` unconditionally (used by both basic and hybrid
        search modes) and `PYTOOLS_DB_PATH` for hybrid mode. Uses absolute
        paths derived from `self.freeact_dir`.
        """
        os.environ.setdefault("PYTOOLS_DIR", str(self.generated_dir))
        os.environ.setdefault("PYTOOLS_DB_PATH", str(self.search_db_file))

    def _ensure_hybrid_env_defaults(self) -> None:
        """Set default values in `os.environ` for hybrid-specific env vars.

        Called when `tool-search` is `"hybrid"`. Each variable uses
        `os.environ.setdefault` so user-provided values take precedence.
        `GEMINI_API_KEY` is intentionally omitted -- it has no default and
        validation will catch it if missing.
        """
        for key, default in _HYBRID_ENV_DEFAULTS.items():
            os.environ.setdefault(key, default)

    def _load_config_json(self) -> dict[str, Any]:
        """Load config.json file."""
        config_file = self.freeact_dir / "config.json"
        if not config_file.exists():
            return {}
        with open(config_file) as f:
            return json.load(f)

    def _load_kernel_env(self) -> dict[str, str]:
        """Load kernel environment variables from config.json.

        Auto-adds defaults for PYTHONPATH and HOME, then validates
        and resolves `${VAR}` placeholders against `os.environ`.
        User values in config.json take precedence over auto-defaults.
        """
        env: dict[str, str] = {}

        # Auto-defaults (lowest priority)
        env["PYTHONPATH"] = str(self.generated_dir)
        home = os.environ.get("HOME")
        if home:
            env["HOME"] = home

        # User values from config.json (highest priority)
        user_env = self._config_data.get("kernel-env", {})
        env.update(user_env)

        if not env:
            return {}

        result = replace_variables(env, os.environ)
        if result.missing_variables:
            raise ValueError(f"Missing environment variables for kernel-env: {result.missing_variables}")

        return result.replaced

    def _load_skills_metadata(self) -> list[SkillMetadata]:
        """Load skill metadata from all SKILL.md files."""
        skills_dir = self.freeact_dir / "skills"
        skills: list[SkillMetadata] = []

        if not skills_dir.exists():
            return skills

        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    if metadata := self._parse_skill_file(skill_file):
                        skills.append(metadata)

        return skills

    def _parse_skill_file(self, skill_file: Path) -> SkillMetadata | None:
        """Parse YAML frontmatter from a SKILL.md file."""
        content = skill_file.read_text()
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter = yaml.safe_load(parts[1])

        return SkillMetadata(
            name=frontmatter["name"],
            description=frontmatter["description"],
            path=skill_file,
        )

    def _render_skills_section(self) -> str:
        """Render skills as markdown list for system prompt injection."""
        if not self.skills_metadata:
            return "No skills available."

        lines = []
        for skill in self.skills_metadata:
            relative_path = skill.path.relative_to(self.working_dir)
            lines.append(f"- **{skill.name}**: {skill.description}")
            lines.append(f"  - Location: `{relative_path}`")

        return "\n".join(lines)

    def _load_system_prompt(self) -> str:
        """Load and render system prompt template from package resources."""
        prompt_files = files("freeact.agent.config").joinpath("prompts")
        with as_file(prompt_files) as prompts_dir:
            name = "system-hybrid.md" if self.tool_search == "hybrid" else "system-basic.md"
            template = (prompts_dir / name).read_text()

        return template.format(
            working_dir=self.working_dir,
            skills=self._render_skills_section(),
            generated_rel_dir=self._config_paths.generated_rel_dir,
        )

    def _internal_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Return internal MCP server configs based on tool_search mode."""
        pytools = PYTOOLS_HYBRID_CONFIG if self.tool_search == "hybrid" else PYTOOLS_BASIC_CONFIG
        return {"pytools": pytools, "filesystem": FILESYSTEM_CONFIG}

    def _load_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Load MCP servers: internal defaults merged with user overrides.

        User-defined servers from `config.json` take precedence over
        internal configs for the same key. All ``${VAR}`` placeholders
        are validated and resolved against ``os.environ``.
        """
        internal = self._internal_mcp_servers()
        user = self._config_data.get("mcp-servers", {})
        merged = {**internal, **user}

        if not merged:
            return {}

        result = replace_variables(merged, os.environ)
        if result.missing_variables:
            raise ValueError(f"Missing environment variables for mcp-servers: {result.missing_variables}")

        return result.replaced

    def _load_ptc_servers(self) -> dict[str, dict[str, Any]]:
        """Load PTC server configs, validating env vars but keeping placeholders."""
        config = self._config_data.get("ptc-servers", {})
        if not config:
            return {}

        result = replace_variables(config, os.environ)
        if result.missing_variables:
            raise ValueError(f"Missing environment variables for ptc-servers: {result.missing_variables}")

        return config
