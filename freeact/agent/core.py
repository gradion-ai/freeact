import asyncio
import json
import logging
import uuid
from collections.abc import Sequence, Set
from dataclasses import replace
from pathlib import Path
from typing import Any, AsyncIterator

import ipybox
from aiostream.stream import merge
from ipybox.utils import arun
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

from freeact.agent._subagent import _SubagentRunner
from freeact.agent._supervisor import _ResourceSupervisor
from freeact.agent.config import Config
from freeact.agent.events import (
    AgentEvent,
    ApprovalRequest,
    CodeExecutionOutput,
    CodeExecutionOutputChunk,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.agent.store import SessionStore, ToolResultMaterializer
from freeact.tools.utils import (
    get_tool_definitions,
    load_ipybox_tool_definitions,
    load_subagent_task_tool_definitions,
)

logger = logging.getLogger("freeact")


class _MCPServerStdioFiltered(MCPServerStdio):
    """MCPServerStdio that filters out specified tools."""

    def __init__(self, excluded_tools: Set[str], **kwargs: Any):
        super().__init__(**kwargs)
        self._excluded_tools = excluded_tools

    async def list_tools(self) -> list[mcp_types.Tool]:
        tools = await super().list_tools()
        return [t for t in tools if t.name not in self._excluded_tools]


class Agent:
    """Code action agent that executes Python code and shell commands.

    Fulfills user requests by writing code and running it in a stateful
    IPython kernel provided by ipybox. Variables persist across executions.
    MCP server tools can be called in two ways:

    - JSON tool calls: MCP servers called directly via structured arguments
    - Programmatic tool calls (PTC): agent writes Python code that imports
      and calls tool APIs, auto-generated from MCP schemas (`mcptools/`)
      or user-defined (`gentools/`)

    All code actions and tool calls require approval. The `stream()` method
    yields [`ApprovalRequest`][freeact.agent.ApprovalRequest] events that
    must be resolved before execution proceeds.

    Use as an async context manager or call `start()`/`stop()` explicitly.
    """

    def __init__(
        self,
        config: Config,
        agent_id: str | None = None,
        session_id: str | None = None,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
    ):
        """Initialize the agent.

        Args:
            config: Agent configuration containing model, system prompt,
                MCP servers, kernel env, timeouts, and subagent settings.
            agent_id: Identifier for this agent instance. Defaults to
                `"main"` when not provided.
            session_id: Optional session identifier for persistence.
                If `None` and persistence is enabled, a new session ID
                is generated. If provided and persistence is enabled, that
                session ID is used. Existing session history is resumed when
                present; otherwise a new session starts with that ID.
            sandbox: Run the kernel in sandbox mode.
            sandbox_config: Path to custom sandbox configuration.

        Raises:
            ValueError: If `session_id` is provided while
                `config.enable_persistence` is `False`.
        """
        self._config = config
        if session_id is not None and not config.enable_persistence:
            raise ValueError("session_id requires config.enable_persistence=True")

        self.agent_id = agent_id or "main"
        self.model = config.model_instance
        self.model_settings = config.model_settings

        self._system_prompt = config.system_prompt
        self._execution_timeout = config.execution_timeout
        self._enable_subagents = config.enable_subagents
        self._sandbox = sandbox
        self._sandbox_config = sandbox_config

        self._session_id: str | None = None
        self._session_store: SessionStore | None = None
        if config.enable_persistence:
            self._session_id = session_id or str(uuid.uuid4())
            self._session_store = SessionStore(config.sessions_dir, self._session_id)

        self._result_materializer: ToolResultMaterializer | None = None
        if self._session_store is not None:
            self._result_materializer = ToolResultMaterializer(
                session_store=self._session_store,
                inline_max_bytes=config.tool_result_inline_max_bytes,
                preview_lines=config.tool_result_preview_lines,
                working_dir=config.working_dir,
            )

        self._mcp_servers = config.resolved_mcp_servers
        self._mcp_server_instances: dict[str, MCPServer] = {}

        self._tool_mapping: dict[str, MCPServer] = {}
        self._tool_definitions: list[ToolDefinition] = []

        self._kernel_env = config.resolved_kernel_env

        self._code_executor_lock = asyncio.Lock()
        self._code_executor = ipybox.CodeExecutor(
            kernel_env=config.resolved_kernel_env,
            sandbox=sandbox,
            sandbox_config=sandbox_config,
            images_dir=config.images_dir,
            approval_timeout=config.approval_timeout,
            log_level="ERROR",
        )

        self._message_history: list[ModelMessage] = []
        self._resource_supervisors: list[_ResourceSupervisor] = []
        self._subagent_semaphore = asyncio.Semaphore(config.max_subagents)

    @property
    def _history_agent_id(self) -> str:
        if self.agent_id.startswith("sub-"):
            return self.agent_id
        return "main"

    @property
    def session_id(self) -> str | None:
        """Session ID used by this agent, or `None` when persistence is disabled."""
        return self._session_id

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
        """Restore persisted history, start the code executor and MCP servers.

        Automatically called when entering the async context manager.
        """
        if self._resource_supervisors:
            return

        if self._session_store is not None and self._history_agent_id == "main" and not self._message_history:
            self._message_history = await arun(self._session_store.load_messages, agent_id="main")

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
        """Stop the code executor and MCP servers.

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
        """Run a single agent turn, yielding events as they occur.

        Loops through model responses and tool executions until the model
        produces a response without tool calls. All code actions and tool
        calls yield an [`ApprovalRequest`][freeact.agent.ApprovalRequest]
        that must be resolved before execution proceeds.

        Args:
            prompt: User message as text or multimodal content sequence.
            max_turns: Maximum number of tool-execution rounds. Each round
                consists of a model response followed by tool execution.
                If `None`, runs until the model stops calling tools.

        Returns:
            An async event iterator.
        """
        request = self._create_model_request(prompt)
        request_params = ModelRequestParameters(function_tools=self._tool_definitions)

        await self._append_message_history([request])

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
                        case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=delta)) if delta:
                            thinking_parts.append(delta)
                            yield ThoughtsChunk(content=delta, agent_id=self.agent_id)
                        case PartDeltaEvent(delta=TextPartDelta(content_delta=delta)) if delta:
                            response_parts.append(delta)
                            yield ResponseChunk(content=delta, agent_id=self.agent_id)

                aggregated = event_stream.get()

            thoughts = "".join(thinking_parts) if thinking_parts else None
            response = "".join(response_parts)

            await self._append_message_history([aggregated])

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

            await self._append_message_history([ModelRequest(parts=tool_returns)])

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
        corr_id = uuid.uuid4().hex[:8]

        if tool_name not in self.tool_names:
            yield ToolReturnPart(
                tool_call_id=call.tool_call_id,
                tool_name=tool_name,
                content=f"Unknown tool name: {tool_name}",
                metadata={"rejected": False},
            )
            return

        approval = ApprovalRequest(
            tool_name=tool_name,
            tool_args=tool_args,
            agent_id=self.agent_id,
            corr_id=corr_id,
        )

        yield approval

        if not await approval.approved():
            yield ToolReturnPart(
                tool_call_id=call.tool_call_id,
                tool_name=tool_name,
                content="Tool call rejected",
                metadata={"rejected": True},
            )
            return

        content: ToolResult = ""
        rejected = False

        match tool_name:
            case "ipybox_execute_ipython_cell":
                async for item in self._ipybox_execute_ipython_cell(tool_args["code"]):
                    match item:
                        case ApprovalRequest():
                            yield replace(item, corr_id=corr_id)
                        case CodeExecutionOutputChunk():
                            yield replace(item, corr_id=corr_id)
                        case CodeExecutionOutput(text=text):
                            if item.ptc_rejected():
                                rejected = True
                                content = "Tool call rejected"
                                yield replace(item, corr_id=corr_id)
                                break

                            text_orig = text or ""
                            text = await self._process_tool_text(text_orig)
                            item = replace(item, corr_id=corr_id, text=text, truncated=text_orig != text)
                            content = item.format()
                            yield item
                        case _:
                            yield item
            case "ipybox_reset":
                content = await self._ipybox_reset()
                yield ToolOutput(corr_id=corr_id, agent_id=self.agent_id, content=content)
            case "subagent_task":
                async for event in self._execute_subagent_task(
                    prompt=tool_args["prompt"],
                    max_turns=tool_args.get("max_turns", 100),
                    corr_id=corr_id,
                ):
                    yield event
                    match event:
                        case ToolOutput(agent_id=agent_id, content=tool_content) if agent_id == self.agent_id:
                            content = tool_content
            case _:
                content = await self._call_mcp_tool(tool_name, tool_args)
                content = await self._process_tool_result(content)
                yield ToolOutput(content=content, agent_id=self.agent_id, corr_id=corr_id)

        yield ToolReturnPart(
            tool_call_id=call.tool_call_id,
            tool_name=tool_name,
            content=content,
            metadata={"rejected": rejected},
        )

    async def _execute_subagent_task(self, prompt: str, max_turns: int, corr_id: str) -> AsyncIterator[AgentEvent]:
        subagent_config = self._config.for_subagent()
        subagent = Agent(
            config=subagent_config,
            agent_id=f"sub-{uuid.uuid4().hex[:4]}",
            sandbox=self._sandbox,
            sandbox_config=self._sandbox_config,
            session_id=self._session_id,
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
            error_content = f"Subagent error: {e}"
            yield ToolOutput(content=error_content, agent_id=self.agent_id, corr_id=corr_id)
            return

        final_content = await self._process_tool_text(last_response)
        yield ToolOutput(content=final_content, agent_id=self.agent_id, corr_id=corr_id)

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
                                ptc=True,
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
            resolved_name = tool_name.removeprefix(f"{mcp_server.tool_prefix}_")
            result = await mcp_server.direct_call_tool(
                name=resolved_name,
                args=tool_args,
            )
            if tool_name in {"filesystem_read_text_file", "filesystem_read_multiple_files"}:
                return self._extract_file_content(result)
            return result
        except Exception as e:
            return f"MCP tool call failed: {str(e)}"

    @staticmethod
    def _extract_file_content(result: ToolResult) -> ToolResult:
        match result:
            case {"content": content} as payload if len(payload) == 1:
                return content
            case str() as raw:
                try:
                    decoded = json.loads(raw)
                except json.JSONDecodeError:
                    return result
                match decoded:
                    case {"content": content} as payload if len(payload) == 1:
                        return content
                    case _:
                        return result
            case _:
                return result

    async def _append_message_history(self, messages: list[ModelMessage]) -> None:
        if not messages:
            return

        self._message_history.extend(messages)
        if self._session_store is not None:
            await arun(
                self._session_store.append_messages,
                agent_id=self._history_agent_id,
                messages=messages,
            )

    async def _process_tool_result(self, content: ToolResult) -> ToolResult:
        if self._result_materializer is not None:
            return await arun(self._result_materializer.materialize, content)
        return content

    async def _process_tool_text(self, text: str) -> str:
        content = await self._process_tool_result(text)
        return str(content)
