from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import ipybox
from pydantic_ai.models.function import FunctionModel

from freeact.agent import Agent
from freeact.config import AgentSection, ResolvedRuntime, Workspace


def create_test_runtime(
    tmp_dir: Path,
    stream_function: Any | None = None,
    *,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    **section_overrides: Any,
) -> ResolvedRuntime:
    """Create a ResolvedRuntime for test agents using tmp_dir as working directory.

    Bypasses config resolution so tests control every runtime value; no
    internal MCP servers are started.
    """
    # Old-style None timeouts map to the schema's 0 = disabled/forever.
    for key in ("execution_timeout", "approval_timeout"):
        if key in section_overrides and section_overrides[key] is None:
            section_overrides[key] = 0

    section = AgentSection(model="test", model_settings={}, **section_overrides)
    model: Any = FunctionModel(stream_function=stream_function) if stream_function is not None else "test"

    return ResolvedRuntime(
        config=section,
        workspace=Workspace(working_dir=tmp_dir.resolve()),
        model=model,
        mcp_servers=mcp_servers or {},
        ptc_servers={},
        kernel_env={},
        enable_subagents=section.enable_subagents,
    )


class FakeCodeExecutor:
    """In-process stand-in for ipybox.CodeExecutor.

    Yields items produced by a `script` async generator function (called
    with the executed code), or a simple result when no script is given.
    """

    def __init__(self, script: Callable[[str], AsyncIterator[Any]] | None = None) -> None:
        self.script = script
        self.cancelled = False
        self.reset_calls = 0
        self.reset_error: Exception | None = None
        self.stream_calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> "FakeCodeExecutor":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def cancel(self) -> None:
        self.cancelled = True

    async def reset(self) -> None:
        self.reset_calls += 1
        if self.reset_error is not None:
            raise self.reset_error

    async def stream(self, code: str, timeout: float | None = None, chunks: bool = False) -> AsyncIterator[Any]:
        self.stream_calls.append({"code": code, "timeout": timeout, "chunks": chunks})
        if self.script is None:
            yield ipybox.CodeExecutionResult(text=f"executed: {code}", images=[])
            return
        async for item in self.script(code):
            yield item


class ApprovalRecorder:
    """Records accept/reject decisions made on fake ipybox approvals."""

    def __init__(self) -> None:
        self.decisions: list[bool] = []

    async def respond(self, decision: bool) -> None:
        self.decisions.append(decision)


def ipybox_shell_approval(cmd: str, recorder: ApprovalRecorder) -> ipybox.ApprovalRequest:
    """Create a real ipybox shell approval backed by a recorder."""
    return ipybox.ApprovalRequest(server_name="", tool_name="shell", tool_args={"cmd": cmd}, respond=recorder.respond)


def ipybox_shell_magic_approval(cmd: str, recorder: ApprovalRecorder) -> ipybox.ApprovalRequest:
    """Create a real ipybox shell-magic approval backed by a recorder."""
    return ipybox.ApprovalRequest(
        server_name="", tool_name="shell_magic", tool_args={"cmd": cmd}, respond=recorder.respond
    )


def ipybox_ptc_approval(
    server_name: str, tool_name: str, tool_args: dict[str, Any], recorder: ApprovalRecorder
) -> ipybox.ApprovalRequest:
    """Create a real ipybox PTC approval backed by a recorder."""
    return ipybox.ApprovalRequest(
        server_name=server_name, tool_name=tool_name, tool_args=tool_args, respond=recorder.respond
    )


@asynccontextmanager
async def patched_agent(
    stream_function: Any,
    code_executor: FakeCodeExecutor | None = None,
    *,
    tmp_dir: Path,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    session_id: str | None = None,
    **section_overrides: Any,
):
    """Create an agent whose kernel is a FakeCodeExecutor."""
    runtime = create_test_runtime(
        tmp_dir=tmp_dir,
        stream_function=stream_function,
        mcp_servers=mcp_servers,
        **section_overrides,
    )
    agent = Agent(runtime, session_id=session_id)
    agent._executor._code_executor = code_executor or FakeCodeExecutor()  # type: ignore[assignment]
    async with agent:
        yield agent


@asynccontextmanager
async def unpatched_agent(
    stream_function: Any,
    *,
    tmp_dir: Path,
    session_id: str | None = None,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    **section_overrides: Any,
):
    """Create an agent with a real ipybox code executor."""
    runtime = create_test_runtime(
        tmp_dir=tmp_dir,
        stream_function=stream_function,
        mcp_servers=mcp_servers,
        **section_overrides,
    )
    agent = Agent(runtime, session_id=session_id)
    async with agent:
        yield agent
