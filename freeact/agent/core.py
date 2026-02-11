import asyncio
import logging
import re
import uuid
from asyncio import Future
from collections.abc import Sequence, Set
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

import ipybox
from aiostream.stream import merge
from mcp import types as mcp_types
from pydantic_ai.direct import model_request_stream
from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP, ToolResult
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
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.tools import ToolDefinition

from freeact.agent.config import Config
from freeact.agent.session import SessionStore
from freeact.agent.tools.utils import (
    get_tool_definitions,
    load_ipybox_tool_definitions,
    load_subagent_task_tool_definitions,
)

logger = logging.getLogger("freeact")


@dataclass(kw_only=True)
class AgentEvent:
    """Base class for all agent stream events.

    Carries the ``agent_id`` of the agent that produced the event, allowing
    callers to distinguish events from a parent agent vs. its subagents.
    """

    agent_id: str = ""


@dataclass
class ResponseChunk(AgentEvent):
    """Partial text from an in-progress model response."""

    content: str


@dataclass
class Response(AgentEvent):
    """Complete model text response after streaming finishes."""

    content: str


@dataclass
class ThoughtsChunk(AgentEvent):
    """Partial text from model's extended thinking."""

    content: str


@dataclass
class Thoughts(AgentEvent):
    """Complete model thoughts after streaming finishes."""

    content: str


@dataclass
class ToolOutput(AgentEvent):
    """Result from a tool or built-in agent operation."""

    content: ToolResult


@dataclass
class CodeExecutionOutputChunk(AgentEvent):
    """Partial output from an in-progress code execution."""

    text: str


@dataclass
class CodeExecutionOutput(AgentEvent):
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
class ApprovalRequest(AgentEvent):
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


class _MCPServerStdioFiltered(MCPServerStdio):
    """MCPServerStdio that filters out specified tools."""

    def __init__(self, excluded_tools: Set[str], **kwargs: Any):
        super().__init__(**kwargs)
        self._excluded_tools = excluded_tools

    async def list_tools(self) -> list[mcp_types.Tool]:
        tools = await super().list_tools()
        return [t for t in tools if t.name not in self._excluded_tools]


class _ResourceSupervisor:
    """Keeps a single async context manager running in its own task."""

    def __init__(self, resource: Any, name: str):
        self._resource = resource
        self._name = name
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._entered_resource: Any | None = None
        self._error: Exception | None = None

    async def start(self) -> Any:
        """Start resource task and wait until context is entered."""
        if self._task is not None:
            raise RuntimeError(f"Resource supervisor for '{self._name}' already started")

        self._task = asyncio.create_task(self._run(), name=f"resource-{self._name}")
        await self._ready.wait()

        if self._error is not None:
            raise RuntimeError(f"Failed to start resource '{self._name}'") from self._error

        return self._entered_resource

    async def stop(self) -> None:
        """Signal resource task to exit context and wait for completion."""
        if self._task is None:
            return

        self._stop.set()
        await self._task

    async def _run(self) -> None:
        try:
            async with self._resource as entered_resource:
                self._entered_resource = entered_resource
                self._ready.set()
                await self._stop.wait()
        except Exception as e:
            self._error = e
            self._ready.set()
            raise


class _SubagentRunner:
    """Runs a subagent in a dedicated task and streams its events safely."""

    def __init__(self, subagent: "Agent", semaphore: asyncio.Semaphore):
        self._subagent = subagent
        self._semaphore = semaphore

    async def stream(self, prompt: str, max_turns: int) -> AsyncIterator[AgentEvent]:
        queue: asyncio.Queue[AgentEvent | Exception | None] = asyncio.Queue()

        async def run_subagent() -> None:
            try:
                async with self._semaphore:
                    async with self._subagent:
                        async for event in self._subagent.stream(prompt, max_turns=max_turns):
                            await queue.put(event)
            except Exception as e:
                queue.put_nowait(e)
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(run_subagent())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    return
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


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
        config: Config,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
        session_store: SessionStore | None = None,
    ):
        """Initialize the agent.

        Args:
            config: Agent configuration containing model, system prompt,
                MCP servers, kernel env, timeouts, and subagent settings.
            sandbox: Run the kernel in sandbox mode.
            sandbox_config: Path to custom sandbox configuration.
        """
        self._config = config

        self.agent_id = config.agent_id
        self.model = config.model
        self.model_settings = config.model_settings

        self._system_prompt = config.system_prompt
        self._execution_timeout = config.execution_timeout
        self._enable_subagents = config.enable_subagents
        self._mcp_servers = config.mcp_servers
        self._subagent_semaphore = asyncio.Semaphore(config.max_subagents)
        self._sandbox = sandbox
        self._sandbox_config = sandbox_config
        self._session_store = session_store

        self._mcp_server_instances: dict[str, MCPServer] = {}
        self._tool_mapping: dict[str, MCPServer] = {}
        self._tool_definitions: list[ToolDefinition] = []

        self._kernel_env = config.kernel_env

        self._code_executor_lock = asyncio.Lock()
        self._code_executor = ipybox.CodeExecutor(
            kernel_env=config.kernel_env,
            sandbox=sandbox,
            sandbox_config=sandbox_config,
            images_dir=config.images_dir,
            approval_timeout=config.approval_timeout,
            log_level="ERROR",
        )

        self._message_history: list[ModelMessage] = []
        self._resource_supervisors: list[_ResourceSupervisor] = []

    @property
    def _history_agent_id(self) -> str:
        if self.agent_id.startswith("sub-"):
            return self.agent_id
        return "main"

    def _append_message_history(self, messages: list[ModelMessage]) -> None:
        if not messages:
            return

        self._message_history.extend(messages)
        if self._session_store is not None:
            self._session_store.append(agent_id=self._history_agent_id, messages=messages)

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
        if self._resource_supervisors:
            return

        if self._session_store is not None and self._history_agent_id == "main" and not self._message_history:
            self._message_history = self._session_store.load(agent_id="main")

        self._mcp_server_instances = self._create_mcp_servers()

        resource_supervisors = [_ResourceSupervisor(self._code_executor, "code-executor")]
        for name, server in self._mcp_server_instances.items():
            logger.info(f"Starting MCP server: {name}")
            server.tool_prefix = name
            resource_supervisors.append(_ResourceSupervisor(server, f"mcp-server-{name}"))

        try:
            await asyncio.gather(*(supervisor.start() for supervisor in resource_supervisors))
        except Exception:
            await asyncio.gather(
                *(supervisor.stop() for supervisor in resource_supervisors),
                return_exceptions=True,
            )
            raise

        self._resource_supervisors = resource_supervisors

        try:
            self._tool_definitions = await load_ipybox_tool_definitions()
            if self._enable_subagents:
                self._tool_definitions.extend(await load_subagent_task_tool_definitions())

            for server in self._mcp_server_instances.values():
                for tool_def in await get_tool_definitions(server):
                    self._tool_definitions.append(tool_def)
                    self._tool_mapping[tool_def.name] = server
        except Exception:
            self._tool_definitions = []
            self._tool_mapping = {}
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the code executor and disconnect from MCP servers.

        Automatically called when exiting the async context manager.
        """
        self._tool_definitions = []
        self._tool_mapping = {}

        resource_supervisors = self._resource_supervisors
        self._resource_supervisors = []
        if not resource_supervisors:
            return

        results = await asyncio.gather(
            *(supervisor.stop() for supervisor in resource_supervisors),
            return_exceptions=True,
        )
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise ExceptionGroup("Multiple errors while stopping agent resources", errors)
        self._mcp_server_instances = {}

    def _create_mcp_servers(self) -> dict[str, MCPServer]:
        if not self._mcp_servers:
            return {}

        servers: dict[str, MCPServer] = {}

        for name, raw_cfg in self._mcp_servers.items():
            cfg = dict(raw_cfg)
            excluded_tools = cfg.pop("excluded_tools", None)
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

    def _create_model_request(self, user_prompt: str | Sequence[UserContent]) -> ModelRequest:
        parts: list[SystemPromptPart | UserPromptPart] = []

        if not self._message_history:
            parts.append(SystemPromptPart(content=self._system_prompt))
        parts.append(UserPromptPart(content=user_prompt))

        return ModelRequest(parts=parts)

    async def stream(
        self,
        prompt: str | Sequence[UserContent],
        max_turns: int | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run a full agentic turn, yielding events as they occur.

        Loops through model responses and tool executions until the model
        produces a response without tool calls. Both JSON-based and programmatic
        tool calls yield an [`ApprovalRequest`][freeact.agent.core.ApprovalRequest]
        that must be resolved before execution proceeds.

        Args:
            prompt: User message as text or multimodal content sequence.
            max_turns: Maximum number of tool-execution rounds. Each round
                consists of a model response followed by tool execution.
                If None, runs until the model stops calling tools.

        Returns:
            An async event iterator.
        """
        request = self._create_model_request(prompt)
        request_params = ModelRequestParameters(function_tools=self._tool_definitions)

        self._append_message_history([request])

        turn = 0

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
                            yield ThoughtsChunk(content=content, agent_id=self.agent_id)
                        case PartStartEvent(part=TextPart(content=content)) if content:
                            response_parts.append(content)
                            yield ResponseChunk(content=content, agent_id=self.agent_id)
                        case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=delta)):
                            thinking_parts.append(delta)
                            yield ThoughtsChunk(content=delta, agent_id=self.agent_id)
                        case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)):
                            response_parts.append(delta)
                            yield ResponseChunk(content=delta, agent_id=self.agent_id)

                aggregated = event_stream.get()

            thoughts = "".join(thinking_parts) if thinking_parts else None
            response = "".join(response_parts)

            self._append_message_history([aggregated])

            if thoughts:
                yield Thoughts(content=thoughts, agent_id=self.agent_id)

            if response:
                yield Response(content=response, agent_id=self.agent_id)

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

            self._append_message_history([ModelRequest(parts=tool_returns)])

            if any(tool_return.metadata.get("rejected", False) for tool_return in tool_returns):
                content = "Tool call rejected"
                yield ResponseChunk(content=content, agent_id=self.agent_id)
                yield Response(content=content, agent_id=self.agent_id)
                break  # end of agent turn

            turn += 1

            if max_turns is not None and turn >= max_turns:
                return

    async def _execute_tool(self, call: ToolCallPart) -> AsyncIterator[AgentEvent | ToolReturnPart]:
        tool_name = call.tool_name
        tool_args = call.args_as_dict()

        rejected = False

        if tool_name not in self.tool_names:
            content = f"Unknown tool name: {tool_name}"
        else:
            approval = ApprovalRequest(tool_name=tool_name, tool_args=tool_args, agent_id=self.agent_id)
            yield approval

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
                    case "ipybox_reset":
                        content = await self._ipybox_reset()
                        yield ToolOutput(content=content, agent_id=self.agent_id)
                    case "subagent_task":
                        async for task_event in self._execute_subagent_task(
                            prompt=tool_args["prompt"],
                            max_turns=tool_args.get("max_turns", 100),
                        ):
                            yield task_event
                            match task_event:
                                case ToolOutput():
                                    content = task_event.content
                    case _:
                        content = await self._call_mcp_tool(tool_name, tool_args)
                        yield ToolOutput(content=content, agent_id=self.agent_id)

        yield ToolReturnPart(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            content=content,
            metadata={"rejected": rejected},
        )

    async def _execute_subagent_task(self, prompt: str, max_turns: int) -> AsyncIterator[AgentEvent]:
        subagent_config = self._config.for_subagent(agent_id=f"sub-{uuid.uuid4().hex[:4]}")
        subagent = Agent(
            config=subagent_config,
            sandbox=self._sandbox,
            sandbox_config=self._sandbox_config,
            session_store=self._session_store,
        )
        runner = _SubagentRunner(subagent=subagent, semaphore=self._subagent_semaphore)

        last_response = ""
        try:
            async for item in runner.stream(prompt, max_turns=max_turns):
                yield item
                match item:
                    case Response(content=content):
                        last_response = content
        except Exception as e:
            yield ToolOutput(content=f"Subagent error: {e}", agent_id=self.agent_id)
            return

        yield ToolOutput(content=last_response, agent_id=self.agent_id)

    async def _ipybox_execute_ipython_cell(
        self, code: str
    ) -> AsyncIterator[ApprovalRequest | CodeExecutionOutputChunk | CodeExecutionOutput]:
        try:
            async with self._code_executor_lock:
                async for item in self._code_executor.stream(code, timeout=self._execution_timeout, chunks=True):
                    match item:
                        case ipybox.ApprovalRequest(
                            server_name=server_name,
                            tool_name=tool_name,
                            tool_args=tool_args,
                        ):
                            ptc_request = ApprovalRequest(
                                tool_name=f"{server_name}_{tool_name}",  # type: ignore[has-type]
                                tool_args=tool_args,  # type: ignore[has-type]
                                agent_id=self.agent_id,
                            )
                            yield ptc_request
                            if await ptc_request.approved():
                                await item.accept()
                            else:
                                await item.reject()
                        case ipybox.CodeExecutionChunk(text=text):
                            yield CodeExecutionOutputChunk(text=text, agent_id=self.agent_id)  # type: ignore[has-type]
                        case ipybox.CodeExecutionResult(text=text, images=images):
                            yield CodeExecutionOutput(text=text, images=images, agent_id=self.agent_id)  # type: ignore[has-type]
        except Exception as e:
            yield CodeExecutionOutputChunk(text=str(e), agent_id=self.agent_id)
            yield CodeExecutionOutput(text=str(e), images=[], agent_id=self.agent_id)

    async def _ipybox_reset(self) -> str:
        try:
            async with self._code_executor_lock:
                await self._code_executor.reset()
                return "Kernel reset successfully."
        except Exception as e:
            return f"Kernel reset failed: {str(e)}"

    async def _call_mcp_tool(self, tool_name: str, tool_args: dict[str, object]) -> ToolResult:
        try:
            mcp_server = self._tool_mapping[tool_name]
            return await mcp_server.direct_call_tool(
                name=tool_name.removeprefix(f"{mcp_server.tool_prefix}_"),
                args=tool_args,
            )
        except Exception as e:
            return f"MCP tool call failed: {str(e)}"
