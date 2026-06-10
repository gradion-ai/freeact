import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

import ipybox
from aiostream.stream import merge
from pydantic_ai import BinaryContent
from pydantic_ai.mcp import ToolResult
from pydantic_ai.messages import ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.tools import ToolDefinition

from freeact.agent.approvals import ApprovalGate, CancelToken, Decision
from freeact.agent.mcp import MCPServerManager
from freeact.agent.session import Session
from freeact.agent.shell import split_composite_command
from freeact.agent.supervisor import ResourceSupervisor
from freeact.agent.tooldefs import load_ipybox_tool_definitions, load_subagent_task_tool_definitions
from freeact.config import ResolvedRuntime
from freeact.events import (
    AgentEvent,
    ApprovalRequest,
    CodeExecutionOutput,
    CodeExecutionOutputChunk,
    ToolOutput,
)
from freeact.toolcalls import GenericCall, ShellAction, ToolCall

if TYPE_CHECKING:
    from freeact.agent.subagents import SubagentRunner

logger = logging.getLogger("freeact")


def interrupted_tool_return(call: ToolCallPart, content: ToolResult = "") -> ToolReturnPart:
    """Synthetic tool return for a call interrupted by cancellation."""
    return ToolReturnPart(
        tool_call_id=call.tool_call_id,
        tool_name=call.tool_name,
        content=content or "Interrupted by user",
        metadata={"interrupted": True},
    )


class ToolExecutor:
    """Routes model tool calls to their execution backends.

    Owns the kernel bridge (ipybox): code execution streaming, shell and
    PTC approval interception, the execution timeout (enforced by ipybox
    so approval wait time is excluded), and single materialization of the
    final output. Kernel access is serialized; code actions and resets
    share one kernel.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        runtime: ResolvedRuntime,
        gate: ApprovalGate,
        session: Session,
        mcp: MCPServerManager,
        cancel: CancelToken,
        subagents: "SubagentRunner | None" = None,
        sandbox: bool = False,
        sandbox_config: Path | None = None,
    ) -> None:
        self._agent_id = agent_id
        self._gate = gate
        self._session = session
        self._mcp = mcp
        self._cancel = cancel
        self._subagents = subagents
        self._execution_timeout = runtime.execution_timeout

        self._kernel_lock = asyncio.Lock()
        self._code_executor = ipybox.CodeExecutor(
            kernel_env=runtime.kernel_env,
            working_dir=runtime.working_dir,
            # Resolved path: a configured relative dir (or the `images` default)
            # anchors to working_dir, not to the embedder's process cwd.
            images_dir=runtime.images_dir,
            sandbox=sandbox,
            sandbox_config=sandbox_config,
            approval_timeout=runtime.approval_timeout,
            log_level="ERROR",
            approve_tool_calls=True,
            approve_shell_cmds=True,
            require_shell_escape=True,
        )

        self._supervisor: ResourceSupervisor | None = None
        self._builtin_tool_definitions: list[ToolDefinition] = []

    @property
    def tool_definitions(self) -> list[ToolDefinition]:
        """Built-in tool definitions plus all MCP server tool definitions."""
        return self._builtin_tool_definitions + self._mcp.tool_definitions

    @property
    def tool_names(self) -> list[str]:
        """Names of all registered tools."""
        return [tool_def.name for tool_def in self.tool_definitions]

    def cancel_kernel(self) -> None:
        """Interrupt any running kernel execution."""
        self._code_executor.cancel()

    async def start(self) -> None:
        """Start the code executor and load built-in tool definitions."""
        if self._supervisor is not None:
            return

        supervisor = ResourceSupervisor(self._code_executor, "code-executor")
        await supervisor.start()
        self._supervisor = supervisor

        self._builtin_tool_definitions = await load_ipybox_tool_definitions()
        if self._subagents is not None:
            self._builtin_tool_definitions.extend(await load_subagent_task_tool_definitions())

    async def stop(self) -> None:
        """Stop the code executor."""
        self._builtin_tool_definitions = []
        supervisor = self._supervisor
        self._supervisor = None
        if supervisor is not None:
            await supervisor.stop()

    async def run(
        self, calls: list[ToolCallPart]
    ) -> AsyncGenerator[AgentEvent | ToolReturnPart | UserPromptPart, None]:
        """Execute tool calls concurrently, yielding merged events and returns."""
        streams = [self._execute(call) for call in calls]
        merged = merge(*streams)
        async with merged.stream() as streamer:
            async for item in streamer:
                yield item

    async def _execute(self, call: ToolCallPart) -> AsyncIterator[AgentEvent | ToolReturnPart | UserPromptPart]:
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

        approval = self._gate.create(ToolCall.from_raw(tool_name, tool_args), corr_id=corr_id)
        try:
            yield approval
        except GeneratorExit:
            # Consumer abandoned the stream while this approval was pending:
            # resolve it as rejected so no waiter on the request hangs.
            self._gate.resolve_rejected(approval)
            raise

        decision = await self._gate.decide(approval)
        match decision:
            case Decision.CANCELLED:
                yield interrupted_tool_return(call)
                return
            case Decision.REJECTED | Decision.TIMED_OUT:
                yield ToolReturnPart(
                    tool_call_id=call.tool_call_id,
                    tool_name=tool_name,
                    content="Tool call rejected",
                    metadata={"rejected": True},
                )
                return
            case Decision.APPROVED:
                pass

        content: ToolResult = ""
        rejected = False

        match tool_name:
            case "ipybox_execute_ipython_cell":
                async for item in self._execute_code(tool_args["code"], corr_id):
                    yield item
                    match item:
                        case CodeExecutionOutput() if item.approval_rejected:
                            rejected = True
                            content = "Tool call rejected"
                        case CodeExecutionOutput():
                            content = item.format()
            case "ipybox_reset":
                content = await self._reset_kernel()
                yield ToolOutput(corr_id=corr_id, agent_id=self._agent_id, content=content)
            case "subagent_task" if self._subagents is not None:
                async for event in self._subagents.run_task(
                    prompt=tool_args["prompt"],
                    max_turns=tool_args.get("max_turns", 100),
                    corr_id=corr_id,
                ):
                    yield event
                    match event:
                        case ToolOutput(agent_id=agent_id, content=tool_content) if agent_id == self._agent_id:
                            content = tool_content
            case _:
                result = await self._mcp.call(tool_name, tool_args)
                if isinstance(result, BinaryContent):
                    path = tool_args.get("path", "unknown")
                    content = f"Read media: {path}"
                    yield ToolOutput(content=content, agent_id=self._agent_id, corr_id=corr_id)
                    yield UserPromptPart(content=[f"Read media: {path}", result])
                else:
                    content = await self._session.materialize(result)
                    yield ToolOutput(content=content, agent_id=self._agent_id, corr_id=corr_id)

        if self._cancel.is_set() and not rejected:
            yield interrupted_tool_return(call, content)
            return

        yield ToolReturnPart(
            tool_call_id=call.tool_call_id,
            tool_name=tool_name,
            content=content,
            metadata={"rejected": rejected},
        )

    async def _execute_code(
        self, code: str, corr_id: str
    ) -> AsyncGenerator[ApprovalRequest | CodeExecutionOutputChunk | CodeExecutionOutput, None]:
        rejected = False
        try:
            async with self._kernel_lock:
                async for item in self._code_executor.stream(code, timeout=self._execution_timeout, chunks=True):
                    match item:
                        case ipybox.ApprovalRequest(tool_name="shell", tool_args=tool_args):
                            cmd = tool_args["cmd"]  # type: ignore[has-type,index]
                            sub_rejected = False
                            for sub_cmd in split_composite_command(cmd):
                                approval = self._gate.create(
                                    ShellAction(tool_name="bash", command=sub_cmd), corr_id=corr_id
                                )
                                try:
                                    yield approval
                                except GeneratorExit:
                                    self._gate.resolve_rejected(approval)
                                    await self._reject_ipybox_approval(item)
                                    raise
                                decision = await self._gate.decide(approval)
                                if not decision.approved:
                                    sub_rejected = True
                                    rejected = rejected or decision is not Decision.CANCELLED
                                    break
                            if sub_rejected:
                                await item.reject()
                            else:
                                await item.accept()
                        case ipybox.ApprovalRequest(tool_name="shell_magic", tool_args=tool_args):
                            cmd = tool_args["cmd"]  # type: ignore[has-type,index]
                            approval = self._gate.create(
                                ShellAction(tool_name="shell_magic", command=cmd), corr_id=corr_id
                            )
                            try:
                                yield approval
                            except GeneratorExit:
                                self._gate.resolve_rejected(approval)
                                await self._reject_ipybox_approval(item)
                                raise
                            rejected = rejected or await self._decide_ipybox(approval, item)
                        case ipybox.ApprovalRequest(
                            server_name=server_name,
                            tool_name=tool_name,
                            tool_args=tool_args,
                        ):
                            approval = self._gate.create(
                                GenericCall(
                                    tool_name=f"{server_name}_{tool_name}",  # type: ignore[has-type]
                                    tool_args=tool_args,  # type: ignore[has-type]
                                    ptc=True,
                                ),
                                corr_id=corr_id,
                            )
                            try:
                                yield approval
                            except GeneratorExit:
                                self._gate.resolve_rejected(approval)
                                await self._reject_ipybox_approval(item)
                                raise
                            rejected = rejected or await self._decide_ipybox(approval, item)
                        case ipybox.CodeExecutionChunk(text=text):
                            yield CodeExecutionOutputChunk(text=text, agent_id=self._agent_id, corr_id=corr_id)  # type: ignore[has-type]
                        case ipybox.CodeExecutionResult(text=text, images=images):
                            yield await self._final_output(text, images, corr_id, rejected)  # type: ignore[has-type]
        except Exception as e:
            yield CodeExecutionOutputChunk(text=str(e), agent_id=self._agent_id, corr_id=corr_id)
            yield await self._final_output(str(e), [], corr_id, rejected)

    async def _decide_ipybox(self, approval: ApprovalRequest, item: ipybox.ApprovalRequest) -> bool:
        """Yield-free part of in-kernel approval handling; returns rejection flag.

        The caller is responsible for yielding the approval event (with
        GeneratorExit protection) BEFORE calling this. Used for the
        single-approval cases (shell magic, PTC).
        """
        decision = await self._gate.decide(approval)
        if decision.approved:
            await item.accept()
            return False
        await item.reject()
        return decision is not Decision.CANCELLED

    async def _final_output(
        self, text: str | None, images: list[Path], corr_id: str, rejected: bool
    ) -> CodeExecutionOutput:
        if rejected:
            return CodeExecutionOutput(
                text=text,
                images=images,
                agent_id=self._agent_id,
                corr_id=corr_id,
                approval_rejected=True,
            )

        materialized, truncated = await self._session.materialize_text(text or "")
        return CodeExecutionOutput(
            text=materialized,
            images=images,
            agent_id=self._agent_id,
            corr_id=corr_id,
            truncated=truncated,
        )

    async def _reset_kernel(self) -> str:
        try:
            async with self._kernel_lock:
                await self._code_executor.reset()
                return "Kernel reset successfully."
        except Exception as e:
            return f"Kernel reset failed: {str(e)}"

    @staticmethod
    async def _reject_ipybox_approval(item: ipybox.ApprovalRequest) -> None:
        # Called during generator cleanup (GeneratorExit) to ensure the
        # approval channel on the tool server is unblocked before the
        # ApprovalClient disconnects.
        try:
            await item.reject()
        except Exception:
            logger.debug("Failed to reject ipybox approval during cleanup", exc_info=True)
