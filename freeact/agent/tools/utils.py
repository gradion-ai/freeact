import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from ipybox.utils import arun
from pydantic_ai.mcp import MCPServer, MCPServerStdio
from pydantic_ai.tools import ToolDefinition

IPYBOX_TOOL_DEFS_PATH = Path(__file__).parent / "ipybox.json"
TASK_TOOL_DEFS_PATH = Path(__file__).parent / "task.json"
IPYBOX_TOOL_PREFIX = "ipybox"


async def get_tool_definitions(server: MCPServer) -> list[ToolDefinition]:
    """Extract tool definitions from an MCP server.

    Args:
        server: Active MCP server connection.

    Returns:
        List of tool definitions exposed by the server.
    """
    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.result import RunUsage

    ctx = RunContext(
        deps=None,
        model=TestModel(),
        usage=RunUsage(),
    )

    tools = await server.get_tools(ctx)
    return [tool.tool_def for tool in tools.values()]


def load_tool_definitions(path: Path) -> list[ToolDefinition]:
    """Load tool definitions from a JSON file.

    Args:
        path: Path to JSON file containing serialized tool definitions.

    Returns:
        List of deserialized tool definitions.
    """
    data = json.loads(path.read_text())
    return [ToolDefinition(**item) for item in data]


def save_tool_definitions(tool_defs: list[ToolDefinition], path: Path) -> None:
    """Persist tool definitions to a JSON file.

    Args:
        tool_defs: Tool definitions to serialize.
        path: Destination file path.
    """
    data = [asdict(tool_def) for tool_def in tool_defs]
    path.write_text(json.dumps(data, indent=2))


async def load_ipybox_tool_definitions() -> list[ToolDefinition]:
    """Load cached ipybox tool definitions from the bundled JSON file."""
    return await arun(load_tool_definitions, IPYBOX_TOOL_DEFS_PATH)


async def load_task_tool_definitions() -> list[ToolDefinition]:
    """Load cached task tool definitions from the bundled JSON file."""
    return await arun(load_tool_definitions, TASK_TOOL_DEFS_PATH)


async def save_ipybox_tool_definitions() -> None:
    """Regenerate the bundled ipybox tool definitions cache.

    Connects to a live ipybox MCP server, extracts tool definitions
    (excluding `install_package`), and saves them to the bundled JSON file.
    """
    server = MCPServerStdio("uvx", args=["ipybox"], tool_prefix=IPYBOX_TOOL_PREFIX)
    server = server.filtered(lambda _, t: t.name != f"{IPYBOX_TOOL_PREFIX}_install_package")
    async with server as server:
        tool_defs = await get_tool_definitions(server)
        await arun(save_tool_definitions, tool_defs, IPYBOX_TOOL_DEFS_PATH)


if __name__ == "__main__":
    asyncio.run(save_ipybox_tool_definitions())
