import copy
import json
import os
from pathlib import Path
from typing import Any, Literal

from ipybox.utils import arun
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic_ai.models import Model

from .prompts import load_system_prompt
from .runtime import (
    resolve_kernel_env,
    resolve_mcp_servers,
    resolve_model_instance,
    validate_ptc_servers,
)
from .skills import SkillMetadata, load_skills_metadata, materialize_bundled_skills

FREEACT_DIR_NAME = ".freeact"

DEFAULT_MODEL_NAME = "google-gla:gemini-3-flash-preview"
DEFAULT_MODEL_SETTINGS: dict[str, Any] = {
    "google_thinking_config": {
        "thinking_level": "high",
        "include_thoughts": True,
    }
}

FILESYSTEM_MCP_SERVER_CONFIG: dict[str, Any] = {
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

BASIC_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.search.basic"],
    "env": {
        "PYTOOLS_DIR": "${PYTOOLS_DIR}",
    },
}

HYBRID_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.search.hybrid"],
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

HYBRID_SEARCH_ENV_DEFAULTS: dict[str, str] = {
    "PYTOOLS_EMBEDDING_MODEL": "google-gla:gemini-embedding-001",
    "PYTOOLS_EMBEDDING_DIM": "3072",
    "PYTOOLS_SYNC": "true",
    "PYTOOLS_WATCH": "true",
    "PYTOOLS_BM25_WEIGHT": "1.0",
    "PYTOOLS_VEC_WEIGHT": "1.0",
}

GOOGLE_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.gsearch", "--thinking-level", "medium"],
    "env": {"GEMINI_API_KEY": "${GEMINI_API_KEY}"},
}


class Config(BaseModel):
    """Agent configuration."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", validate_assignment=True, frozen=True)
    working_dir: Path = Field(default_factory=Path.cwd, exclude=True)

    model: str | Model = DEFAULT_MODEL_NAME
    model_settings: dict[str, Any] = Field(default_factory=lambda: copy.deepcopy(DEFAULT_MODEL_SETTINGS))
    provider_settings: dict[str, Any] | None = None
    tool_search: Literal["basic", "hybrid"] = "basic"

    images_dir: Path | None = None
    execution_timeout: float | None = 300
    approval_timeout: float | None = None
    tool_result_inline_max_bytes: int = Field(default=32768, ge=1)
    tool_result_preview_lines: int = Field(default=10, ge=1)
    enable_subagents: bool = True
    max_subagents: int = 5
    kernel_env: dict[str, str] = Field(default_factory=dict)

    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    ptc_servers: dict[str, dict[str, Any]] = Field(
        default_factory=lambda: {
            "google": copy.deepcopy(GOOGLE_SEARCH_MCP_SERVER_CONFIG),
        }
    )

    _resolved_model_instance: str | Model = PrivateAttr(default="")
    _resolved_mcp_servers: dict[str, dict[str, Any]] = PrivateAttr(default_factory=dict)
    _resolved_kernel_env: dict[str, str] = PrivateAttr(default_factory=dict)
    _subagent_mode: bool = PrivateAttr(default=False)

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "working_dir", self.working_dir.resolve())
        resolution_env = self._resolution_env()
        object.__setattr__(
            self,
            "_resolved_model_instance",
            resolve_model_instance(
                model=self.model,
                provider_settings=self.provider_settings,
                resolution_env=resolution_env,
            ),
        )
        object.__setattr__(
            self,
            "_resolved_mcp_servers",
            resolve_mcp_servers(
                tool_search=self.tool_search,
                mcp_servers=self.mcp_servers,
                basic_search_mcp_server_config=BASIC_SEARCH_MCP_SERVER_CONFIG,
                hybrid_search_mcp_server_config=HYBRID_SEARCH_MCP_SERVER_CONFIG,
                filesystem_mcp_server_config=FILESYSTEM_MCP_SERVER_CONFIG,
                resolution_env=resolution_env,
            ),
        )
        object.__setattr__(
            self,
            "_resolved_kernel_env",
            resolve_kernel_env(
                kernel_env=self.kernel_env,
                generated_dir=self.generated_dir,
                resolution_env=resolution_env,
            ),
        )
        validate_ptc_servers(
            ptc_servers=self.ptc_servers,
            resolution_env=resolution_env,
        )

    async def save(self) -> None:
        """Persist config and scaffold static directories and bundled skills."""
        await arun(self._save_sync)

    @classmethod
    async def load(cls, working_dir: Path | None = None) -> "Config":
        """Load persisted config if present, otherwise return defaults."""
        config = cls(working_dir=working_dir or Path.cwd())
        config_file = config.freeact_dir / "agent.json"
        if not config_file.exists():
            return config

        data = await arun(lambda: json.loads(config_file.read_text()))
        return cls.model_validate(
            {
                **data,
                "working_dir": config.working_dir,
            }
        )

    @classmethod
    async def init(cls, working_dir: Path | None = None) -> "Config":
        """Load config from `.freeact/` when present, otherwise save defaults."""
        config = cls(working_dir=working_dir or Path.cwd())
        if config.freeact_dir.exists():
            return await cls.load(working_dir=config.working_dir)

        await config.save()
        return config

    @property
    def freeact_dir(self) -> Path:
        return self.working_dir / FREEACT_DIR_NAME

    @property
    def skills_dir(self) -> Path:
        return self.freeact_dir / "skills"

    @property
    def project_instructions_file(self) -> Path:
        return self.working_dir / "AGENTS.md"

    @property
    def project_skills_dir(self) -> Path:
        return self.working_dir / ".agents" / "skills"

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
        return self._relative_to_working_dir(self.generated_dir)

    @property
    def plans_rel_dir(self) -> Path:
        return self._relative_to_working_dir(self.plans_dir)

    @property
    def model_instance(self) -> str | Model:
        return self._resolved_model_instance

    @property
    def resolved_kernel_env(self) -> dict[str, str]:
        return dict(self._resolved_kernel_env)

    @property
    def resolved_mcp_servers(self) -> dict[str, dict[str, Any]]:
        servers = copy.deepcopy(self._resolved_mcp_servers)
        if self._subagent_mode and "pytools" in servers and "env" in servers["pytools"]:
            servers["pytools"]["env"]["PYTOOLS_SYNC"] = "false"
            servers["pytools"]["env"]["PYTOOLS_WATCH"] = "false"
        return servers

    @property
    def skills_metadata(self) -> list[SkillMetadata]:
        return load_skills_metadata(
            skills_dir=self.skills_dir,
            project_skills_dir=self.project_skills_dir,
        )

    @property
    def system_prompt(self) -> str:
        return load_system_prompt(
            tool_search=self.tool_search,
            working_dir=self.working_dir,
            generated_rel_dir=self.generated_rel_dir,
            project_instructions_file=self.project_instructions_file,
            skills_metadata=self.skills_metadata,
        )

    def for_subagent(self) -> "Config":
        config = self.model_copy(update={"enable_subagents": False}, deep=True)
        object.__setattr__(config, "_subagent_mode", True)
        return config

    def _save_sync(self) -> None:
        if not isinstance(self.model, str):
            raise ValueError("model must be a string when saving config")

        self.freeact_dir.mkdir(parents=True, exist_ok=True)

        payload = self.model_dump(mode="json", exclude={"working_dir"})
        config_file = self.freeact_dir / "agent.json"
        config_file.write_text(json.dumps(payload, indent=2) + "\n")

        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        materialize_bundled_skills(
            skills_dir=self.skills_dir,
            generated_rel_dir=self.generated_rel_dir,
            plans_rel_dir=self.plans_rel_dir,
        )

    def _resolution_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.setdefault("PYTOOLS_DIR", str(self.generated_rel_dir))
        env.setdefault("PYTOOLS_DB_PATH", str(self.search_db_file))
        if self.tool_search == "hybrid":
            for key, default in HYBRID_SEARCH_ENV_DEFAULTS.items():
                env.setdefault(key, default)
        return env

    def _relative_to_working_dir(self, path: Path) -> Path:
        try:
            return path.relative_to(self.working_dir)
        except ValueError:
            return path
