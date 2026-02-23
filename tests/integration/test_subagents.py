import json
from collections.abc import AsyncIterator

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall

from freeact.agent import ApprovalRequest, CodeExecutionOutput, Response, ToolOutput
from freeact.agent.events import AgentEvent, ResponseChunk
from tests.helpers import (
    DeltaToolCalls,
    collect_stream,
    create_stream_function,
    create_task_stream_function,
    get_tool_return_parts,
    unpatched_agent,
)

# ---------------------------------------------------------------------------
# Step 1: Agent identity
# ---------------------------------------------------------------------------


class TestAgentIdentity:
    """Agent ID generation and AgentEvent base class."""

    @pytest.mark.asyncio
    async def test_agent_has_default_id(self):
        """Agent uses 'main' as default agent_id."""

        async def noop(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
            yield "hello"

        async with unpatched_agent(noop) as agent:
            assert agent.agent_id == "main"

    @pytest.mark.asyncio
    async def test_events_carry_agent_id(self):
        """All yielded events are AgentEvent instances with the agent's agent_id."""

        async def noop(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
            yield "hello"

        async with unpatched_agent(noop) as agent:
            results = await collect_stream(agent, "test")
            assert len(results.all_events) > 0
            for event in results.all_events:
                assert isinstance(event, AgentEvent), f"{type(event).__name__} is not an AgentEvent"
                assert event.agent_id == agent.agent_id


# ---------------------------------------------------------------------------
# Step 2: max_turns
# ---------------------------------------------------------------------------


class TestMaxTurns:
    """max_turns parameter on stream() limits agentic turns."""

    @pytest.mark.asyncio
    async def test_max_turns_limits_parent(self):
        """Parent with max_turns=1 stops after 1 tool-execution round."""
        turn_count = 0

        async def always_call_tool(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls]:
            nonlocal turn_count
            turn_count += 1
            yield {
                0: DeltaToolCall(
                    name="ipybox_execute_ipython_cell",
                    json_args=json.dumps({"code": f"print('turn {turn_count}')"}),
                    tool_call_id=f"call_{turn_count}",
                )
            }

        async with unpatched_agent(always_call_tool) as agent:
            results = await collect_stream(agent, "test", max_turns=1)
            assert len(results.code_outputs) == 1

    @pytest.mark.asyncio
    async def test_no_max_turns_completes_normally(self):
        """Without max_turns, agent completes when model stops calling tools."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('done')"},
        )

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test")
            assert len(results.code_outputs) == 1
            assert any(r.content == "Done" for r in results.responses)


# ---------------------------------------------------------------------------
# Steps 3-6: Task tool and subagent lifecycle
# ---------------------------------------------------------------------------


class TestTaskExecution:
    """Subagent spawning via task tool -- full lifecycle tests."""

    @pytest.mark.asyncio
    async def test_task_returns_subagent_response(self):
        """Parent calls task tool, subagent returns text, parent gets ToolOutput."""
        async with unpatched_agent(create_task_stream_function("Hello from subagent")) as agent:
            results = await collect_stream(agent, "run a subtask")

            task_outputs = [e for e in results.all_events if isinstance(e, ToolOutput)]
            assert any("Hello from subagent" in str(out.content) for out in task_outputs)
            assert any(r.content == "Done" for r in results.responses)

    @pytest.mark.asyncio
    async def test_subagent_events_have_different_agent_id(self):
        """Subagent events carry a different agent_id than parent events."""
        async with unpatched_agent(create_task_stream_function()) as agent:
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
    async def test_tool_output_carries_parent_id(self):
        """The ToolOutput from the task carries the parent's agent_id."""
        async with unpatched_agent(create_task_stream_function("Sub result")) as agent:
            results = await collect_stream(agent, "test")

            task_tool_outputs = [
                e for e in results.all_events if isinstance(e, ToolOutput) and e.agent_id == agent.agent_id
            ]
            assert len(task_tool_outputs) == 1
            assert "Sub result" in str(task_tool_outputs[0].content)

    @pytest.mark.asyncio
    async def test_subagent_has_no_task_tool(self):
        """Subagent does not have the task tool (no nesting)."""
        seen_tool_names: list[set[str]] = []

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = {t.name for t in info.function_tools}
            seen_tool_names.append(tool_names)
            if get_tool_return_parts(messages):
                yield "Done"
            elif "subagent_task" in tool_names:
                yield {
                    0: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": "check tools"}),
                        tool_call_id="call_task",
                    )
                }
            else:
                yield "Subagent here"

        async with unpatched_agent(stream_function) as agent:
            await collect_stream(agent, "test")

            # First call is parent (has "subagent_task"), last call is subagent (no "subagent_task")
            assert "subagent_task" in seen_tool_names[0]
            # Find the subagent's tool set (any call without "subagent_task")
            subagent_tool_sets = [ts for ts in seen_tool_names if "subagent_task" not in ts]
            assert len(subagent_tool_sets) >= 1
            # Subagent should still have ipybox tools
            assert "ipybox_execute_ipython_cell" in subagent_tool_sets[0]

    @pytest.mark.asyncio
    async def test_task_approval_rejected(self):
        """Rejecting the task tool approval prevents subagent from running."""

        def reject_task(req: ApprovalRequest) -> bool:
            return req.tool_name != "subagent_task"

        async with unpatched_agent(create_task_stream_function("Should not appear")) as agent:
            results = await collect_stream(agent, "test", approve_function=reject_task)

            # Subagent response should not appear in any event
            subagent_responses = [
                e for e in results.all_events if isinstance(e, Response) and "Should not appear" in e.content
            ]
            assert len(subagent_responses) == 0

            # Agent turn should end with rejection
            assert any(r.content == "Tool call rejected" for r in results.responses)


class TestSubagentCodeExecution:
    """Subagent executes real code in its own ipybox kernel."""

    @pytest.mark.asyncio
    async def test_subagent_executes_code(self):
        """Subagent executes Python code and output flows back through parent."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [t.name for t in info.function_tools]
            if get_tool_return_parts(messages):
                yield "Done"
            elif "subagent_task" in tool_names:
                yield {
                    0: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": "Calculate 99"}),
                        tool_call_id="call_task",
                    )
                }
            else:
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "x = 99; print(x)"}),
                        tool_call_id="call_exec",
                    )
                }

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test")

            # Should have code execution output with "99"
            code_outputs = [e for e in results.all_events if isinstance(e, CodeExecutionOutput)]
            assert any("99" in (out.text or "") for out in code_outputs)

    @pytest.mark.asyncio
    async def test_subagent_approval_bubbles_up(self):
        """Subagent approval requests appear in the parent's event stream."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [t.name for t in info.function_tools]
            if get_tool_return_parts(messages):
                yield "Done"
            elif "subagent_task" in tool_names:
                yield {
                    0: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": "Run code"}),
                        tool_call_id="call_task",
                    )
                }
            else:
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print('hi')"}),
                        tool_call_id="call_exec",
                    )
                }

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test")

            # Should have approval requests from both parent (task) and subagent (ipybox)
            approval_names = [a.tool_name for a in results.approvals]
            assert "subagent_task" in approval_names
            assert "ipybox_execute_ipython_cell" in approval_names

    @pytest.mark.asyncio
    async def test_subagent_events_keep_subagent_corr_ids(self):
        """Subagent-originated events keep their own corr_id instead of parent's task corr_id."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [t.name for t in info.function_tools]
            if get_tool_return_parts(messages):
                yield "Done"
            elif "subagent_task" in tool_names:
                yield {
                    0: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": "Run code"}),
                        tool_call_id="call_task",
                    )
                }
            else:
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print('hi')"}),
                        tool_call_id="call_exec",
                    )
                }

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test")

            parent_task_approvals = [a for a in results.approvals if a.tool_name == "subagent_task"]
            assert len(parent_task_approvals) == 1
            parent_corr_id = parent_task_approvals[0].corr_id

            subagent_approvals = [
                a
                for a in results.approvals
                if a.agent_id != agent.agent_id and a.tool_name == "ipybox_execute_ipython_cell"
            ]
            assert len(subagent_approvals) >= 1
            assert all(a.corr_id != parent_corr_id for a in subagent_approvals)

    @pytest.mark.asyncio
    async def test_subagent_kernel_is_independent(self):
        """Subagent has its own kernel -- parent kernel state is not shared."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [t.name for t in info.function_tools]
            if get_tool_return_parts(messages):
                yield "Done"
            elif "subagent_task" in tool_names:
                yield {
                    0: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": "Read parent var"}),
                        tool_call_id="call_task",
                    )
                }
            else:
                # Try to read a variable that only exists in the parent kernel
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print(type(parent_secret_var))"}),
                        tool_call_id="call_exec",
                    )
                }

        # Set up parent kernel with a variable before spawning subagent
        # We use a two-phase stream function: first set var in parent, then call task
        call_count = 0

        async def phased_stream_function(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls]:
            nonlocal call_count
            tool_names = [t.name for t in info.function_tools]

            if "subagent_task" not in tool_names:
                # Subagent: try to access parent's variable
                if get_tool_return_parts(messages):
                    yield "Subagent done"
                else:
                    yield {
                        0: DeltaToolCall(
                            name="ipybox_execute_ipython_cell",
                            json_args=json.dumps({"code": "print(parent_secret_var)"}),
                            tool_call_id="call_read",
                        )
                    }
                return

            call_count += 1
            tool_returns = get_tool_return_parts(messages)  # noqa: F841

            if call_count == 1:
                # Phase 1: set a variable in the parent kernel
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "parent_secret_var = 42"}),
                        tool_call_id="call_set",
                    )
                }
            elif call_count == 2:
                # Phase 2: spawn subagent that tries to read the variable
                yield {
                    0: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": "Read parent var"}),
                        tool_call_id="call_task",
                    )
                }
            else:
                yield "Parent done"

        async with unpatched_agent(phased_stream_function) as agent:
            results = await collect_stream(agent, "test")

            # The subagent's code execution should fail (NameError) because
            # parent_secret_var doesn't exist in the subagent's kernel
            subagent_code_outputs = [
                e for e in results.all_events if isinstance(e, CodeExecutionOutput) and e.agent_id != agent.agent_id
            ]
            assert len(subagent_code_outputs) >= 1
            assert any("NameError" in (out.text or "") for out in subagent_code_outputs)


class TestSubagentMaxTurns:
    """max_turns in task args limits subagent execution."""

    @pytest.mark.asyncio
    async def test_max_turns_limits_subagent(self):
        """Subagent with max_turns=1 stops after 1 tool-execution round."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [t.name for t in info.function_tools]
            if "subagent_task" in tool_names:
                if get_tool_return_parts(messages):
                    yield "Parent done"
                else:
                    yield {
                        0: DeltaToolCall(
                            name="subagent_task",
                            json_args=json.dumps({"prompt": "Loop forever", "max_turns": 1}),
                            tool_call_id="call_task",
                        )
                    }
            else:
                # Subagent: always call a tool (would loop forever without max_turns)
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print('turn')"}),
                        tool_call_id="call_loop",
                    )
                }

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test")

            # Subagent should have executed exactly 1 code block
            subagent_code_outputs = [
                e for e in results.all_events if isinstance(e, CodeExecutionOutput) and e.agent_id != agent.agent_id
            ]
            assert len(subagent_code_outputs) == 1


class TestSubagentErrors:
    """Error handling during subagent execution."""

    @pytest.mark.asyncio
    async def test_subagent_exception_returns_error_in_tool_output(self):
        """Subagent exception is returned as error text in parent's ToolOutput."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [t.name for t in info.function_tools]
            if "subagent_task" in tool_names:
                if get_tool_return_parts(messages):
                    yield "Parent done"
                else:
                    yield {
                        0: DeltaToolCall(
                            name="subagent_task",
                            json_args=json.dumps({"prompt": "Crash please"}),
                            tool_call_id="call_task",
                        )
                    }
            else:
                # Subagent model raises an exception
                raise RuntimeError("Subagent model crashed")
                yield  # make it an async generator  # noqa: E501

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test")

            # Parent should get a ToolOutput with the error message
            task_tool_outputs = [
                e for e in results.all_events if isinstance(e, ToolOutput) and e.agent_id == agent.agent_id
            ]
            assert len(task_tool_outputs) == 1
            assert "Subagent error" in str(task_tool_outputs[0].content)


class TestParallelTasks:
    """Multiple task tool calls run concurrently."""

    @pytest.mark.asyncio
    async def test_parallel_task_execution(self):
        """Two parallel task calls both complete and return results."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [t.name for t in info.function_tools]
            if "subagent_task" in tool_names:
                if get_tool_return_parts(messages):
                    yield "Parent done"
                else:
                    # Spawn two parallel tasks
                    yield {
                        0: DeltaToolCall(
                            name="subagent_task",
                            json_args=json.dumps({"prompt": "Task A"}),
                            tool_call_id="call_a",
                        ),
                        1: DeltaToolCall(
                            name="subagent_task",
                            json_args=json.dumps({"prompt": "Task B"}),
                            tool_call_id="call_b",
                        ),
                    }
            else:
                # Subagent: respond with text identifying the task
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print('parallel task done')"}),
                        tool_call_id="call_exec",
                    )
                }

        async with unpatched_agent(stream_function) as agent:
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
