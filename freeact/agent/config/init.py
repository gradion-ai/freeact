"""Initialize .freeact/ directory from templates."""

import json
import shutil
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, Literal

PYTOOLS_BASIC: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.agent.tools.pytools.search.basic"],
}

PYTOOLS_HYBRID: dict[str, Any] = {
    "command": "python",
    "args": ["-m", "freeact.agent.tools.pytools.search.hybrid"],
    "env": {"GEMINI_API_KEY": "${GEMINI_API_KEY}"},
}


def init_config(
    working_dir: Path | None = None,
    tool_search: Literal["basic", "hybrid"] = "basic",
) -> None:
    """Initialize `.freeact/` config directory from templates.

    Copies template files that don't already exist, preserving user modifications.
    Enforces the pytools server configuration based on the tool_search setting.

    Args:
        working_dir: Base directory. Defaults to current working directory.
        tool_search: Tool discovery mode. "basic" uses category browsing via
            `list_categories` and `list_tools`. "hybrid" uses BM25/vector search
            via `search_tools` for natural language queries.
    """
    working_dir = working_dir or Path.cwd()
    freeact_dir = working_dir / ".freeact"

    template_files = files("freeact.agent.config").joinpath("templates")

    with as_file(template_files) as template_dir:
        for template_file in template_dir.rglob("*"):
            if not template_file.is_file():
                continue

            relative = template_file.relative_to(template_dir)
            target = freeact_dir / relative

            if target.exists():
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template_file, target)

    # Create plans directory
    plans_dir = freeact_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)

    # Enforce pytools configuration based on tool_search setting
    servers_path = freeact_dir / "servers.json"
    if servers_path.exists():
        servers = json.loads(servers_path.read_text())
        current_pytools = servers.get("mcp-servers", {}).get("pytools", {})
        current_args = current_pytools.get("args", [])

        # Check if current mode matches expected by looking for module string
        has_hybrid = any("freeact.agent.tools.pytools.search.hybrid" in arg for arg in current_args)
        has_basic = any("freeact.agent.tools.pytools.search.basic" in arg for arg in current_args)
        needs_hybrid = tool_search == "hybrid"

        # Only update if mode doesn't match (preserves user modifications when mode is correct)
        if needs_hybrid and not has_hybrid:
            servers.setdefault("mcp-servers", {})["pytools"] = PYTOOLS_HYBRID
            servers_path.write_text(json.dumps(servers, indent=2) + "\n")
        elif not needs_hybrid and not has_basic:
            servers.setdefault("mcp-servers", {})["pytools"] = PYTOOLS_BASIC
            servers_path.write_text(json.dumps(servers, indent=2) + "\n")
