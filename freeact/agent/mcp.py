import asyncio
import logging
from collections.abc import Set
from typing import Any

from mcp import types as mcp_types
from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP, ToolResult
from pydantic_ai.tools import ToolDefinition

from freeact.agent.supervisor import ResourceSupervisor

logger = logging.getLogger("freeact")


class _MCPServerStdioFiltered(MCPServerStdio):
    """MCPServerStdio that filters out specified tools."""

    def __init__(self, excluded_tools: Set[str], **kwargs: Any):
        super().__init__(**kwargs)
        self._excluded_tools = excluded_tools

    async def list_tools(self) -> list[mcp_types.Tool]:
        tools = await super().list_tools()
        return [t for t in tools if t.name not in self._excluded_tools]


class MCPServerManager:
    """Lifecycle and dispatch for the agent's MCP servers.

    Servers are created from resolved configs, started/stopped
    concurrently, and their tools exposed with the server name as prefix.
    Tool call exceptions are converted to error text so a failing server
    never crashes a turn.
    """

    def __init__(self, server_configs: dict[str, dict[str, Any]]) -> None:
        self._server_configs = server_configs
        self._servers: dict[str, MCPServer] = {}
        self._supervisors: list[ResourceSupervisor] = []
        self._tool_definitions: list[ToolDefinition] = []
        self._tool_mapping: dict[str, MCPServer] = {}

    @property
    def tool_definitions(self) -> list[ToolDefinition]:
        """Definitions of all tools exposed by managed servers."""
        return list(self._tool_definitions)

    def serves(self, tool_name: str) -> bool:
        """Whether a tool name belongs to a managed server."""
        return tool_name in self._tool_mapping

    async def start(self) -> None:
        """Create and start all configured servers, then load their tools.

        On partial start failure, successfully started servers are stopped
        before the error propagates.
        """
        if self._supervisors:
            return

        self._servers = self._create_servers()

        supervisors = []
        for name, server in self._servers.items():
            logger.debug(f"Starting MCP server: {name}")
            server.tool_prefix = name
            supervisors.append(ResourceSupervisor(server, f"mcp-server-{name}"))

        try:
            await asyncio.gather(*(supervisor.start() for supervisor in supervisors))
        except Exception:
            await asyncio.gather(*(supervisor.stop() for supervisor in supervisors), return_exceptions=True)
            raise

        self._supervisors = supervisors

        try:
            for server in self._servers.values():
                for tool_def in await _get_tool_definitions(server):
                    self._tool_definitions.append(tool_def)
                    self._tool_mapping[tool_def.name] = server
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop all servers, raising collected errors after all stopped."""
        self._tool_definitions = []
        self._tool_mapping = {}

        supervisors = self._supervisors
        self._supervisors = []
        self._servers = {}
        if not supervisors:
            return

        results = await asyncio.gather(*(supervisor.stop() for supervisor in supervisors), return_exceptions=True)
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise ExceptionGroup("Multiple errors while stopping MCP servers", errors)

    async def call(self, tool_name: str, tool_args: dict[str, object]) -> ToolResult:
        """Call a managed server tool, converting exceptions to error text."""
        try:
            server = self._tool_mapping[tool_name]
            resolved_name = tool_name.removeprefix(f"{server.tool_prefix}_")
            return await server.direct_call_tool(name=resolved_name, args=tool_args)
        except Exception as e:
            return f"MCP tool call failed: {str(e)}"

    def _create_servers(self) -> dict[str, MCPServer]:
        servers: dict[str, MCPServer] = {}

        for name, raw_cfg in self._server_configs.items():
            cfg = dict(raw_cfg)
            excluded_tools = cfg.pop("exclude_tools", None) or cfg.pop("excluded_tools", None)
            match cfg:
                case {"command": _}:
                    if excluded_tools:
                        servers[name] = _MCPServerStdioFiltered(
                            excluded_tools=frozenset(excluded_tools),
                            **cfg,
                        )
                    else:
                        servers[name] = MCPServerStdio(**cfg)
                case {"url": _}:
                    servers[name] = MCPServerStreamableHTTP(**cfg)
                case _:
                    raise ValueError(f"Invalid server config for {name}: must have 'command' or 'url'")

        return servers


async def _get_tool_definitions(server: MCPServer) -> list[ToolDefinition]:
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
