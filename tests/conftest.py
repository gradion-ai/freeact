import json
import tempfile
import types
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, DeltaToolCall, FunctionModel

from freeact.agent import Agent, ApprovalRequest, CodeExecutionOutput, Response, ToolOutput
from freeact.agent.config import Config
from freeact.agent.config.config import _ConfigPaths
from freeact.agent.core import ResponseChunk, Thoughts, ThoughtsChunk

DeltaToolCalls = dict[int, DeltaToolCall]
DeltaThinkingCalls = dict[int, DeltaThinkingPart]
CodeExecFunction = Callable[..., AsyncIterator[ApprovalRequest | CodeExecutionOutput]]


# Low-level utilities


def get_tool_return_parts(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    """Get ToolReturnParts if the last ModelRequest contains only tool returns."""
    match messages:
        case [*_, ModelRequest(parts=parts)] if all(isinstance(p, ToolReturnPart) for p in parts):
            return list(parts)
        case _:
            return []


# Stream function creation


def create_stream_function(
    tool_name: str,
    tool_args: dict[str, Any],
    final_text: str = "Done",
) -> Any:
    """Create a `FunctionModel` stream function that yields a tool call, then final text."""

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if get_tool_return_parts(messages):
            yield final_text
        else:
            yield {
                0: DeltaToolCall(
                    name=tool_name,
                    json_args=json.dumps(tool_args),
                    tool_call_id="call_1",
                )
            }

    return stream_function


# Agent creation


def _create_test_config(
    stream_function: Any,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    execution_timeout: float | None = 300,
    approval_timeout: float | None = None,
) -> Config:
    """Create a Config for test agents with a temporary working directory."""
    tmp_dir = Path(tempfile.mkdtemp())
    freeact_dir = _ConfigPaths(tmp_dir).freeact_dir
    freeact_dir.mkdir()
    (freeact_dir / "config.json").write_text(json.dumps({"model": "test"}))
    config = Config(working_dir=tmp_dir)
    config.model = FunctionModel(stream_function=stream_function)
    config.model_settings = {}
    config.mcp_servers = mcp_servers if mcp_servers is not None else {}
    config.execution_timeout = execution_timeout
    config.approval_timeout = approval_timeout
    return config


@asynccontextmanager
async def _mock_code_executor():
    """No-op async context manager to replace heavy CodeExecutor."""
    yield


@asynccontextmanager
async def patched_agent(
    stream_function,
    code_exec_function: CodeExecFunction | None = None,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
    execution_timeout: float | None = 300,
    approval_timeout: float | None = None,
):
    """Context manager that creates and yields a patched agent with mocked code execution."""
    config = _create_test_config(
        stream_function,
        mcp_servers=mcp_servers,
        execution_timeout=execution_timeout,
        approval_timeout=approval_timeout,
    )
    agent = Agent(config=config)
    agent._code_executor = _mock_code_executor()
    if code_exec_function is not None:
        agent._ipybox_execute_ipython_cell = types.MethodType(code_exec_function, agent)  # type: ignore[method-assign]
    async with agent:
        yield agent


# Agent streaming utilities


@dataclass
class StreamResults:
    """Container for collected stream events."""

    approvals: list[ApprovalRequest] = field(default_factory=list)
    code_outputs: list[CodeExecutionOutput] = field(default_factory=list)
    tool_outputs: list[ToolOutput] = field(default_factory=list)
    responses: list[Response] = field(default_factory=list)
    response_chunks: list[ResponseChunk] = field(default_factory=list)
    thoughts: list[Thoughts] = field(default_factory=list)
    thoughts_chunks: list[ThoughtsChunk] = field(default_factory=list)
    all_events: list[Any] = field(default_factory=list)


async def collect_stream(
    agent: Agent,
    prompt: str,
    approve_function: Callable[[ApprovalRequest], bool] = lambda _: True,
    max_turns: int | None = None,
) -> StreamResults:
    """Collect all events from agent.stream(), auto-approving with approve_function."""
    results = StreamResults()
    async for event in agent.stream(prompt, max_turns=max_turns):
        results.all_events.append(event)
        match event:
            case ApprovalRequest() as req:
                results.approvals.append(req)
                req.approve(approve_function(req))
            case CodeExecutionOutput() as out:
                results.code_outputs.append(out)
            case ToolOutput() as out:
                results.tool_outputs.append(out)
            case Response() as resp:
                results.responses.append(resp)
            case ResponseChunk() as chunk:
                results.response_chunks.append(chunk)
            case Thoughts() as thought:
                results.thoughts.append(thought)
            case ThoughtsChunk() as chunk:
                results.thoughts_chunks.append(chunk)
    return results
