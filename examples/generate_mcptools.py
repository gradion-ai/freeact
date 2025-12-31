"""mcptools generation example.

Demonstrates generating Python APIs for PTC servers.
"""

import asyncio

# --8<-- [start:example]
from freeact.agent import Agent
from freeact.agent.config import Config, init_config
from freeact.agent.tools.pytools.apigen import generate_mcp_sources


async def main() -> None:
    # Initialize and load configuration
    init_config()
    config = Config()

    # Generate Python APIs for PTC servers before starting agent
    # This creates modules in mcptools/<server_name>/
    if config.ptc_servers:
        await generate_mcp_sources(config.ptc_servers)

    # Now the agent can write code that imports from mcptools/
    async with Agent(
        model=config.model,
        model_settings=config.model_settings,
        system_prompt=config.system_prompt,
        mcp_servers=config.mcp_servers,
    ):
        # Agent can now use PTC tools in code actions:
        # from mcptools.google.search import run, Params
        # result = run(Params(query="..."))
        pass


# --8<-- [end:example]

if __name__ == "__main__":
    asyncio.run(main())
