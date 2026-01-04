import asyncio
from pathlib import Path

# --8<-- [start:imports]
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

# --8<-- [end:imports]


async def main() -> None:
    # --8<-- [start:config]
    # Initialize .freeact/ config directory if needed
    init_config()

    # Load configuration from .freeact/
    config = Config()
    # --8<-- [end:config]

    # --8<-- [start:apigen]
    # Generate Python APIs for MCP servers not yet in mcptools/
    for server_name, params in config.ptc_servers.items():
        if not Path(f"mcptools/{server_name}").exists():
            await generate_mcp_sources({server_name: params})
    # --8<-- [end:apigen]

    # --8<-- [start:agent]
    async with Agent(
        model=config.model,
        model_settings=config.model_settings,
        system_prompt=config.system_prompt,
        mcp_servers=config.mcp_servers,
    ) as agent:
        prompt = "Who is the F1 world champion 2025?"

        async for event in agent.stream(prompt):
            match event:
                case ApprovalRequest(tool_name="ipybox_execute_ipython_cell", tool_args=args) as request:
                    print(f"Code action:\n{args['code']}")
                    request.approve(True)
                case ApprovalRequest(tool_name=name, tool_args=args) as request:
                    print(f"Tool: {name}")
                    print(f"Args: {args}")
                    request.approve(True)
                case Thoughts(content=content):
                    print(f"Thinking: {content}")
                case CodeExecutionOutput(text=text):
                    print(f"Code execution output: {text}")
                case ToolOutput(content=content):
                    print(f"Tool call result: {content}")
                case Response(content=content):
                    print(content)
    # --8<-- [end:agent]


if __name__ == "__main__":
    asyncio.run(main())
