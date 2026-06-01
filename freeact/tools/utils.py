import asyncio
import json
from collections.abc import Set
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastmcp.client.transports import ClientTransport, StdioTransport
from ipybox.utils import arun
from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FilteredToolset, PrefixedToolset
from pydantic_ai.toolsets.abstract import AbstractToolset, ToolsetTool

IPYBOX_TOOL_PREFIX = "ipybox"
IPYBOX_TOOL_DEFS_PATH = Path(__file__).parent / "ipybox.json"
SUBAGENT_TOOL_DEFS_PATH = Path(__file__).parent / "subagent.json"


class _McpServer:
    """MCP server adapter that namespaces and filters an `MCPToolset`.

    Wraps a pydantic-ai [`MCPToolset`][pydantic_ai.mcp.MCPToolset] so that tool
    names exposed via `get_tools` are prefixed with `tool_prefix` (avoiding
    collisions between servers) and optionally excludes selected tools. Tool
    calls route to the underlying toolset via `direct_call_tool` using the
    un-prefixed tool name.
    """

    def __init__(
        self,
        transport: ClientTransport,
        *,
        tool_prefix: str,
        excluded_tools: Set[str] = frozenset(),
    ) -> None:
        self.tool_prefix = tool_prefix
        self._toolset = MCPToolset(transport)

        view: AbstractToolset[Any] = self._toolset
        if excluded_tools:
            excluded = frozenset(excluded_tools)
            view = FilteredToolset(view, lambda ctx, tool_def: tool_def.name not in excluded)
        self._view: AbstractToolset[Any] = PrefixedToolset(view, tool_prefix)

    async def __aenter__(self) -> "_McpServer":
        await self._view.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> bool | None:
        return await self._view.__aexit__(*exc_info)

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        return await self._view.get_tools(ctx)

    async def direct_call_tool(self, name: str, args: dict[str, Any]) -> Any:
        return await self._toolset.direct_call_tool(name=name, args=args)


async def get_tool_definitions(server: _McpServer) -> list[ToolDefinition]:
    """Extract tool definitions from an MCP server.

    Args:
        server: Active MCP server connection.

    Returns:
        List of tool definitions exposed by the server.
    """
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.result import RunUsage

    ctx: RunContext[Any] = RunContext(
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


async def load_subagent_task_tool_definitions() -> list[ToolDefinition]:
    """Load cached subagent task tool definitions from the bundled JSON file."""
    return await arun(load_tool_definitions, SUBAGENT_TOOL_DEFS_PATH)


async def save_ipybox_tool_definitions() -> None:
    """Regenerate the bundled ipybox tool definitions cache.

    Connects to a live ipybox MCP server, extracts tool definitions
    (excluding `install_package`), and saves them to the bundled JSON file.
    """
    transport = StdioTransport(command="uvx", args=["ipybox"])
    server = _McpServer(transport, tool_prefix=IPYBOX_TOOL_PREFIX, excluded_tools={"install_package"})
    async with server:
        tool_defs = await get_tool_definitions(server)
        await arun(save_tool_definitions, tool_defs, IPYBOX_TOOL_DEFS_PATH)


if __name__ == "__main__":
    asyncio.run(save_ipybox_tool_definitions())
