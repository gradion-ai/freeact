import asyncio

# --8<-- [start:agent-imports]
from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeExecutionOutput,
    Response,
    Thoughts,
    ToolOutput,
)

# --8<-- [end:agent-imports]
# --8<-- [start:config-imports]
from freeact.agent.config import Config, init_config

# --8<-- [end:config-imports]
# --8<-- [start:apigen-imports]
from freeact.agent.tools.pytools.apigen import generate_mcp_sources

# --8<-- [end:apigen-imports]


async def main() -> None:
    # --8<-- [start:config]
    # Initialize .freeact/ config directory if needed
    init_config()

    # Load configuration from .freeact/
    config = Config()
    # --8<-- [end:config]

    # --8<-- [start:apigen]
    # Generate Python APIs for MCP servers in ptc_servers
    for server_name, params in config.ptc_servers.items():
        if not (config.generated_dir / "mcptools" / server_name).exists():
            await generate_mcp_sources({server_name: params}, config.generated_dir)
    # --8<-- [end:apigen]

    # --8<-- [start:agent]
    async with Agent(config=config) as agent:
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
