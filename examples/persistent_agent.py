import asyncio
import uuid

from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeExecutionOutput,
    Response,
    Thoughts,
    ToolOutput,
)
from freeact.agent.config import Config

# --8<-- [start:session-imports]
from freeact.agent.store import SessionStore

# --8<-- [end:session-imports]
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
    await Config.init()
    config = Config()

    for server_name, params in config.ptc_servers.items():
        if not (config.generated_dir / "mcptools" / server_name).exists():
            await generate_mcp_sources({server_name: params}, config.generated_dir)

    # --8<-- [start:session-create]
    # Create a session store with a new session ID
    session_id = str(uuid.uuid4())
    session_store = SessionStore(config.sessions_dir, session_id)
    # --8<-- [end:session-create]

    # --8<-- [start:session-run]
    # Run agent with session persistence
    async with Agent(config=config, session_store=session_store) as agent:
        await handle_events(agent, "What is the capital of France?")
        await handle_events(agent, "What about Germany?")
    # --8<-- [end:session-run]

    # --8<-- [start:session-resume]
    # Resume session with the same session ID
    session_store = SessionStore(config.sessions_dir, session_id)

    async with Agent(config=config, session_store=session_store) as agent:
        # Previous message history is restored automatically
        await handle_events(agent, "And what was the first country we discussed?")
    # --8<-- [end:session-resume]


if __name__ == "__main__":
    asyncio.run(main())
