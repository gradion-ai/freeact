import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall

from freeact import AgentEvent, ApprovalRequest, CodeExecutionOutput, Response, ResponseChunk, ToolOutput
from tests.helpers import (
    DeltaToolCalls,
    collect_stream,
    create_stream_function,
    create_task_stream_function,
    get_tool_return_parts,
    unpatched_agent,
)


async def noop_stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
    yield "hello"


def exec_call(code: str, tool_call_id: str = "call_exec") -> DeltaToolCalls:
    return {
        0: DeltaToolCall(
            name="ipybox_execute_ipython_cell",
            json_args=json.dumps({"code": code}),
            tool_call_id=tool_call_id,
        )
    }


def task_call(prompt: str = "task") -> DeltaToolCalls:
    return {
        0: DeltaToolCall(
            name="subagent_task",
            json_args=json.dumps({"prompt": prompt}),
            tool_call_id="call_task",
        )
    }


def create_subagent_code_stream_function(
    code: str = "print('hi')",
    num_tasks: int = 1,
    task_args: dict[str, Any] | None = None,
    subagent_loops: bool = False,
) -> Any:
    """Stream function: parent spawns subagent task(s), each subagent executes `code`.

    With `subagent_loops=True` the subagent calls the code tool on every turn
    (it would loop forever without a `max_turns` limit).
    """

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        tool_names = [t.name for t in info.function_tools]
        if "subagent_task" in tool_names:
            if get_tool_return_parts(messages):
                yield "Parent done"
            else:
                yield {
                    i: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": f"Task {i}", **(task_args or {})}),
                        tool_call_id=f"call_task_{i}",
                    )
                    for i in range(num_tasks)
                }
        elif get_tool_return_parts(messages) and not subagent_loops:
            yield "Subagent done"
        else:
            yield exec_call(code)

    return stream_function


# Agent identity


@pytest.mark.asyncio
async def test_agent_has_default_id(tmp_path: Path) -> None:
    """Agent uses 'main' as default agent_id."""
    async with unpatched_agent(noop_stream_function, tmp_dir=tmp_path) as agent:
        assert agent.agent_id == "main"


@pytest.mark.asyncio
async def test_events_carry_agent_id(tmp_path: Path) -> None:
    """All yielded events are AgentEvent instances with the agent's agent_id."""
    async with unpatched_agent(noop_stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")
        assert len(results.all_events) > 0
        for event in results.all_events:
            assert isinstance(event, AgentEvent), f"{type(event).__name__} is not an AgentEvent"
            assert event.agent_id == agent.agent_id


# max_turns


@pytest.mark.asyncio
async def test_max_turns_limits_parent(tmp_path: Path) -> None:
    """Parent with max_turns=1 stops after 1 tool-execution round."""
    turn_count = 0

    async def always_call_tool(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        nonlocal turn_count
        turn_count += 1
        yield exec_call(f"print('turn {turn_count}')", tool_call_id=f"call_{turn_count}")

    async with unpatched_agent(always_call_tool, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test", max_turns=1)
        assert len(results.code_outputs) == 1


@pytest.mark.asyncio
async def test_no_max_turns_completes_normally(tmp_path: Path) -> None:
    """Without max_turns, agent completes when model stops calling tools."""
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "print('done')"},
    )

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")
        assert len(results.code_outputs) == 1
        assert any(r.content == "Done" for r in results.responses)


# Task tool and subagent lifecycle


@pytest.mark.asyncio
async def test_task_returns_subagent_response(tmp_path: Path) -> None:
    """Parent calls task tool, subagent returns text, parent gets ToolOutput."""
    async with unpatched_agent(create_task_stream_function("Hello from subagent"), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "run a subtask")

        task_outputs = [e for e in results.all_events if isinstance(e, ToolOutput)]
        assert any("Hello from subagent" in str(out.content) for out in task_outputs)
        assert any(r.content == "Done" for r in results.responses)


@pytest.mark.asyncio
async def test_subagent_events_have_different_agent_id(tmp_path: Path) -> None:
    """Subagent events carry a different agent_id than parent events."""
    async with unpatched_agent(create_task_stream_function(), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")
        parent_id = agent.agent_id

        # Collect all agent_ids from events
        agent_ids = {e.agent_id for e in results.all_events if isinstance(e, AgentEvent)}

        # Should have at least two distinct agent IDs (parent + subagent)
        assert len(agent_ids) >= 2
        assert parent_id in agent_ids
        assert any(aid.startswith("sub-") for aid in agent_ids if aid != parent_id)

        # Subagent response events should carry a different ID
        subagent_responses = [
            e for e in results.all_events if isinstance(e, (Response, ResponseChunk)) and e.agent_id != parent_id
        ]
        assert len(subagent_responses) > 0


@pytest.mark.asyncio
async def test_tool_output_carries_parent_id(tmp_path: Path) -> None:
    """The ToolOutput from the task carries the parent's agent_id."""
    async with unpatched_agent(create_task_stream_function("Sub result"), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        task_tool_outputs = [
            e for e in results.all_events if isinstance(e, ToolOutput) and e.agent_id == agent.agent_id
        ]
        assert len(task_tool_outputs) == 1
        assert "Sub result" in str(task_tool_outputs[0].content)


@pytest.mark.asyncio
async def test_subagent_has_no_task_tool(tmp_path: Path) -> None:
    """Subagent does not have the task tool (no nesting)."""
    seen_tool_names: list[set[str]] = []

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        tool_names = {t.name for t in info.function_tools}
        seen_tool_names.append(tool_names)
        if get_tool_return_parts(messages):
            yield "Done"
        elif "subagent_task" in tool_names:
            yield task_call("check tools")
        else:
            yield "Subagent here"

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        await collect_stream(agent, "test")

        # First call is parent (has "subagent_task"), last call is subagent (no "subagent_task")
        assert "subagent_task" in seen_tool_names[0]
        # Find the subagent's tool set (any call without "subagent_task")
        subagent_tool_sets = [ts for ts in seen_tool_names if "subagent_task" not in ts]
        assert len(subagent_tool_sets) >= 1
        # Subagent should still have ipybox tools
        assert "ipybox_execute_ipython_cell" in subagent_tool_sets[0]


@pytest.mark.asyncio
async def test_task_approval_rejected(tmp_path: Path) -> None:
    """Rejecting the task tool approval prevents subagent from running."""

    def reject_task(req: ApprovalRequest) -> bool:
        return req.tool_call.tool_name != "subagent_task"

    async with unpatched_agent(create_task_stream_function("Should not appear"), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test", approve_function=reject_task)

        # Subagent response should not appear in any event
        subagent_responses = [
            e for e in results.all_events if isinstance(e, Response) and "Should not appear" in e.content
        ]
        assert len(subagent_responses) == 0

        # Agent turn should end with rejection
        assert any(r.content == "Tool call rejected" for r in results.responses)


# Subagent code execution


@pytest.mark.asyncio
async def test_subagent_executes_code(tmp_path: Path) -> None:
    """Subagent executes Python code and output flows back through parent."""
    stream_function = create_subagent_code_stream_function(code="x = 99; print(x)")

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # Should have code execution output with "99"
        code_outputs = [e for e in results.all_events if isinstance(e, CodeExecutionOutput)]
        assert any("99" in (out.text or "") for out in code_outputs)


@pytest.mark.asyncio
async def test_subagent_approval_bubbles_up(tmp_path: Path) -> None:
    """Subagent approval requests appear in the parent's event stream."""
    async with unpatched_agent(create_subagent_code_stream_function(), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # Should have approval requests from both parent (task) and subagent (ipybox)
        approval_names = [a.tool_call.tool_name for a in results.approvals]
        assert "subagent_task" in approval_names
        assert "ipybox_execute_ipython_cell" in approval_names


@pytest.mark.asyncio
async def test_subagent_events_keep_subagent_corr_ids(tmp_path: Path) -> None:
    """Subagent-originated events keep their own corr_id instead of parent's task corr_id."""
    async with unpatched_agent(create_subagent_code_stream_function(), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        parent_task_approvals = [a for a in results.approvals if a.tool_call.tool_name == "subagent_task"]
        assert len(parent_task_approvals) == 1
        parent_corr_id = parent_task_approvals[0].corr_id

        subagent_approvals = [
            a
            for a in results.approvals
            if a.agent_id != agent.agent_id and a.tool_call.tool_name == "ipybox_execute_ipython_cell"
        ]
        assert len(subagent_approvals) >= 1
        assert all(a.corr_id != parent_corr_id for a in subagent_approvals)
        assert all(a.parent_corr_id == parent_corr_id for a in subagent_approvals)


@pytest.mark.asyncio
async def test_subagent_kernel_is_independent(tmp_path: Path) -> None:
    """Subagent has its own kernel -- parent kernel state is not shared."""
    parent_turn = 0

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        nonlocal parent_turn
        tool_names = [t.name for t in info.function_tools]

        if "subagent_task" not in tool_names:
            # Subagent: try to read a variable that only exists in the parent kernel
            if get_tool_return_parts(messages):
                yield "Subagent done"
            else:
                yield exec_call("print(parent_secret_var)", tool_call_id="call_read")
            return

        parent_turn += 1
        if parent_turn == 1:
            # Phase 1: set a variable in the parent kernel
            yield exec_call("parent_secret_var = 42", tool_call_id="call_set")
        elif parent_turn == 2:
            # Phase 2: spawn subagent that tries to read the variable
            yield task_call("Read parent var")
        else:
            yield "Parent done"

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # The subagent's code execution should fail (NameError) because
        # parent_secret_var doesn't exist in the subagent's kernel
        subagent_code_outputs = [
            e for e in results.all_events if isinstance(e, CodeExecutionOutput) and e.agent_id != agent.agent_id
        ]
        assert len(subagent_code_outputs) >= 1
        assert any("NameError" in (out.text or "") for out in subagent_code_outputs)


@pytest.mark.asyncio
async def test_max_turns_limits_subagent(tmp_path: Path) -> None:
    """Subagent with max_turns=1 stops after 1 tool-execution round."""
    stream_function = create_subagent_code_stream_function(
        code="print('turn')",
        task_args={"max_turns": 1},
        subagent_loops=True,
    )

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # Subagent should have executed exactly 1 code block
        subagent_code_outputs = [
            e for e in results.all_events if isinstance(e, CodeExecutionOutput) and e.agent_id != agent.agent_id
        ]
        assert len(subagent_code_outputs) == 1


# Subagent errors


@pytest.mark.asyncio
async def test_subagent_exception_returns_error_in_tool_output(tmp_path: Path) -> None:
    """Subagent exception is returned as error text in parent's ToolOutput."""

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        tool_names = [t.name for t in info.function_tools]
        if "subagent_task" in tool_names:
            if get_tool_return_parts(messages):
                yield "Parent done"
            else:
                yield task_call("Crash please")
        else:
            # Subagent model raises an exception
            raise RuntimeError("Subagent model crashed")
            yield  # make it an async generator

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # Parent should get a ToolOutput with the error message
        task_tool_outputs = [
            e for e in results.all_events if isinstance(e, ToolOutput) and e.agent_id == agent.agent_id
        ]
        assert len(task_tool_outputs) == 1
        assert "Subagent error" in str(task_tool_outputs[0].content)


# Parallel tasks


@pytest.mark.asyncio
async def test_parallel_task_execution(tmp_path: Path) -> None:
    """Two parallel task calls both complete and return results."""
    async with unpatched_agent(create_subagent_code_stream_function(num_tasks=2), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # Should have two ToolOutputs from the parent (one per task)
        task_tool_outputs = [
            e for e in results.all_events if isinstance(e, ToolOutput) and e.agent_id == agent.agent_id
        ]
        assert len(task_tool_outputs) == 2

        # Should have code execution from two different subagents
        subagent_ids = {
            e.agent_id
            for e in results.all_events
            if isinstance(e, CodeExecutionOutput) and e.agent_id != agent.agent_id
        }
        assert len(subagent_ids) == 2


@pytest.mark.asyncio
async def test_parallel_subagent_events_keep_parent_task_corr_ids(tmp_path: Path) -> None:
    """Parallel subagent events carry the owning parent task corr_id."""
    async with unpatched_agent(create_subagent_code_stream_function(num_tasks=2), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        parent_task_corr_ids = {
            approval.corr_id
            for approval in results.approvals
            if approval.agent_id == agent.agent_id and approval.tool_call.tool_name == "subagent_task"
        }
        assert len(parent_task_corr_ids) == 2

        subagent_code_outputs = [
            event
            for event in results.all_events
            if isinstance(event, CodeExecutionOutput) and event.agent_id != agent.agent_id
        ]
        assert len(subagent_code_outputs) >= 2
        assert {event.parent_corr_id for event in subagent_code_outputs} == parent_task_corr_ids
