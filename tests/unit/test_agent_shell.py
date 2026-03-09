import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall

from freeact.agent.call import ShellAction
from freeact.agent.events import ApprovalRequest, CodeExecutionOutput, CodeExecutionOutputChunk
from tests.helpers.agents import collect_stream, patched_agent
from tests.helpers.streams import DeltaToolCalls, get_tool_return_parts


def _make_cell_stream(code: str) -> Any:
    """Create a stream function that yields a single ipybox_execute_ipython_cell call."""

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        if get_tool_return_parts(messages):
            yield "Done"
        else:
            yield {
                0: DeltaToolCall(
                    name="ipybox_execute_ipython_cell",
                    json_args=json.dumps({"code": code}),
                    tool_call_id="call_1",
                )
            }

    return stream_function


def _simple_exec(
    self: Any, code: str
) -> AsyncIterator[ApprovalRequest | CodeExecutionOutputChunk | CodeExecutionOutput]:
    async def _gen() -> AsyncIterator[ApprovalRequest | CodeExecutionOutputChunk | CodeExecutionOutput]:
        yield CodeExecutionOutput(text="ok", images=[], agent_id=self.agent_id)

    return _gen()


@pytest.mark.asyncio
async def test_code_action_with_no_shell_commands_yields_no_extra_approvals(tmp_path):
    code = "x = 1 + 2\nprint(x)"
    async with patched_agent(_make_cell_stream(code), code_exec_function=_simple_exec, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "run it")

    # Only the cell-level approval, no shell approvals
    assert len(results.approvals) == 1
    assert not isinstance(results.approvals[0].tool_call, ShellAction)


@pytest.mark.asyncio
async def test_code_action_with_shell_command_yields_shell_approval_request(tmp_path):
    code = "!git status"
    async with patched_agent(_make_cell_stream(code), code_exec_function=_simple_exec, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "run it")

    # Cell-level approval + shell approval
    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 1
    tc = shell_approvals[0].tool_call
    assert isinstance(tc, ShellAction)
    assert tc.command == "git status"


@pytest.mark.asyncio
async def test_shell_approval_request_has_shell_flag(tmp_path):
    code = "!pip install pandas"
    async with patched_agent(_make_cell_stream(code), code_exec_function=_simple_exec, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "run it")

    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 1
    assert isinstance(shell_approvals[0].tool_call, ShellAction)
    assert shell_approvals[0].tool_call.tool_name == "bash"


@pytest.mark.asyncio
async def test_shell_command_denied_blocks_cell_execution(tmp_path):
    code = "!rm -rf /"
    exec_called = False

    async def _tracking_exec(
        self: Any, code: str
    ) -> AsyncIterator[ApprovalRequest | CodeExecutionOutputChunk | CodeExecutionOutput]:
        nonlocal exec_called
        exec_called = True
        yield CodeExecutionOutput(text="ok", images=[], agent_id=self.agent_id)

    async with patched_agent(_make_cell_stream(code), code_exec_function=_tracking_exec, tmp_dir=tmp_path) as agent:

        def deny_shell(req: ApprovalRequest) -> bool:
            if isinstance(req.tool_call, ShellAction):
                return False
            return True

        results = await collect_stream(agent, "run it", approve_function=deny_shell)

    assert not exec_called
    # Response indicates rejection
    assert any("rejected" in r.content.lower() for r in results.responses)


@pytest.mark.asyncio
async def test_all_shell_commands_approved_cell_executes(tmp_path):
    code = "!git status\n!echo hello"
    async with patched_agent(_make_cell_stream(code), code_exec_function=_simple_exec, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "run it")

    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 2
    # Cell should have executed
    assert len(results.code_outputs) == 1


@pytest.mark.asyncio
async def test_composite_shell_commands_yield_separate_approvals(tmp_path):
    code = "!git add . && git commit -m 'msg'"
    async with patched_agent(_make_cell_stream(code), code_exec_function=_simple_exec, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "run it")

    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 2
    tc0 = shell_approvals[0].tool_call
    tc1 = shell_approvals[1].tool_call
    assert isinstance(tc0, ShellAction)
    assert isinstance(tc1, ShellAction)
    assert tc0.command == "git add ."
    assert tc1.command == "git commit -m 'msg'"
