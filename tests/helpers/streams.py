import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, DeltaToolCall

from freeact import (
    ApprovalRequest,
    Cancelled,
    CodeExecutionOutput,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.agent import Agent

DeltaToolCalls = dict[int, DeltaToolCall]
DeltaThinkingCalls = dict[int, DeltaThinkingPart]


def get_tool_return_parts(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    """Get ToolReturnParts if the last ModelRequest contains only tool returns."""
    match messages:
        case [*_, ModelRequest(parts=parts)] if all(isinstance(p, ToolReturnPart) for p in parts):
            return list(parts)
        case _:
            return []


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


def create_task_stream_function(
    subagent_response: str = "Subagent response",
    task_args: dict[str, Any] | None = None,
) -> Any:
    """Stream function: parent spawns subagent_task, subagent responds with text."""

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        tool_names = [t.name for t in info.function_tools]
        if get_tool_return_parts(messages):
            yield "Done"
        elif "subagent_task" in tool_names:
            args = {"prompt": "task"}
            if task_args:
                args.update(task_args)
            yield {
                0: DeltaToolCall(
                    name="subagent_task",
                    json_args=json.dumps(args),
                    tool_call_id="call_task",
                )
            }
        else:
            yield subagent_response

    return stream_function


@dataclass
class StreamResults:
    """Container for collected stream events."""

    approvals: list[ApprovalRequest] = field(default_factory=list)
    cancelled: list[Cancelled] = field(default_factory=list)
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
            case Cancelled() as c:
                results.cancelled.append(c)
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
