"""MCP server for searching tool categories."""

import os
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from freeact.tools.pytools import GENTOOLS_DIR, MCPTOOLS_DIR
from freeact.tools.pytools.categories import Categories
from freeact.tools.pytools.categories import list_categories as _list_categories

_PYTOOLS_DIR = Path(os.environ.get("PYTOOLS_DIR", ".freeact/generated"))


class Tools(BaseModel):
    """Tools discovered within a specific category directory."""

    gentools: list[str] = Field(description="Tools in gentools/<category>/<tool>/api.py")
    mcptools: list[str] = Field(description="Tools in mcptools/<category>/<tool>.py")


mcp = FastMCP("pytools_mcp", log_level="ERROR")


@mcp.tool(
    name="list_categories",
    annotations={
        "title": "List Tool Categories",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def list_categories() -> Categories:
    """List all tool categories in `gentools/` and `mcptools/` directories."""
    return _list_categories(_PYTOOLS_DIR)


@mcp.tool(
    name="list_tools",
    annotations={
        "title": "List Tools in Categories",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def list_tools(
    categories: Annotated[
        str | list[str],
        Field(description="Category name or list of category names (e.g., 'github' or ['github', 'slack'])"),
    ],
) -> dict[str, Tools]:
    """List all tools in one or more categories under `gentools/` and `mcptools/` directories."""
    base = _PYTOOLS_DIR

    if isinstance(categories, str):
        categories = [categories]

    result: dict[str, Tools] = {}

    for category in categories:
        gentools: list[str] = []
        mcptools: list[str] = []

        # mcptools: <category>/<tool>.py
        mcp_cat_dir = base / MCPTOOLS_DIR / category
        if mcp_cat_dir.is_dir():
            mcptools = [f.stem for f in mcp_cat_dir.glob("*.py") if not f.name.startswith("_")]

        # gentools: <category>/<tool>/api.py
        gen_cat_dir = base / GENTOOLS_DIR / category
        if gen_cat_dir.is_dir():
            gentools = [d.name for d in gen_cat_dir.iterdir() if d.is_dir() and (d / "api.py").exists()]

        result[category] = Tools(gentools=gentools, mcptools=mcptools)

    return result


def main() -> None:
    """Entry point for the pytools MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
