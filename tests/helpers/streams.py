import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, DeltaToolCall

from freeact.agent import ApprovalRequest, CodeExecutionOutput

DeltaToolCalls = dict[int, DeltaToolCall]
DeltaThinkingCalls = dict[int, DeltaThinkingPart]
CodeExecFunction = Callable[..., AsyncIterator[ApprovalRequest | CodeExecutionOutput]]


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
