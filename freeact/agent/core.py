import asyncio
import logging
import re
from asyncio import Future
from collections.abc import Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

import ipybox
from aiostream.stream import merge
from pydantic_ai.direct import model_request_stream
from pydantic_ai.mcp import MCPServer, ToolResult
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    PartDeltaEvent,
    PartStartEvent,
    SystemPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings
from pydantic_ai.tools import ToolDefinition

from freeact.agent.tools.utils import get_tool_definitions, load_ipybox_tool_definitions

logger = logging.getLogger("freeact")


@dataclass
class ResponseChunk:
    """Partial text from an in-progress model response."""

    content: str


@dataclass
class Response:
    """Complete model text response after streaming finishes."""

    content: str


@dataclass
class ThoughtsChunk:
    """Partial text from model's extended thinking."""

    content: str


@dataclass
class Thoughts:
    """Complete model thoughts after streaming finishes."""

    content: str


@dataclass
class ToolOutput:
    """Result from a JSON-based MCP tool call."""

    content: ToolResult


@dataclass
class CodeExecutionOutputChunk:
    """Partial output from an in-progress code execution."""

    text: str


@dataclass
class CodeExecutionOutput:
    """Complete result from Python code execution in the ipybox kernel."""

    text: str | None
    images: list[Path]

    def ptc_rejected(self) -> bool:
        """Whether the output indicates a rejected programmatic tool call."""
        if not self.text:
            return False

        # TODO: make detection of PTC rejection more robust ...
        pattern = r"ToolRunnerError: Approval request for \S+ rejected"
        return bool(re.search(pattern, self.text))

    def format(self, max_chars: int = 5000) -> str:
        """Format output with image markdown links, truncated to `max_chars`.

        Preserves 80% of characters from the start and 20% from the end
        when truncation is needed.
        """
        parts: list[str] = []
        if self.text:
            parts.append(self.text)
        for image_path in self.images:
            parts.append(f"![Image]({image_path})")
        formatted = "\n".join(parts) if parts else ""

        if len(formatted) <= max_chars:
            return formatted

        first_part_len = int(max_chars * 0.8)
        last_part_len = int(max_chars * 0.2) - 3

        return formatted[:first_part_len] + "..." + formatted[-last_part_len:]


@dataclass
class ApprovalRequest:
    """Pending tool execution awaiting user approval.

    Yielded by [`Agent.stream()`][freeact.agent.core.Agent.stream] before
    executing any tool. The agent is suspended until `approve()` is called.
    """

    tool_name: str
    tool_args: dict[str, Any]
    _future: Future[bool] = field(default_factory=Future)

    def approve(self, decision: bool) -> None:
        """Resolve this approval request.

        Args:
            decision: `True` to allow execution, `False` to reject.
        """
        self._future.set_result(decision)

    async def approved(self) -> bool:
        """Await until `approve()` is called and return the decision."""
        return await self._future


class Agent:
    """Code action agent that generates and executes Python code in ipybox.

    The agent fulfills user requests by writing Python code and running it in
    a sandboxed IPython kernel where variables persist across executions.
    Tools can be called in two ways:

    - **JSON tool calls**: MCP servers called directly via structured arguments
    - **Programmatic tool calls (PTC)**: Agent writes Python code that imports
      and calls tool APIs. These can be auto-generated from MCP schemas
      (`mcptools/`) or user-defined (`gentools/`).

    All tool executions require approval. The `stream()` method yields
    [`ApprovalRequest`][freeact.agent.core.ApprovalRequest] events that must
    be resolved before execution proceeds.

    Use as an async context manager or call `start()`/`stop()` explicitly.
    """

    def __init__(
        self,
        model: str | Model,
        model_settings: ModelSettings,
        system_prompt: str,
        mcp_servers: dict[str, MCPServer] | None = None,
        kernel_env: dict[str, str] | None = None,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
        images_dir: Path | None = None,
    ):
        """Initialize the agent.

        Args:
            model: LLM model identifier or pydantic-ai Model instance.
            model_settings: Temperature, max tokens, and other model params.
            system_prompt: Instructions defining agent behavior.
            mcp_servers: Named MCP servers for JSON-based tool calls.
            kernel_env: Environment variables passed to the IPython kernel.
            sandbox: Run the kernel in a sandboxed container.
            sandbox_config: Path to custom sandbox configuration.
            images_dir: Directory for saving generated images.
        """
        self.model = model
        self.model_settings = model_settings

        self._system_prompt = system_prompt

        self._mcp_servers = mcp_servers or {}
        self._tool_servers: dict[str, MCPServer] = {}
        self._tool_definitions: list[ToolDefinition] = []

        self._code_executor_lock = asyncio.Lock()
        self._code_executor = ipybox.CodeExecutor(
            kernel_env=kernel_env,
            sandbox=sandbox,
            sandbox_config=sandbox_config,
            images_dir=images_dir,
            log_level="ERROR",
        )

        self._message_history: list[ModelMessage] = []
        self._exit_stack = AsyncExitStack()

    @property
    def tool_names(self) -> list[str]:
        """Names of all registered tools (ipybox tools and MCP server tools)."""
        return [tool_def.name for tool_def in self._tool_definitions]

    async def __aenter__(self) -> "Agent":
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    async def start(self) -> None:
        """Start the code executor and connect to MCP servers.

        Automatically called when entering the async context manager.
        """
        await self._exit_stack.enter_async_context(self._code_executor)
        self._tool_definitions = await load_ipybox_tool_definitions()
        for name, server in self._mcp_servers.items():
            logger.info(f"Starting MCP server: {name}")
            server.tool_prefix = name
            await self._exit_stack.enter_async_context(server)
            for tool_def in await get_tool_definitions(server):
                self._tool_definitions.append(tool_def)
                self._tool_servers[tool_def.name] = server

    async def stop(self) -> None:
        """Stop the code executor and disconnect from MCP servers.

        Automatically called when exiting the async context manager.
        """
        self._tool_definitions = []
        self._tool_servers = {}
        await self._exit_stack.aclose()

    def _create_model_request(self, user_prompt: str | Sequence[UserContent]) -> ModelRequest:
        parts: list[SystemPromptPart | UserPromptPart] = []

        if not self._message_history:
            parts.append(SystemPromptPart(content=self._system_prompt))
        parts.append(UserPromptPart(content=user_prompt))

        return ModelRequest(parts=parts)

    async def stream(
        self, prompt: str | Sequence[UserContent]
    ) -> AsyncIterator[
        ApprovalRequest
        | ToolOutput
        | CodeExecutionOutputChunk
        | CodeExecutionOutput
        | ThoughtsChunk
        | Thoughts
        | ResponseChunk
        | Response
    ]:
        """Run a full agentic turn, yielding events as they occur.

        Loops through model responses and tool executions until the model
        produces a response without tool calls. Both JSON-based and programmatic
        tool calls yield an [`ApprovalRequest`][freeact.agent.core.ApprovalRequest]
        that must be resolved before execution proceeds.

        Args:
            prompt: User message as text or multimodal content sequence.

        Yields:
            [`ThoughtsChunk`][freeact.agent.core.ThoughtsChunk]: Partial model thinking.
            [`Thoughts`][freeact.agent.core.Thoughts]: Complete model thoughts.
            [`ResponseChunk`][freeact.agent.core.ResponseChunk]: Partial model response.
            [`Response`][freeact.agent.core.Response]: Complete model response.
            [`ApprovalRequest`][freeact.agent.core.ApprovalRequest]: Pending tool approval.
            [`CodeExecutionOutputChunk`][freeact.agent.core.CodeExecutionOutputChunk]: Partial code execution output.
            [`CodeExecutionOutput`][freeact.agent.core.CodeExecutionOutput]: Complete code execution output.
            [`ToolOutput`][freeact.agent.core.ToolOutput]: Result from a JSON-based MCP tool call..
        """
        request = self._create_model_request(prompt)
        request_params = ModelRequestParameters(function_tools=self._tool_definitions)

        self._message_history.append(request)

        while True:
            thinking_parts: list[str] = []
            response_parts: list[str] = []

            async with model_request_stream(
                self.model,
                self._message_history,
                model_settings=self.model_settings,
                model_request_parameters=request_params,
            ) as event_stream:
                async for event in event_stream:
                    match event:
                        case PartStartEvent(part=ThinkingPart(content=content)) if content:
                            thinking_parts.append(content)
                            yield ThoughtsChunk(content=content)
                        case PartStartEvent(part=TextPart(content=content)) if content:
                            response_parts.append(content)
                            yield ResponseChunk(content=content)
                        case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=delta)):
                            thinking_parts.append(delta)
                            yield ThoughtsChunk(content=delta)
                        case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)):
                            response_parts.append(delta)
                            yield ResponseChunk(content=delta)

                aggregated = event_stream.get()

            thoughts = "".join(thinking_parts) if thinking_parts else None
            response = "".join(response_parts)

            self._message_history.append(aggregated)

            if thoughts:
                yield Thoughts(content=thoughts)

            if response:
                yield Response(content=response)

            if not aggregated.tool_calls:
                return

            tool_returns: list[ToolReturnPart] = []
            tool_streams = [self._execute_tool(call) for call in aggregated.tool_calls]

            merged = merge(*tool_streams)

            async with merged.stream() as streamer:
                async for item in streamer:
                    match item:
                        case ToolReturnPart():
                            tool_returns.append(item)
                        case _:
                            yield item

            self._message_history.append(ModelRequest(parts=tool_returns))

            if any(tool_return.metadata.get("rejected", False) for tool_return in tool_returns):
                content = "Tool call rejected"
                yield ResponseChunk(content=content)
                yield Response(content=content)
                break  # end of agent turn

    async def _execute_tool(
        self, call: ToolCallPart
    ) -> AsyncIterator[ApprovalRequest | CodeExecutionOutputChunk | CodeExecutionOutput | ToolOutput | ToolReturnPart]:
        tool_name = call.tool_name
        tool_args = call.args_as_dict()

        if tool_name not in self.tool_names:
            content = f"Unknown tool name: {tool_name}"
        else:
            approval = ApprovalRequest(tool_name=tool_name, tool_args=tool_args)
            yield approval

            rejected = False
            if not await approval.approved():
                content = "Tool call rejected"
                rejected = True
            else:
                match tool_name:
                    case "ipybox_execute_ipython_cell":
                        async for item in self._ipybox_execute_ipython_cell(tool_args["code"]):
                            yield item
                            match item:
                                case CodeExecutionOutput() if item.ptc_rejected():
                                    rejected = True
                                    content = "Tool call rejected"
                                case CodeExecutionOutput():
                                    content = item.format(max_chars=tool_args.get("max_output_chars", 5000))
                    case "ipybox_register_mcp_server":
                        content = await self._ipybox_register_mcp_server(
                            server_name=tool_args["server_name"],
                            server_params=tool_args["server_params"],
                        )
                        yield ToolOutput(content=content)
                    case "ipybox_reset":
                        content = await self._ipybox_reset()
                        yield ToolOutput(content=content)
                    case _:
                        content = await self._call_mcp_tool(tool_name, tool_args)
                        yield ToolOutput(content=content)

        yield ToolReturnPart(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            content=content,
            metadata={"rejected": rejected},
        )

    async def _ipybox_execute_ipython_cell(
        self, code: str
    ) -> AsyncIterator[ApprovalRequest | CodeExecutionOutputChunk | CodeExecutionOutput]:
        try:
            async with self._code_executor_lock:
                async for item in self._code_executor.stream(code, chunks=True):
                    match item:
                        case ipybox.ApprovalRequest(
                            server_name=server_name,
                            tool_name=tool_name,
                            tool_args=tool_args,
                        ):
                            ptc_request = ApprovalRequest(
                                tool_name=f"{server_name}_{tool_name}",  # type: ignore[has-type]
                                tool_args=tool_args,  # type: ignore[has-type]
                            )
                            yield ptc_request
                            if await ptc_request.approved():
                                await item.accept()
                            else:
                                await item.reject()
                        case ipybox.CodeExecutionChunk(text=text):
                            yield CodeExecutionOutputChunk(text=text)  # type: ignore[has-type]
                        case ipybox.CodeExecutionResult(text=text, images=images):
                            yield CodeExecutionOutput(text=text, images=images)  # type: ignore[has-type]
        except Exception as e:
            yield CodeExecutionOutputChunk(text=str(e))
            yield CodeExecutionOutput(text=str(e), images=[])

    async def _ipybox_register_mcp_server(self, server_name: str, server_params: dict[str, Any]) -> str:
        try:
            tool_names = await ipybox.generate_mcp_sources(server_name, server_params, Path("mcptools"))
            return f"Registered MCP server {server_name} with tools: {', '.join(tool_names)}"
        except Exception as e:
            return f"Registration of MCP server {server_name} failed: {str(e)}"

    async def _ipybox_reset(self) -> str:
        try:
            async with self._code_executor_lock:
                await self._code_executor.reset()
                return "Kernel reset successfully."
        except Exception as e:
            return f"Kernel reset failed: {str(e)}"

    async def _call_mcp_tool(self, tool_name: str, tool_args: dict[str, object]) -> ToolResult:
        try:
            mcp_server = self._tool_servers[tool_name]
            return await mcp_server.direct_call_tool(
                name=tool_name.removeprefix(f"{mcp_server.tool_prefix}_"),
                args=tool_args,
            )
        except Exception as e:
            return f"MCP tool call failed: {str(e)}"
