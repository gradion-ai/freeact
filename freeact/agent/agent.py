import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator, Sequence
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic_ai.direct import model_request_stream
from pydantic_ai.messages import (
    ModelRequest,
    PartDeltaEvent,
    PartStartEvent,
    SystemPromptPart,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolReturnPart,
    UserContent,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters

from freeact.agent.approvals import ApprovalGate, CancelToken
from freeact.agent.executor import ToolExecutor, interrupted_tool_return
from freeact.agent.mcp import MCPServerManager
from freeact.agent.session import Session, SessionStore
from freeact.agent.subagents import SubagentRunner
from freeact.config import ResolvedRuntime
from freeact.events import (
    AgentEvent,
    Cancelled,
    Phase,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
)

logger = logging.getLogger("freeact")


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
    yields [`ApprovalRequest`][freeact.ApprovalRequest] events that must be
    resolved before execution proceeds.

    Use as an async context manager or call `start()`/`stop()` explicitly.
    """

    def __init__(
        self,
        runtime: ResolvedRuntime,
        agent_id: str | None = None,
        session_id: str | None = None,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
        cancel_token: CancelToken | None = None,
    ):
        """Initialize the agent.

        Args:
            runtime: Resolved runtime produced by
                [`resolve()`][freeact.config.resolve].
            agent_id: Identifier for this agent instance. Defaults to
                `"main"` when not provided.
            session_id: Optional session identifier for persistence.
                If `None` and persistence is enabled, a new session ID
                is generated. If provided and persistence is enabled, that
                session ID is used. Existing session history is resumed when
                present; otherwise a new session starts with that ID.
            sandbox: Run the kernel in sandbox mode.
            sandbox_config: Path to custom sandbox configuration.
            cancel_token: Shared cancellation token. Used internally to
                propagate parent cancellation to subagents; leave unset
                otherwise.

        Raises:
            ValueError: If `session_id` is provided while persistence is
                disabled in the configuration.
        """
        if session_id is not None and not runtime.config.enable_persistence:
            raise ValueError("session_id requires enable_persistence=True")

        self.agent_id = agent_id or "main"
        self.model: str | Model = runtime.model
        self.model_settings: dict[str, Any] = runtime.model_settings

        self._runtime = runtime
        self._system_prompt = runtime.system_prompt
        self._cancel = cancel_token or CancelToken()
        self._started = False

        self._session_id: str | None = None
        store: SessionStore | None = None
        if runtime.config.enable_persistence:
            self._session_id = session_id or str(uuid.uuid4())
            store = SessionStore(runtime.workspace.sessions_dir, self._session_id)

        self._session = Session(
            agent_id=self.agent_id,
            store=store,
            working_dir=runtime.working_dir,
            inline_max_bytes=runtime.config.tool_result_inline_max_bytes,
            preview_chars=runtime.config.tool_result_preview_chars,
        )

        self._gate = ApprovalGate(
            agent_id=self.agent_id,
            cancel=self._cancel,
            timeout=runtime.approval_timeout,
        )

        self._mcp = MCPServerManager(runtime.mcp_servers)

        subagents: SubagentRunner | None = None
        if runtime.enable_subagents:
            subagents = SubagentRunner(
                runtime=runtime,
                agent_id=self.agent_id,
                session_id=self._session_id,
                session=self._session,
                cancel=self._cancel,
                sandbox=sandbox,
                sandbox_config=sandbox_config,
            )

        self._executor = ToolExecutor(
            agent_id=self.agent_id,
            runtime=runtime,
            gate=self._gate,
            session=self._session,
            mcp=self._mcp,
            cancel=self._cancel,
            subagents=subagents,
            sandbox=sandbox,
            sandbox_config=sandbox_config,
        )

    @property
    def runtime(self) -> ResolvedRuntime:
        """Resolved runtime this agent was constructed with."""
        return self._runtime

    @property
    def session_id(self) -> str | None:
        """Session ID used by this agent, or `None` when persistence is disabled."""
        return self._session_id

    @property
    def tool_names(self) -> list[str]:
        """Names of all registered tools (ipybox tools and MCP server tools)."""
        return self._executor.tool_names

    def cancel(self) -> None:
        """Cancel the current agent turn.

        Sets the cancellation token and interrupts any running kernel
        execution. The active `stream()` call will stop at the next phase
        boundary and yield a [`Cancelled`][freeact.Cancelled] event.
        """
        self._cancel.set()
        self._executor.cancel_kernel()

    async def __aenter__(self) -> "Agent":
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    async def start(self) -> None:
        """Restore persisted history, start the code executor and MCP servers.

        Automatically called when entering the async context manager.
        """
        if self._started:
            return

        await self._session.load()

        try:
            await asyncio.gather(self._executor.start(), self._mcp.start())
        except Exception:
            await asyncio.gather(self._executor.stop(), self._mcp.stop(), return_exceptions=True)
            raise

        self._started = True

    async def stop(self) -> None:
        """Stop the code executor and MCP servers.

        Automatically called when exiting the async context manager.
        """
        if not self._started:
            return
        self._started = False

        results = await asyncio.gather(self._executor.stop(), self._mcp.stop(), return_exceptions=True)
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise ExceptionGroup("Multiple errors while stopping agent resources", errors)

    async def stream(
        self,
        prompt: str | Sequence[UserContent],
        max_turns: int | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run a single agent turn, yielding events as they occur.

        Loops through model responses and tool executions until the model
        produces a response without tool calls. All code actions and tool
        calls yield an [`ApprovalRequest`][freeact.ApprovalRequest] that
        must be resolved before execution proceeds.

        Args:
            prompt: User message as text or multimodal content sequence.
            max_turns: Maximum number of tool-execution rounds. Each round
                consists of a model response followed by tool execution.
                If `None`, runs until the model stops calling tools.

        Returns:
            An async event iterator.
        """
        if not self.agent_id.startswith("sub-"):
            self._cancel.clear()

        turn_history_start = len(self._session)
        turn_stream = self._stream_turn(prompt, max_turns)

        try:
            async for event in turn_stream:
                yield event
        except Exception:
            # Rollback is exclusively for turn exceptions; cancellation
            # keeps (and repairs) history so sessions stay resumable.
            rollback_count = len(self._session) - turn_history_start
            if rollback_count > 0:
                try:
                    await self._session.rollback(rollback_count)
                except Exception:
                    logger.exception("Failed to rollback message history after turn error")
            raise
        finally:
            # Deterministically close the turn stream (async for does not
            # close its iterator on early exit), so abandonment propagates
            # into tool execution and resolves pending approvals.
            await turn_stream.aclose()

    async def _stream_turn(
        self,
        prompt: str | Sequence[UserContent],
        max_turns: int | None,
    ) -> AsyncGenerator[AgentEvent, None]:
        request = self._create_model_request(prompt)
        request_params = ModelRequestParameters(function_tools=self._executor.tool_definitions)

        await self._session.append([request])

        turn = 0

        while True:
            if self._cancel.is_set():
                yield Cancelled(agent_id=self.agent_id, phase=Phase.BETWEEN_TURNS)
                return

            thinking_parts: list[str] = []
            response_parts: list[str] = []

            async with model_request_stream(
                self.model,
                self._session.messages,
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
                    if self._cancel.is_set():
                        break

                aggregated = event_stream.get()

            thoughts = "".join(thinking_parts) if thinking_parts else None
            response = "".join(response_parts)

            await self._session.append([aggregated])

            if thoughts:
                yield Thoughts(content=thoughts, agent_id=self.agent_id)

            if response:
                yield Response(content=response, agent_id=self.agent_id)

            if self._cancel.is_set():
                if aggregated.tool_calls:
                    synthetic_returns = [interrupted_tool_return(c) for c in aggregated.tool_calls]
                    await self._session.append([ModelRequest(parts=synthetic_returns)])
                yield Cancelled(agent_id=self.agent_id, phase=Phase.LLM_STREAMING)
                return

            if not aggregated.tool_calls:
                return

            tool_returns: list[ToolReturnPart] = []
            media_parts: list[UserPromptPart] = []

            execution = self._executor.run(aggregated.tool_calls)
            try:
                async for item in execution:
                    match item:
                        case ToolReturnPart():
                            tool_returns.append(item)
                        case UserPromptPart():
                            media_parts.append(item)
                        case _:
                            yield item
                    if self._cancel.is_set():
                        break
            finally:
                # Closing the execution stream propagates GeneratorExit into
                # per-call generators, rejecting any still-pending approvals.
                await execution.aclose()

            # Synthetic returns for tools that didn't complete
            returned_ids = {tr.tool_call_id for tr in tool_returns}
            for call in aggregated.tool_calls:
                if call.tool_call_id not in returned_ids:
                    tool_returns.append(interrupted_tool_return(call))

            request_parts: list[ToolReturnPart | UserPromptPart] = list(tool_returns)
            request_parts.extend(media_parts)
            await self._session.append([ModelRequest(parts=request_parts)])

            if self._cancel.is_set():
                yield Cancelled(agent_id=self.agent_id, phase=Phase.TOOL_EXECUTION)
                return

            if any(tool_return.metadata.get("rejected", False) for tool_return in tool_returns):
                content = "Tool call rejected"
                yield ResponseChunk(content=content, agent_id=self.agent_id)
                yield Response(content=content, agent_id=self.agent_id)
                break

            turn += 1

            if max_turns is not None and turn >= max_turns:
                return

    def _create_model_request(self, user_prompt: str | Sequence[UserContent]) -> ModelRequest:
        parts: list[SystemPromptPart | UserPromptPart] = []

        if not self._session.messages:
            parts.append(SystemPromptPart(content=self._system_prompt))
        parts.append(UserPromptPart(content=user_prompt))

        return ModelRequest(parts=parts)
