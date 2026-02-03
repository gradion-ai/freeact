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
        tool_search: Tool search mode - "basic" or "hybrid".
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
        expected_pytools = PYTOOLS_HYBRID if tool_search == "hybrid" else PYTOOLS_BASIC
        current_pytools = servers.get("mcp-servers", {}).get("pytools")

        if current_pytools != expected_pytools:
            servers.setdefault("mcp-servers", {})["pytools"] = expected_pytools
            servers_path.write_text(json.dumps(servers, indent=2) + "\n")
