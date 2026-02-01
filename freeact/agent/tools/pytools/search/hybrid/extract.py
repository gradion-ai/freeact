"""Extract docstrings from tool files using AST parsing."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolInfo:
    """Information about a discovered tool."""

    id: str  # "source:category:tool_name"
    name: str  # tool name
    category: str  # category/server name
    source: str  # "gentools" or "mcptools"
    filepath: Path  # source file path
    description: str  # full docstring (including Args/Returns)


def extract_docstring(filepath: Path) -> str | None:
    """Extract full docstring from run() or run_parsed() in file.

    Prefers run_parsed over run. Returns full docstring
    including Args/Returns/Raises sections.

    Args:
        filepath: Path to the Python file to parse.

    Returns:
        The docstring if found, None otherwise.
    """
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return None

    # Find run_parsed and run functions
    run_parsed_docstring: str | None = None
    run_docstring: str | None = None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "run_parsed":
                run_parsed_docstring = ast.get_docstring(node)
            elif node.name == "run":
                run_docstring = ast.get_docstring(node)

    # Prefer run_parsed over run
    return run_parsed_docstring or run_docstring


def make_tool_id(source: str, category: str, name: str) -> str:
    """Create 'source:category:name' ID.

    Args:
        source: Tool source ("gentools" or "mcptools").
        category: Category/server name.
        name: Tool name.

    Returns:
        Formatted tool ID string.
    """
    return f"{source}:{category}:{name}"


def parse_tool_id(tool_id: str) -> tuple[str, str, str]:
    """Parse ID into (source, category, name).

    Args:
        tool_id: Tool ID in "source:category:name" format.

    Returns:
        Tuple of (source, category, name).

    Raises:
        ValueError: If the ID format is invalid.
    """
    parts = tool_id.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid tool ID format: {tool_id}")
    return parts[0], parts[1], parts[2]


def _scan_mcptools(base_dir: Path) -> list[ToolInfo]:
    """Scan mcptools/<category>/<tool>.py for tools."""
    tools: list[ToolInfo] = []
    mcptools_dir = base_dir / "mcptools"

    if not mcptools_dir.is_dir():
        return tools

    for category_dir in mcptools_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith("_"):
            continue

        category = category_dir.name

        for tool_file in category_dir.glob("*.py"):
            if tool_file.name.startswith("_"):
                continue

            tool_name = tool_file.stem
            description = extract_docstring(tool_file)

            if description is None:
                continue

            tools.append(
                ToolInfo(
                    id=make_tool_id("mcptools", category, tool_name),
                    name=tool_name,
                    category=category,
                    source="mcptools",
                    filepath=tool_file,
                    description=description,
                )
            )

    return tools


def _scan_gentools(base_dir: Path) -> list[ToolInfo]:
    """Scan gentools/<category>/<tool>/api.py for tools."""
    tools: list[ToolInfo] = []
    gentools_dir = base_dir / "gentools"

    if not gentools_dir.is_dir():
        return tools

    for category_dir in gentools_dir.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith("_"):
            continue

        category = category_dir.name

        for tool_dir in category_dir.iterdir():
            if not tool_dir.is_dir() or tool_dir.name.startswith("_"):
                continue

            api_file = tool_dir / "api.py"
            if not api_file.is_file():
                continue

            tool_name = tool_dir.name
            description = extract_docstring(api_file)

            if description is None:
                continue

            tools.append(
                ToolInfo(
                    id=make_tool_id("gentools", category, tool_name),
                    name=tool_name,
                    category=category,
                    source="gentools",
                    filepath=api_file,
                    description=description,
                )
            )

    return tools


def scan_tools(base_dir: Path) -> list[ToolInfo]:
    """Scan mcptools/ and gentools/ for tools.

    Discovery rules:
    - mcptools/<category>/<tool>.py -> tool_name = stem
    - gentools/<category>/<tool>/api.py -> tool_name = parent dir
    - Skip _prefixed files/dirs
    - Skip tools without docstrings

    Args:
        base_dir: Base directory containing mcptools/ and gentools/.

    Returns:
        List of discovered tools with their information.
    """
    tools: list[ToolInfo] = []
    tools.extend(_scan_mcptools(base_dir))
    tools.extend(_scan_gentools(base_dir))
    return tools
