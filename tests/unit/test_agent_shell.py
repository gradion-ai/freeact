from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import ipybox
import pytest

from freeact.agent.call import GenericCall, ShellAction
from freeact.agent.events import ApprovalRequest
from tests.helpers import collect_stream, create_stream_function, patched_agent


def _cell_stream(code: str) -> Any:
    return create_stream_function(tool_name="ipybox_execute_ipython_cell", tool_args={"code": code})


def _make_ipybox_approval(
    tool_name: str,
    tool_args: dict[str, Any],
    decisions: list[bool],
    server_name: str = "ipybox",
) -> ipybox.ApprovalRequest:
    """Create an ipybox.ApprovalRequest with a tracking respond callback."""

    async def _respond(decision: bool) -> None:
        decisions.append(decision)

    return ipybox.ApprovalRequest(
        server_name=server_name,
        tool_name=tool_name,
        tool_args=tool_args,
        respond=_respond,
    )


class MockCodeExecutor:
    """Mock code executor that yields configurable items from stream().

    When an ipybox.ApprovalRequest is yielded, the executor waits for the
    decision. If rejected, it raises CodeExecutionError (matching real
    ipybox behavior where the kernel raises ApprovalRejectedError).
    """

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
            if isinstance(item, ipybox.ApprovalRequest):
                decision = await item.response()
                if not decision:
                    raise ipybox.CodeExecutionError(
                        f"ApprovalRejectedError: Approval request for {item.tool_name} rejected"
                    )
        yield ipybox.CodeExecutionResult(text=self._result_text, images=[])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ipybox_tool", "command", "cell_code", "expected_tool_name"),
    [
        ("shell", "git status", "!git status", "bash"),
        ("shell_magic", "echo hello\necho world", "%%bash\necho hello\necho world", "shell_magic"),
    ],
)
async def test_shell_command_yields_shell_approval(
    tmp_path: Path, ipybox_tool: str, command: str, cell_code: str, expected_tool_name: str
) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_approval(ipybox_tool, {"cmd": command}, decisions)

    async with patched_agent(_cell_stream(cell_code), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])
        results = await collect_stream(agent, "run it")

    shell_approvals = [a for a in results.approvals if isinstance(a.tool_call, ShellAction)]
    assert len(shell_approvals) == 1
    tc = shell_approvals[0].tool_call
    assert isinstance(tc, ShellAction)
    assert tc.tool_name == expected_tool_name
    assert tc.command == command
    assert decisions == [True]


@pytest.mark.asyncio
async def test_composite_shell_command_yields_separate_approvals(tmp_path: Path) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_approval("shell", {"cmd": "git add . && git commit -m 'msg'"}, decisions)

    async with patched_agent(_cell_stream("!git add . && git commit -m 'msg'"), tmp_dir=tmp_path) as agent:
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
@pytest.mark.parametrize(
    ("ipybox_tool", "command", "cell_code"),
    [
        ("shell", "rm -rf /", "!rm -rf /"),
        ("shell_magic", "rm -rf /", "%%bash\nrm -rf /"),
    ],
)
async def test_shell_rejection_rejects_ipybox_approval(
    tmp_path: Path, ipybox_tool: str, command: str, cell_code: str
) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_approval(ipybox_tool, {"cmd": command}, decisions)

    async with patched_agent(_cell_stream(cell_code), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])

        def deny_shell(req: ApprovalRequest) -> bool:
            return not isinstance(req.tool_call, ShellAction)

        results = await collect_stream(agent, "run it", approve_function=deny_shell)

    assert decisions == [False]
    # Agent sees the rejection error in code output
    assert len(results.code_outputs) == 1
    assert results.code_outputs[0].approval_rejected()
    # Agent turn ends with rejection response
    assert any(r.content == "Tool call rejected" for r in results.responses)


@pytest.mark.asyncio
async def test_composite_partial_rejection_rejects_ipybox_approval(tmp_path: Path) -> None:
    """Rejecting any sub-command of a composite shell command rejects the entire approval."""
    decisions: list[bool] = []
    approval = _make_ipybox_approval("shell", {"cmd": "git add . && rm -rf /"}, decisions)

    async with patched_agent(_cell_stream("!git add . && rm -rf /"), tmp_dir=tmp_path) as agent:
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
    # Agent sees the rejection error in code output
    assert len(results.code_outputs) == 1
    assert results.code_outputs[0].approval_rejected()
    # Agent turn ends with rejection response
    assert any(r.content == "Tool call rejected" for r in results.responses)


@pytest.mark.asyncio
async def test_no_shell_commands_no_extra_approvals(tmp_path: Path) -> None:
    async with patched_agent(_cell_stream("x = 1 + 2"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([])
        results = await collect_stream(agent, "run it")

    # Only the cell-level CodeAction approval, no shell approvals
    assert len(results.approvals) == 1
    assert not isinstance(results.approvals[0].tool_call, ShellAction)
    assert len(results.code_outputs) == 1


@pytest.mark.asyncio
async def test_non_shell_ptc_uses_generic_call(tmp_path: Path) -> None:
    decisions: list[bool] = []
    approval = _make_ipybox_approval("get_url", {"url": "https://example.com"}, decisions, server_name="fetch")

    async with patched_agent(_cell_stream("fetch.get_url(...)"), tmp_dir=tmp_path) as agent:
        agent._code_executor = MockCodeExecutor([approval])
        results = await collect_stream(agent, "run it")

    generic_approvals = [a for a in results.approvals if isinstance(a.tool_call, GenericCall)]
    assert len(generic_approvals) == 1
    tc = generic_approvals[0].tool_call
    assert isinstance(tc, GenericCall)
    assert tc.tool_name == "fetch_get_url"
    assert tc.ptc is True
    assert decisions == [True]
