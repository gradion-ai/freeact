from contextlib import asynccontextmanager

import ipybox
import pytest
import pytest_asyncio
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.function import FunctionModel

from freeact.agent import Agent, ApprovalRequest
from tests.conftest import (
    collect_stream,
    create_stream_function,
    patched_agent,
)
from tests.integration.mcp_server import STDIO_SERVER_PATH


@asynccontextmanager
async def unpatched_agent(stream_function):
    """Context manager that creates and yields an agent with a real code executor."""
    agent = Agent(
        model=FunctionModel(stream_function=stream_function),
        model_settings={},
        system_prompt="Test system prompt",
        mcp_servers={},
    )
    async with agent:
        yield agent


class TestIpyboxExecution:
    """Tests for ipybox_execute_ipython_cell tool with real code executor."""

    @pytest_asyncio.fixture
    async def mcp_sources_dir(self, tmp_path):
        """Pre-generate MCP sources for PTC testing."""
        await ipybox.generate_mcp_sources(
            "test",
            {"command": "python", "args": [str(STDIO_SERVER_PATH)]},
            tmp_path / "mcptools",
        )
        return tmp_path

    @pytest.mark.asyncio
    async def test_real_code_execution(self):
        """Verify ipybox_execute_ipython_cell works with a real code executor."""
        test_code = "x = 5 * 7\nprint(x)"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": test_code},
        )

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "Calculate something")

            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text is not None
            assert "35" in results.code_outputs[0].text

    @pytest.mark.asyncio
    async def test_ptc_approval_accepted(self, mcp_sources_dir):
        """Verify PTC is executed when approval request is accepted."""
        call_code = f"""
            import os
            os.chdir("{mcp_sources_dir}")
            from mcptools.test import tool_2
            tool_2.run(tool_2.Params(s="ptc_test"))
            """

        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": call_code},
        )

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test prompt")

            # 2 approvals: code execution + PTC
            assert len(results.approvals) == 2
            assert results.approvals[0].tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_name == "test_tool_2"
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text is not None
            assert "You passed to tool 2: ptc_test" in results.code_outputs[0].text

    @pytest.mark.asyncio
    async def test_ptc_approval_rejected(self, mcp_sources_dir):
        """Verify PTC rejection ends the agent turn."""
        call_code = f"""
            import os
            os.chdir("{mcp_sources_dir}")
            from mcptools.test import tool_2
            tool_2.run(tool_2.Params(s="ptc_test"))
            """

        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": call_code},
        )

        # Approve code execution, reject PTC
        def approve_function(req: ApprovalRequest) -> bool:
            return req.tool_name == "ipybox_execute_ipython_cell"

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=approve_function)

            assert len(results.approvals) == 2
            assert results.approvals[0].tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_name == "test_tool_2"
            # Agent turn ends with rejection response
            assert any(r.content == "Tool call rejected" for r in results.responses)


class TestMcpToolExecution:
    """Tests for MCP tool calls via _call_mcp_tool."""

    @pytest.fixture
    def mcp_servers(self):
        return {"test": MCPServerStdio("python", args=[str(STDIO_SERVER_PATH)])}

    @pytest.mark.asyncio
    async def test_mcp_tool_called(self, mcp_servers):
        """Verify an MCP tool is called via _call_mcp_tool."""
        stream_function = create_stream_function(
            tool_name="test_tool_2",
            tool_args={"s": "hello"},
        )

        async with patched_agent(stream_function, mcp_servers=mcp_servers) as agent:
            assert "test_tool-1" in agent.tool_names
            assert "test_tool_2" in agent.tool_names
            assert "test_tool_3" in agent.tool_names

            results = await collect_stream(agent, "call mcp tool")

            assert len(results.tool_outputs) == 1
            assert "You passed to tool 2: hello" in str(results.tool_outputs[0].content)

    @pytest.mark.asyncio
    async def test_approval_accepted(self, mcp_servers):
        """Verify tool call is executed when approval request is accepted."""
        stream_function = create_stream_function(
            tool_name="test_tool_2",
            tool_args={"s": "approved"},
        )

        async with patched_agent(stream_function, mcp_servers=mcp_servers) as agent:
            results = await collect_stream(agent, "test prompt")

            assert len(results.approvals) == 1
            assert results.approvals[0].tool_name == "test_tool_2"
            assert results.approvals[0].tool_args == {"s": "approved"}
            assert len(results.tool_outputs) == 1
            assert "You passed to tool 2: approved" in str(results.tool_outputs[0].content)

    @pytest.mark.asyncio
    async def test_approval_rejected(self, mcp_servers):
        """Verify tool call is not executed when approval request is rejected."""
        stream_function = create_stream_function(
            tool_name="test_tool_2",
            tool_args={"s": "should not run"},
        )

        async with patched_agent(stream_function, mcp_servers=mcp_servers) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=lambda _: False)

            # ToolResult is not yielded if rejected
            assert len(results.tool_outputs) == 0
            # Agent turn ends with rejection response
            assert any(r.content == "Tool call rejected" for r in results.responses)
