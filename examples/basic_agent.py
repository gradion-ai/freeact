"""Basic freeact agent example.

Demonstrates minimal usage of the Python API with automatic approval.
"""

import asyncio

# --8<-- [start:example]
from pathlib import Path

from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeExecutionOutput,
    Response,
    Thoughts,
    ToolOutput,
)
from freeact.agent.config import Config, init_config
from freeact.agent.tools.pytools.apigen import generate_mcp_sources


async def main() -> None:
    # Initialize .freeact/ config directory if needed
    init_config()

    # Load configuration from .freeact/
    config = Config()

    # Generate Python APIs for MCP servers not yet in mcptools/
    for name, params in config.ptc_servers.items():
        if not Path(f"mcptools/{name}").exists():
            await generate_mcp_sources({name: params})

    # Create and run agent
    async with Agent(
        model=config.model,
        model_settings=config.model_settings,
        system_prompt=config.system_prompt,
        mcp_servers=config.mcp_servers,
    ) as agent:
        prompt = "Who is the F1 world champion 2025?"

        async for event in agent.stream(prompt):
            match event:
                case ApprovalRequest() as request:
                    # Auto-approve all code actions and tool calls
                    request.approve(True)
                case Thoughts(content=content):
                    print(f"Thinking: {content}")
                case CodeExecutionOutput(text=text):
                    print(f"Code execution output: {text}")
                case ToolOutput(content=content):
                    print(f"Tool call output: {content}")
                case Response(content=content):
                    print(content)


# --8<-- [end:example]

if __name__ == "__main__":
    asyncio.run(main())
