"""mcptools generation example.

Demonstrates generating Python APIs for PTC servers.
"""

import asyncio

# --8<-- [start:example]
from pathlib import Path

from freeact.agent.config import Config
from freeact.agent.tools.pytools.apigen import generate_mcp_sources


async def main() -> None:
    # Load configuration
    config = Config()

    # Generate Python APIs for MCP servers not yet in mcptools/
    for name, params in config.ptc_servers.items():
        if not Path(f"mcptools/{name}").exists():
            await generate_mcp_sources({name: params})


# --8<-- [end:example]

if __name__ == "__main__":
    asyncio.run(main())
