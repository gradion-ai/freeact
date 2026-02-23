import asyncio

from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeExecutionOutput,
    Response,
    Thoughts,
    ToolOutput,
)
from freeact.agent.config import Config
from freeact.tools.pytools.apigen import generate_mcp_sources


async def handle_events(agent: Agent, prompt: str) -> None:
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


async def main() -> None:
    config = await Config.init()

    for server_name, params in config.ptc_servers.items():
        if not (config.generated_dir / "mcptools" / server_name).exists():
            await generate_mcp_sources({server_name: params}, config.generated_dir)

    # --8<-- [start:session-run-no-id]
    # No session_id: agent creates a new session ID internally.
    async with Agent(config=config) as agent:
        print(f"Generated session ID: {agent.session_id}")
        await handle_events(agent, "What is the capital of France?")
        await handle_events(agent, "What about Germany?")
    # --8<-- [end:session-run-no-id]

    # --8<-- [start:session-create]
    # Choose an explicit session ID.
    session_id = "countries-session"
    # --8<-- [end:session-create]

    # --8<-- [start:session-run-existing]
    # Create-or-resume behavior: resume if present, otherwise start new.
    async with Agent(config=config, session_id=session_id) as agent:
        await handle_events(agent, "What is the capital of Spain?")
    # --8<-- [end:session-run-existing]

    # --8<-- [start:session-resume]
    # Resume the same session ID later.
    async with Agent(config=config, session_id=session_id) as agent:
        # Previous message history is restored automatically
        await handle_events(agent, "And what country did we discuss in this session?")
    # --8<-- [end:session-resume]


if __name__ == "__main__":
    asyncio.run(main())
