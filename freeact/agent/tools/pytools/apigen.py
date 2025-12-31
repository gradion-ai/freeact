import logging
from pathlib import Path
from typing import Any

import ipybox

from freeact.agent.tools.pytools.categories import Categories, list_categories

logger = logging.getLogger("freeact")


async def generate_mcp_sources(config: dict[str, dict[str, Any]]) -> None:
    """Generate Python API for MCP servers in `config`.

    For servers not already in `mcptools/` categories, generates Python API
    using `ipybox.generate_mcp_sources`.

    Args:
        config: Dictionary mapping server names to server configurations.
    """
    if not config:
        return

    categories: Categories = list_categories()
    categories_mcptools = set(categories.mcptools)

    for name, params in config.items():
        if name not in categories_mcptools:
            logger.info(f"Generating Python API for MCP server: {name}")
            await ipybox.generate_mcp_sources(name, params, Path("mcptools"))
