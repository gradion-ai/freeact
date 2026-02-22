import copy
from pathlib import Path
from typing import Any, Literal, Mapping

from ipybox.vars import replace_variables
from pydantic_ai.models import Model, infer_model
from pydantic_ai.providers import Provider, infer_provider_class


def resolve_model_instance(
    *,
    model: str | Model,
    provider_settings: dict[str, Any] | None,
    resolution_env: Mapping[str, str],
) -> str | Model:
    if isinstance(model, Model):
        return model

    if provider_settings is None:
        return model

    result = replace_variables(provider_settings, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for provider_settings: {result.missing_variables}")

    resolved = result.replaced

    def provider_factory(name: str) -> Provider[Any]:
        kwargs = dict(resolved)
        if name in ("google-vertex", "google-gla"):
            kwargs.setdefault("vertexai", name == "google-vertex")
        provider_class = infer_provider_class(name)
        return provider_class(**kwargs)

    return infer_model(model, provider_factory=provider_factory)


def resolve_kernel_env(
    *,
    kernel_env: dict[str, str],
    generated_dir: Path,
    resolution_env: Mapping[str, str],
) -> dict[str, str]:
    env: dict[str, str] = {
        "PYTHONPATH": str(generated_dir),
    }

    if home := resolution_env.get("HOME"):
        env["HOME"] = home

    env.update(kernel_env)

    result = replace_variables(env, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for kernel_env: {result.missing_variables}")

    return result.replaced


def resolve_mcp_servers(
    *,
    tool_search: Literal["basic", "hybrid"],
    mcp_servers: dict[str, dict[str, Any]],
    basic_search_mcp_server_config: dict[str, Any],
    hybrid_search_mcp_server_config: dict[str, Any],
    filesystem_mcp_server_config: dict[str, Any],
    resolution_env: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    pytools = hybrid_search_mcp_server_config if tool_search == "hybrid" else basic_search_mcp_server_config
    internal = {
        "pytools": copy.deepcopy(pytools),
        "filesystem": copy.deepcopy(filesystem_mcp_server_config),
    }

    merged = {
        **internal,
        **mcp_servers,
    }

    result = replace_variables(merged, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for mcp_servers: {result.missing_variables}")

    return result.replaced


def validate_ptc_servers(
    *,
    ptc_servers: dict[str, dict[str, Any]],
    resolution_env: Mapping[str, str],
) -> None:
    result = replace_variables(ptc_servers, resolution_env)
    if result.missing_variables:
        raise ValueError(f"Missing environment variables for ptc_servers: {result.missing_variables}")
