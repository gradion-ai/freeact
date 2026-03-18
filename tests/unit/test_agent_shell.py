import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import ipybox
import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall

from freeact.agent.call import GenericCall, ShellAction
from freeact.agent.events import ApprovalRequest
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


def _make_ipybox_approval(
    cmd: str,
    decisions: list[bool],
) -> ipybox.ApprovalRequest:
    """Create an ipybox.ApprovalRequest for a shell command with a tracking respond callback."""

    async def _respond(decision: bool) -> None:
        decisions.append(decision)

    return ipybox.ApprovalRequest(
        server_name="ipybox",
        tool_name="shell",
        tool_args={"cmd": cmd},
        respond=_respond,
    )


def _make_ipybox_ptc_approval(
    server_name: str,
    tool_name: str,
    tool_args: dict[str, Any],
    decisions: list[bool],
) -> ipybox.ApprovalRequest:
    """Create an ipybox.ApprovalRequest for a non-shell PTC."""

    async def _respond(decision: bool) -> None:
        decisions.append(decision)

    return ipybox.ApprovalRequest(
        server_name=server_name,
        tool_name=tool_name,
        tool_args=tool_args,
        respond=_respond,
    )


class MockCodeExecutor:
    """Mock code executor that yields configurable items from stream()."""

    def __init__(self, items: list[Any], result_text: str = "ok"):
        self._items = items
        self._result_text = result_text

    def cancel(self) -> None:
        pass

    async def stream(
        self, code: str, timeout: float | None = None, chunks: bool = True
    ) -> AsyncIterator[ipybox.ApprovalRequest | ipybox.CodeExecutionChunk | ipybox.CodeExecutionResult]:
        for item in self._items:
            yield item
        yield ipybox.CodeExecutionResult(text=self._result_text, images=[])


@pytest.mark.asyncio
async def test_shell_command_yields_shell_approval(tmp_path: Path) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_approval("git status", decisions)

    async with patched_agent(_make_cell_stream("!git status"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])
        results = await collect_stream(agent, "run it")

    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 1
    tc = shell_approvals[0].tool_call
    assert isinstance(tc, ShellAction)
    assert tc.command == "git status"
    assert tc.tool_name == "bash"
    assert decisions == [True]


@pytest.mark.asyncio
async def test_composite_shell_command_yields_separate_approvals(tmp_path: Path) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_approval("git add . && git commit -m 'msg'", decisions)

    async with patched_agent(_make_cell_stream("!git add . && git commit -m 'msg'"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])
        results = await collect_stream(agent, "run it")

    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 2
    tc0 = shell_approvals[0].tool_call
    tc1 = shell_approvals[1].tool_call
    assert isinstance(tc0, ShellAction)
    assert isinstance(tc1, ShellAction)
    assert tc0.command == "git add ."
    assert tc1.command == "git commit -m 'msg'"
    assert decisions == [True]


@pytest.mark.asyncio
async def test_shell_rejection_rejects_ipybox_approval(tmp_path: Path) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_approval("rm -rf /", decisions)

    async with patched_agent(_make_cell_stream("!rm -rf /"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])

        def deny_shell(req: ApprovalRequest) -> bool:
            if isinstance(req.tool_call, ShellAction):
                return False
            return True

        await collect_stream(agent, "run it", approve_function=deny_shell)

    assert decisions == [False]


@pytest.mark.asyncio
async def test_composite_partial_rejection_rejects_ipybox_approval(tmp_path: Path) -> None:
    """Rejecting any sub-command of a composite shell command rejects the entire approval."""
    decisions: list[bool] = []
    approval = _make_ipybox_approval("git add . && rm -rf /", decisions)

    async with patched_agent(_make_cell_stream("!git add . && rm -rf /"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])

        def deny_dangerous(req: ApprovalRequest) -> bool:
            if isinstance(req.tool_call, ShellAction) and req.tool_call.command == "rm -rf /":
                return False
            return True

        results = await collect_stream(agent, "run it", approve_function=deny_dangerous)

    # First sub-command approved, but second rejected -> overall rejected
    assert decisions == [False]
    # Only the first sub-command approval was yielded before the second was rejected
    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 2


@pytest.mark.asyncio
async def test_no_shell_commands_no_extra_approvals(tmp_path: Path) -> None:
    async with patched_agent(_make_cell_stream("x = 1 + 2"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([])
        results = await collect_stream(agent, "run it")

    # Only the cell-level CodeAction approval, no shell approvals
    assert len(results.approvals) == 1
    assert not isinstance(results.approvals[0].tool_call, ShellAction)
    assert len(results.code_outputs) == 1


@pytest.mark.asyncio
async def test_non_shell_ptc_uses_generic_call(tmp_path: Path) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_ptc_approval("fetch", "get_url", {"url": "https://example.com"}, decisions)

    async with patched_agent(_make_cell_stream("fetch.get_url(...)"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])
        results = await collect_stream(agent, "run it")

    generic_approvals = [a for a in results.approvals if isinstance(a.tool_call, GenericCall)]
    assert len(generic_approvals) == 1
    tc = generic_approvals[0].tool_call
    assert isinstance(tc, GenericCall)
    assert tc.tool_name == "fetch_get_url"
    assert tc.ptc is True
    assert decisions == [True]
