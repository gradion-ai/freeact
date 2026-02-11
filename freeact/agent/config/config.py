import json
import os
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

import yaml
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
        skills_metadata: Parsed skill definitions from `.freeact/skills/*/SKILL.md`.
        system_prompt: Rendered system prompt loaded from package resources.
        mcp_servers: Merged MCP server configs (internal defaults + user overrides).
        ptc_servers: Raw PTC server configs loaded from `config.json`.
    """

    def __init__(
        self,
        working_dir: Path | None = None,
        model: str | Model = DEFAULT_MODEL,
        model_settings: ModelSettings = DEFAULT_MODEL_SETTINGS,
    ):
        self.working_dir = working_dir or Path.cwd()
        self.freeact_dir = self.working_dir / ".freeact"

        self.model = model
        self.model_settings = model_settings

        self._config_data = self._load_config_json()
        self.tool_search: str = self._config_data.get("tool-search", "basic")

        self._ensure_pytools_env_defaults()
        if self.tool_search == "hybrid":
            self._ensure_hybrid_env_defaults()

        self.skills_metadata = self._load_skills_metadata()
        self.mcp_servers = self._load_mcp_servers()
        self.ptc_servers = self._load_servers("ptc-servers")
        self.system_prompt = self._load_system_prompt()

    @property
    def plans_dir(self) -> Path:
        """Plan storage directory."""
        return self.freeact_dir / "plans"

    @property
    def generated_dir(self) -> Path:
        """Generated MCP tool sources directory."""
        return self.freeact_dir / "generated"

    @property
    def search_db_path(self) -> Path:
        """Hybrid search database path."""
        return self.freeact_dir / "search.db"

    def _ensure_pytools_env_defaults(self) -> None:
        """Set path-related env var defaults for pytools (basic and hybrid).

        Sets `PYTOOLS_DIR` unconditionally (used by both basic and hybrid
        search modes) and `PYTOOLS_DB_PATH` for hybrid mode. Uses absolute
        paths derived from `self.freeact_dir`.
        """
        os.environ.setdefault("PYTOOLS_DIR", str(self.generated_dir))
        os.environ.setdefault("PYTOOLS_DB_PATH", str(self.search_db_path))

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
            generated_rel_dir=self.generated_dir.relative_to(self.working_dir),
        )

    def _internal_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Return internal MCP server configs based on tool_search mode."""
        pytools = PYTOOLS_HYBRID_CONFIG if self.tool_search == "hybrid" else PYTOOLS_BASIC_CONFIG
        return {"pytools": pytools, "filesystem": FILESYSTEM_CONFIG}

    def _load_mcp_servers(self) -> dict[str, dict[str, Any]]:
        """Load MCP servers: internal defaults merged with user overrides.

        User-defined servers from `config.json` take precedence over
        internal configs for the same key.
        """
        internal = self._internal_mcp_servers()
        user = self._load_servers("mcp-servers")
        return {**internal, **user}

    def _load_servers(self, key: str) -> dict[str, dict[str, Any]]:
        """Load server configs, validating env vars but keeping placeholders."""
        config = self._config_data.get(key, {})
        if not config:
            return {}

        result = replace_variables(config, os.environ)
        if result.missing_variables:
            raise ValueError(f"Missing environment variables for {key}: {result.missing_variables}")

        return config
