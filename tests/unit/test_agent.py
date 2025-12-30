from typing import Any

import pytest

from freeact.agent import ApprovalRequest, CodeExecutionOutput
from tests.conftest import (
    CodeExecFunction,
    collect_stream,
    create_stream_function,
    patched_agent,
)


def create_code_exec_function(output_text: str) -> CodeExecFunction:
    """Returns an execute function that yields a single output element."""

    async def execute(self, code: str):
        yield CodeExecutionOutput(text=output_text, images=[])

    return execute


def create_code_exec_with_approval_function(
    tool_name: str, tool_args: dict[str, Any], approved_result: str, rejected_result: str
) -> CodeExecFunction:
    """Returns an execute function that simulates a PTC approval flow."""

    async def execute(self, code: str):
        approval = ApprovalRequest(tool_name=tool_name, tool_args=tool_args)
        yield approval
        if await approval.approved():
            yield CodeExecutionOutput(text=approved_result, images=[])
        else:
            yield CodeExecutionOutput(text=rejected_result, images=[])

    return execute


class TestIpyboxExecution:
    """Tests for ipybox_execute_ipython_cell tool with mocked code executor."""

    @pytest.mark.asyncio
    async def test_ipybox_execute_ipython_cell_called(self):
        """Verify ipybox_execute_ipython_cell is called with specific code."""
        test_code = "x = 5 * 7\nprint(x)"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": test_code},
        )

        async with patched_agent(stream_function, create_code_exec_function("35")) as agent:
            results = await collect_stream(agent, "Calculate something")

            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "35"

    @pytest.mark.asyncio
    async def test_approval_accepted(self):
        """Verify tool call is executed when approval request is accepted."""
        test_code = "print('approved execution')"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": test_code},
        )

        async with patched_agent(stream_function, create_code_exec_function("approved execution")) as agent:
            results = await collect_stream(agent, "test prompt")

            assert len(results.approvals) == 1
            assert results.approvals[0].tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[0].tool_args == {"code": test_code}
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "approved execution"

    @pytest.mark.asyncio
    async def test_approval_rejected(self):
        """Verify tool call is not executed when approval request is rejected."""
        rejected_code = "print('should not run')"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": rejected_code},
        )

        async with patched_agent(stream_function, create_code_exec_function("should not be called")) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=lambda _: False)

            # CodeExecutionResult is not yielded if code execution is rejected
            assert len(results.code_outputs) == 0
            # Agent turn ends with rejection response
            assert any(r.content == "Tool call rejected" for r in results.responses)

    @pytest.mark.asyncio
    async def test_ptc_approval_accepted(self):
        """Verify PTC is executed when approval request is accepted."""
        test_code = "from test.tool_2 import Params, run; run(Params(s='ptc_approved'))"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": test_code},
        )
        code_exec_function = create_code_exec_with_approval_function(
            tool_name="test_tool_2",
            tool_args={"s": "ptc_approved"},
            approved_result="You passed to tool 2: ptc_approved",
            rejected_result="Tool call rejected",
        )

        async with patched_agent(stream_function, code_exec_function) as agent:
            results = await collect_stream(agent, "test prompt")

            assert len(results.approvals) == 2
            assert results.approvals[0].tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_name == "test_tool_2"
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "You passed to tool 2: ptc_approved"

    @pytest.mark.asyncio
    async def test_ptc_approval_rejected(self):
        """Verify PTC is not executed when approval request is rejected."""
        test_code = "from test.tool_2 import Params, run; run(Params(s='ptc_rejected'))"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": test_code},
        )
        # rejected_result must match the pattern in CodeExecutionOutput.ptc_rejected()
        code_exec_function = create_code_exec_with_approval_function(
            tool_name="test_tool_2",
            tool_args={"s": "ptc_rejected"},
            approved_result="You passed to tool 2: ptc_rejected",
            rejected_result="ToolRunnerError: Approval request for test_tool_2 rejected",
        )

        # Approve code execution, reject PTC
        def approve_function(req: ApprovalRequest) -> bool:
            return req.tool_name == "ipybox_execute_ipython_cell"

        async with patched_agent(stream_function, code_exec_function) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=approve_function)

            assert len(results.approvals) == 2
            assert results.approvals[0].tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_name == "test_tool_2"
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text is not None
            assert "ToolRunnerError: Approval request for test_tool_2 rejected" in results.code_outputs[0].text
            # Agent turn ends with rejection response
            assert any(r.content == "Tool call rejected" for r in results.responses)
