"""Basic freeact agent example.

Demonstrates minimal usage of the Python API with automatic approval.
"""

import asyncio

# --8<-- [start:example]
from freeact.agent import Agent, ApprovalRequest, Response
from freeact.agent.config import Config, init_config


async def main() -> None:
    # Initialize configuration directory if needed
    init_config()

    # Load configuration from .freeact/
    config = Config()

    # Create and run agent
    async with Agent(
        model=config.model,
        model_settings=config.model_settings,
        system_prompt=config.system_prompt,
        mcp_servers=config.mcp_servers,
    ) as agent:
        prompt = "List the files in the current directory"

        async for event in agent.stream(prompt):
            match event:
                case ApprovalRequest() as request:
                    # Auto-approve all tool calls
                    request.approve(True)
                case Response(content=content):
                    print(content)


# --8<-- [end:example]

if __name__ == "__main__":
    asyncio.run(main())
