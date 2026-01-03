"""mcptools generation example.

Demonstrates generating Python APIs for PTC servers.
"""

import asyncio

# --8<-- [start:example]
from pathlib import Path

from freeact.agent import Agent
from freeact.agent.config import Config, init_config
from freeact.agent.tools.pytools.apigen import generate_mcp_sources


async def main() -> None:
    # Initialize and load configuration
    init_config()
    config = Config()

    # Generate Python APIs for MCP servers not yet in mcptools/
    for name, params in config.ptc_servers.items():
        if not Path(f"mcptools/{name}").exists():
            await generate_mcp_sources({name: params})

    # Now the agent can write code that imports from mcptools/
    async with Agent(
        model=config.model,
        model_settings=config.model_settings,
        system_prompt=config.system_prompt,
        mcp_servers=config.mcp_servers,
    ):
        # Agent can now programmatically call the tools in
        # code actions:
        # from mcptools.google.web_search import run, Params
        # result = run(Params(query="..."))
        pass


# --8<-- [end:example]

if __name__ == "__main__":
    asyncio.run(main())
