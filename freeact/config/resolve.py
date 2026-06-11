import copy
import importlib.util
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from mcpygen.vars import replace_variables
from pydantic_ai.models import Model, infer_model
from pydantic_ai.providers import Provider, infer_provider_class

from freeact.config.load import Workspace, workspace
from freeact.config.prompts import load_system_prompt
from freeact.config.schema import AgentSection, FreeactConfig
from freeact.config.skills import SkillMetadata, load_skills_metadata

FILESYSTEM_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.filesystem"],
}

BASIC_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.basic"],
    "env": {
        "PYTOOLS_DIR": "${PYTOOLS_DIR}",
    },
}

HYBRID_SEARCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.pytools.hybrid"],
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

FETCH_MCP_SERVER_CONFIG: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.tools.fetch"],
    "env": {},
}

_HYBRID_EXTRA_MODULES = ("sqlite_vec", "watchfiles")


@dataclass(frozen=True)
class ResolvedRuntime:
    """Everything the agent needs at runtime, resolved from config + environment.

    Produced by [`resolve()`][freeact.config.resolve]. Unlike
    [`FreeactConfig`][freeact.config.FreeactConfig], values here are concrete:
    `${VAR}` references substituted, presets expanded into server configs,
    and the model ready for pydantic-ai.
    """

    config: AgentSection
    workspace: Workspace
    model: str | Model
    mcp_servers: dict[str, dict[str, Any]]
    ptc_servers: dict[str, dict[str, Any]]
    kernel_env: dict[str, str]
    enable_subagents: bool
    subagent_mode: bool = False

    @property
    def working_dir(self) -> Path:
        return self.workspace.working_dir

    @property
    def model_settings(self) -> dict[str, Any]:
        return self.config.model_settings

    @property
    def execution_timeout(self) -> float | None:
        return self.config.execution_timeout or None

    @property
    def approval_timeout(self) -> float | None:
        return self.config.approval_timeout or None

    @property
    def images_dir(self) -> Path:
        return self.workspace.images_dir(self.config.images_dir)

    @property
    def skills_metadata(self) -> list[SkillMetadata]:
        return load_skills_metadata(
            skills_dir=self.workspace.skills_dir,
            project_skills_dir=self.workspace.project_skills_dir,
        )

    @property
    def system_prompt(self) -> str:
        return load_system_prompt(
            working_dir=self.workspace.working_dir,
            generated_rel_dir=self.workspace.generated_rel_dir,
            project_instructions_file=self.workspace.project_instructions_file,
            skills_metadata=self.skills_metadata,
        )

    def for_subagent(self) -> "ResolvedRuntime":
        """Derive the runtime for a subagent.

        Subagents cannot nest, and in hybrid discovery mode they neither
        sync nor watch the shared search index.
        """
        mcp_servers = copy.deepcopy(self.mcp_servers)
        if "pytools" in mcp_servers and "env" in mcp_servers["pytools"]:
            env = mcp_servers["pytools"]["env"]
            if "PYTOOLS_SYNC" in env:
                env["PYTOOLS_SYNC"] = "false"
            if "PYTOOLS_WATCH" in env:
                env["PYTOOLS_WATCH"] = "false"
        return replace(
            self,
            mcp_servers=mcp_servers,
            kernel_env=dict(self.kernel_env),
            enable_subagents=False,
            subagent_mode=True,
        )


def resolve(
    config: FreeactConfig,
    working_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ResolvedRuntime:
    """Resolve a parsed config against the environment into runtime values.

    Expands tool presets into server configs, substitutes `${VAR}` references
    (missing variables raise `ValueError` naming the variable), instantiates
    the model when provider settings are present, and computes the kernel
    environment.

    Args:
        config: Parsed configuration.
        working_dir: Workspace root; defaults to the current directory.
        env: Environment for `${VAR}` substitution; defaults to `os.environ`.

    Returns:
        Resolved runtime values.
    """
    ws = workspace(working_dir)
    agent = config.agent
    resolution_env = _resolution_env(agent, ws, env if env is not None else os.environ)

    if agent.tools.discovery == "hybrid":
        _require_hybrid_extra()

    return ResolvedRuntime(
        config=agent,
        workspace=ws,
        model=_resolve_model(agent, resolution_env),
        mcp_servers=_resolve_mcp_servers(agent, resolution_env),
        ptc_servers=_validated_ptc_servers(agent, resolution_env),
        kernel_env=_resolve_kernel_env(agent, ws, resolution_env),
        enable_subagents=agent.enable_subagents,
    )


def _resolution_env(agent: AgentSection, ws: Workspace, env: Mapping[str, str]) -> dict[str, str]:
    resolution_env = dict(env)
    resolution_env.setdefault("PYTOOLS_DIR", str(ws.generated_rel_dir))
    resolution_env.setdefault("PYTOOLS_DB_PATH", str(ws.search_db_file))
    if agent.tools.discovery == "hybrid":
        for key, default in HYBRID_SEARCH_ENV_DEFAULTS.items():
            resolution_env.setdefault(key, default)
    return resolution_env


def _resolve_model(agent: AgentSection, resolution_env: Mapping[str, str]) -> str | Model:
    if agent.provider_settings is None:
        return agent.model

    result = replace_variables(agent.provider_settings, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for provider_settings: {result.missing_variables}")

    resolved = result.replaced

    def provider_factory(name: str) -> Provider[Any]:
        kwargs = dict(resolved)
        if name in ("google-vertex", "google-gla"):
            kwargs.setdefault("vertexai", name == "google-vertex")
        provider_class = infer_provider_class(name)
        return provider_class(**kwargs)

    return infer_model(agent.model, provider_factory=provider_factory)


def _resolve_mcp_servers(agent: AgentSection, resolution_env: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    internal: dict[str, dict[str, Any]] = {
        "filesystem": copy.deepcopy(FILESYSTEM_MCP_SERVER_CONFIG),
    }
    match agent.tools.discovery:
        case "basic":
            internal["pytools"] = copy.deepcopy(BASIC_SEARCH_MCP_SERVER_CONFIG)
        case "hybrid":
            internal["pytools"] = copy.deepcopy(HYBRID_SEARCH_MCP_SERVER_CONFIG)
        case "off":
            pass

    merged = {**internal, **agent.mcp_servers}

    result = replace_variables(merged, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for mcp_servers: {result.missing_variables}")

    return result.replaced


def _validated_ptc_servers(agent: AgentSection, resolution_env: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    servers: dict[str, dict[str, Any]] = {}
    if agent.tools.search:
        servers["google"] = copy.deepcopy(GOOGLE_SEARCH_MCP_SERVER_CONFIG)
    if agent.tools.fetch:
        servers["fetch"] = copy.deepcopy(FETCH_MCP_SERVER_CONFIG)
    servers.update(agent.ptc_servers)

    # Validate ${VAR} references resolve, but return the unsubstituted configs:
    # substitution happens at use (API generation / server start).
    result = replace_variables(servers, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for ptc_servers: {result.missing_variables}")

    return servers


def _resolve_kernel_env(agent: AgentSection, ws: Workspace, resolution_env: Mapping[str, str]) -> dict[str, str]:
    env: dict[str, str] = {
        "PYTHONPATH": str(ws.generated_dir),
    }

    if home := resolution_env.get("HOME"):
        env["HOME"] = home

    env.update(agent.kernel_env)

    result = replace_variables(env, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for kernel_env: {result.missing_variables}")

    return result.replaced


def _require_hybrid_extra() -> None:
    missing = [name for name in _HYBRID_EXTRA_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        raise ValueError(
            'discovery = "hybrid" requires the freeact[search] extra '
            f"(missing: {', '.join(missing)}). Install with: pip install 'freeact[search]'"
        )
