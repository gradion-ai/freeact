import json
import types
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from freeact.agent import Agent, ApprovalRequest, CodeExecutionOutput, Response, ToolOutput

DeltaToolCalls = dict[int, DeltaToolCall]
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


@asynccontextmanager
async def _mock_code_executor():
    """No-op async context manager to replace heavy CodeExecutor."""
    yield


@asynccontextmanager
async def patched_agent(
    stream_function,
    code_exec_function: CodeExecFunction | None = None,
    mcp_servers: dict[str, Any] | None = None,
):
    """Context manager that creates and yields a patched agent with mocked code execution."""
    agent = Agent(
        model=FunctionModel(stream_function=stream_function),
        model_settings={},
        system_prompt="Test system prompt",
        mcp_servers=mcp_servers or {},
    )
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


async def collect_stream(
    agent: Agent,
    prompt: str,
    approve_function: Callable[[ApprovalRequest], bool] = lambda _: True,
) -> StreamResults:
    """Collect all events from agent.stream(), auto-approving with approve_function."""
    results = StreamResults()
    async for event in agent.stream(prompt):
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
    return results
