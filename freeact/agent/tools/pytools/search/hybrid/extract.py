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


def tool_info_from_path(filepath: Path, base_dir: Path) -> ToolInfo | None:
    """Create ToolInfo from a tool file path.

    Validates the path structure and extracts the docstring. Returns None if
    the path is not a valid tool location or has no docstring.

    Valid tool locations:
    - mcptools/<category>/<tool>.py
    - gentools/<category>/<tool>/api.py

    Args:
        filepath: Absolute path to the tool file.
        base_dir: Base directory containing mcptools/ and gentools/.

    Returns:
        ToolInfo if valid, None otherwise.
    """
    try:
        rel_path = filepath.relative_to(base_dir)
    except ValueError:
        return None

    parts = rel_path.parts

    # Check for mcptools/<category>/<tool>.py
    if len(parts) == 3 and parts[0] == "mcptools" and parts[2].endswith(".py"):
        category = parts[1]
        tool_name = Path(parts[2]).stem

        if category.startswith("_") or tool_name.startswith("_"):
            return None

        description = extract_docstring(filepath)
        if description is None:
            return None

        return ToolInfo(
            id=make_tool_id("mcptools", category, tool_name),
            name=tool_name,
            category=category,
            source="mcptools",
            filepath=filepath,
            description=description,
        )

    # Check for gentools/<category>/<tool>/api.py
    if len(parts) == 4 and parts[0] == "gentools" and parts[3] == "api.py":
        category = parts[1]
        tool_name = parts[2]

        if category.startswith("_") or tool_name.startswith("_"):
            return None

        description = extract_docstring(filepath)
        if description is None:
            return None

        return ToolInfo(
            id=make_tool_id("gentools", category, tool_name),
            name=tool_name,
            category=category,
            source="gentools",
            filepath=filepath,
            description=description,
        )

    return None


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

    # Scan mcptools/<category>/<tool>.py
    mcptools_dir = base_dir / "mcptools"
    if mcptools_dir.is_dir():
        for filepath in mcptools_dir.glob("*/*.py"):
            tool_info = tool_info_from_path(filepath, base_dir)
            if tool_info is not None:
                tools.append(tool_info)

    # Scan gentools/<category>/<tool>/api.py
    gentools_dir = base_dir / "gentools"
    if gentools_dir.is_dir():
        for filepath in gentools_dir.glob("*/*/api.py"):
            tool_info = tool_info_from_path(filepath, base_dir)
            if tool_info is not None:
                tools.append(tool_info)

    return tools
