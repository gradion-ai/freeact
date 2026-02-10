import json
import os
from dataclasses import dataclass
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

    Attributes:
        working_dir: Agent's working directory.
        freeact_dir: Path to `.freeact/` configuration directory.
        plans_dir: Path to `.freeact/plans/` for plan storage.
        model: LLM model name or instance.
        model_settings: Model-specific settings (e.g., thinking config).
        skills_metadata: Parsed skill definitions from `.freeact/skills/*/SKILL.md`.
        system_prompt: Rendered system prompt from `.freeact/prompts/system.md`.
        mcp_servers: Raw MCP server configs loaded from `servers.json`.
        ptc_servers: Raw PTC server configs loaded from `servers.json`..
    """

    def __init__(
        self,
        working_dir: Path | None = None,
        model: str | Model = DEFAULT_MODEL,
        model_settings: ModelSettings = DEFAULT_MODEL_SETTINGS,
    ):
        self.working_dir = working_dir or Path.cwd()
        self.freeact_dir = self.working_dir / ".freeact"
        self.plans_dir = self.freeact_dir / "plans"

        self.model = model
        self.model_settings = model_settings

        # Load all data
        self.skills_metadata = self._load_skills_metadata()
        self.mcp_servers = self._load_servers("mcp-servers")
        self.ptc_servers = self._load_servers("ptc-servers")
        self.system_prompt = self._load_system_prompt()

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

    def _is_hybrid_search_enabled(self) -> bool:
        """Check if pytools server uses hybrid search module."""
        pytools_config = self.mcp_servers.get("pytools", {})
        return "freeact.agent.tools.pytools.search.hybrid" in pytools_config.get("args", [])

    def _load_system_prompt(self) -> str:
        """Load and render system prompt template."""
        if self._is_hybrid_search_enabled():
            prompt_file = self.freeact_dir / "prompts" / "system-hybrid.md"
        else:
            prompt_file = self.freeact_dir / "prompts" / "system-basic.md"

        template = prompt_file.read_text()

        return template.format(
            working_dir=self.working_dir,
            skills=self._render_skills_section(),
        )

    def _load_servers(self, key: str) -> dict[str, dict[str, Any]]:
        """Load server configs, validating env vars but keeping placeholders."""
        raw_config = self._load_servers_json()
        config = raw_config.get(key, {})
        if not config:
            return {}

        result = replace_variables(config, os.environ)
        if result.missing_variables:
            raise ValueError(f"Missing environment variables for {key}: {result.missing_variables}")

        return config

    def _load_servers_json(self) -> dict[str, Any]:
        """Load servers.json file."""
        config_file = self.freeact_dir / "servers.json"
        if not config_file.exists():
            return {}
        with open(config_file) as f:
            return json.load(f)
