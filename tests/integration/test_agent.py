import asyncio
import json
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import ipybox
import pytest
import pytest_asyncio
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, DeltaToolCall, FunctionModel

from freeact.agent import Agent, ApprovalRequest, CodeExecutionOutput, Response
from freeact.agent.config import Config
from freeact.agent.tools.pytools import MCPTOOLS_DIR
from tests.conftest import (
    DeltaThinkingCalls,
    DeltaToolCalls,
    StreamResults,
    collect_stream,
    create_stream_function,
    get_tool_return_parts,
    patched_agent,
)
from tests.integration.mcp_server import STDIO_SERVER_PATH


def _create_unpatched_config(stream_function) -> Config:
    """Create a Config for unpatched agent tests."""
    tmp_dir = Path(tempfile.mkdtemp())
    freeact_dir = tmp_dir / ".freeact"
    freeact_dir.mkdir()
    (freeact_dir / "config.json").write_text(json.dumps({}))

    return Config(
        working_dir=tmp_dir,
        model=FunctionModel(stream_function=stream_function),
        model_settings={},
    )


@asynccontextmanager
async def unpatched_agent(stream_function):
    """Context manager that creates and yields an agent with a real code executor."""
    config = _create_unpatched_config(stream_function)
    agent = Agent(config=config)
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
            tmp_path / MCPTOOLS_DIR,
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
        return {"test": {"command": "python", "args": [str(STDIO_SERVER_PATH)]}}

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


class TestUnknownTool:
    """Tests for unknown tool handling."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_without_approval(self):
        """Unknown tool name returns error without approval request."""

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            if get_tool_return_parts(messages):
                yield "Done"
            else:
                yield {
                    0: DeltaToolCall(
                        name="nonexistent_tool",
                        json_args=json.dumps({"arg": "value"}),
                        tool_call_id="call_unknown",
                    )
                }

        async with patched_agent(stream_function) as agent:
            results = await collect_stream(agent, "test")

            # No approval request for unknown tool
            assert len(results.approvals) == 0
            # Should still get a final response
            assert len(results.responses) > 0


class TestIpyboxReset:
    """Tests for ipybox_reset tool."""

    @pytest.mark.asyncio
    async def test_ipybox_reset_success(self):
        """ipybox_reset tool resets the kernel successfully."""
        stream_function = create_stream_function(
            tool_name="ipybox_reset",
            tool_args={},
        )

        async with unpatched_agent(stream_function) as agent:
            results = await collect_stream(agent, "reset kernel")

            # Should have approval request for reset
            assert len(results.approvals) == 1
            assert results.approvals[0].tool_name == "ipybox_reset"
            # Should have tool output with success message
            assert len(results.tool_outputs) == 1
            assert "reset successfully" in str(results.tool_outputs[0].content).lower()

    @pytest.mark.asyncio
    async def test_ipybox_reset_exception(self):
        """ipybox_reset returns error message when reset fails."""
        stream_function = create_stream_function(
            tool_name="ipybox_reset",
            tool_args={},
        )

        async with unpatched_agent(stream_function) as agent:
            # Mock reset to raise an exception
            async def failing_reset():
                raise RuntimeError("Kernel crashed")

            agent._code_executor.reset = failing_reset

            results = await collect_stream(agent, "reset kernel")

            assert len(results.tool_outputs) == 1
            assert "Kernel reset failed" in str(results.tool_outputs[0].content)
            assert "Kernel crashed" in str(results.tool_outputs[0].content)


class TestMcpToolException:
    """Tests for MCP tool call exception handling."""

    @pytest.fixture
    def mcp_servers(self):
        return {"test": {"command": "python", "args": [str(STDIO_SERVER_PATH)]}}

    @pytest.mark.asyncio
    async def test_mcp_tool_exception_returns_error(self, mcp_servers):
        """MCP tool exception returns error message."""
        stream_function = create_stream_function(
            tool_name="test_tool_2",
            tool_args={"s": "test"},
        )

        async with patched_agent(stream_function, mcp_servers=mcp_servers) as agent:
            # Mock direct_call_tool to raise an exception
            async def failing_call(*args, **kwargs):
                raise RuntimeError("Connection failed")

            agent._tool_mapping["test_tool_2"].direct_call_tool = failing_call

            results = await collect_stream(agent, "test")

            assert len(results.tool_outputs) == 1
            assert "MCP tool call failed" in str(results.tool_outputs[0].content)
            assert "Connection failed" in str(results.tool_outputs[0].content)


class TestCodeExecutionException:
    """Tests for code execution exception handling."""

    @pytest.mark.asyncio
    async def test_code_execution_exception_yields_error(self):
        """Code executor exception yields error output."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "x = 1"},
        )

        async with unpatched_agent(stream_function) as agent:
            # Mock the stream method to raise an exception
            async def failing_stream(code, timeout=None, chunks=False):
                raise RuntimeError("Kernel crashed unexpectedly")
                yield  # Make it an async generator

            agent._code_executor.stream = failing_stream

            results = await collect_stream(agent, "test")

            assert len(results.code_outputs) == 1
            assert "Kernel crashed unexpectedly" in str(results.code_outputs[0].text)


class TestExtendedThinking:
    """Tests for extended thinking (ThinkingPart/ThinkingPartDelta) handling."""

    @pytest.mark.asyncio
    async def test_thinking_parts_yielded(self):
        """ThinkingPart events are captured and yielded as ThoughtsChunk/Thoughts."""

        async def stream_function_with_thinking(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls | DeltaThinkingCalls]:
            # Yield thinking parts
            yield {0: DeltaThinkingPart(content="Let me think")}
            yield {0: DeltaThinkingPart(content=" about this.")}
            # Then yield text response
            yield "Here is my answer."

        async with patched_agent(stream_function_with_thinking) as agent:
            results = await collect_stream(agent, "test")

            # Should have thinking chunks
            assert len(results.thoughts_chunks) >= 1
            # Should have final thoughts
            assert len(results.thoughts) == 1
            assert "think" in results.thoughts[0].content.lower()
            # Should have response
            assert len(results.responses) == 1
            assert "answer" in results.responses[0].content


class TestStreamingDeltas:
    """Tests for text streaming deltas (TextPartDelta) handling."""

    @pytest.mark.asyncio
    async def test_text_deltas_yielded(self):
        """Multiple text yields produce ResponseChunk events."""

        async def stream_function_with_deltas(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls]:
            # Yield text in chunks
            yield "Hello"
            yield " world"
            yield "!"

        async with patched_agent(stream_function_with_deltas) as agent:
            results = await collect_stream(agent, "test")

            # Should have multiple response chunks
            assert len(results.response_chunks) >= 1
            # Should have final response with combined text
            assert len(results.responses) == 1
            assert results.responses[0].content == "Hello world!"


class TestTimeouts:
    """Tests for execution_timeout and approval_timeout behavior."""

    @pytest_asyncio.fixture
    async def mcp_sources_dir(self, tmp_path):
        """Pre-generate MCP sources for PTC testing."""
        await ipybox.generate_mcp_sources(
            "test",
            {"command": "python", "args": [str(STDIO_SERVER_PATH)]},
            tmp_path / MCPTOOLS_DIR,
        )
        return tmp_path

    @pytest.mark.asyncio
    async def test_execution_timeout_exceeded(self):
        """Code execution exceeding timeout raises error."""
        # Code that would print "completed" if it ran to completion
        slow_code = "import time; time.sleep(2); print('completed')"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": slow_code},
        )

        config = _create_unpatched_config(stream_function)
        config.execution_timeout = 0.5  # 500ms timeout
        agent = Agent(config=config)
        async with agent:
            results = await collect_stream(agent, "run slow code")

            # Should have code output (timeout is caught and yields output)
            assert len(results.code_outputs) == 1
            # The code should NOT have completed - "completed" should not appear
            # TimeoutError has empty str() representation, so text is empty
            assert "completed" not in (results.code_outputs[0].text or "")

    @pytest.mark.asyncio
    async def test_execution_timeout_excludes_ptc_approval_wait(self, mcp_sources_dir):
        """Execution timeout does not count PTC approval waiting time."""
        # Code that calls a tool (triggering PTC approval)
        call_code = f"""
import os
os.chdir("{mcp_sources_dir}")
from mcptools.test import tool_2
tool_2.run(tool_2.Params(s="test"))
"""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": call_code},
        )

        # Use a 10 second execution timeout - generous for slow CI environments.
        # The key is that we delay PTC approval by 15 seconds, which is longer
        # than the execution timeout. If approval wait counted toward timeout,
        # this would fail.
        config = _create_unpatched_config(stream_function)
        config.execution_timeout = 10  # 10 second timeout for actual execution
        agent = Agent(config=config)

        async def delayed_ptc_approve(agent, prompt):
            """Collect stream, approve code action immediately, delay PTC approval."""
            results = StreamResults()
            async for event in agent.stream(prompt):
                match event:
                    case ApprovalRequest() as req:
                        results.approvals.append(req)
                        if req.tool_name == "ipybox_execute_ipython_cell":
                            req.approve(True)  # Approve code action immediately
                        else:
                            # Delay PTC approval by 15 seconds - longer than execution_timeout
                            # If approval wait counted toward timeout, this would fail
                            await asyncio.sleep(15)
                            req.approve(True)
                    case CodeExecutionOutput() as out:
                        results.code_outputs.append(out)
                    case Response() as resp:
                        results.responses.append(resp)
            return results

        async with agent:
            results = await delayed_ptc_approve(agent, "run code")

            # Should succeed despite 15s PTC approval delay with 10s execution timeout
            # This proves approval wait time is excluded from the timeout budget
            assert len(results.approvals) == 2
            assert results.approvals[0].tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_name == "test_tool_2"
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text is not None
            assert "You passed to tool 2: test" in results.code_outputs[0].text

    @pytest.mark.asyncio
    async def test_fast_execution_within_timeout(self):
        """Code completing within timeout succeeds."""
        fast_code = "print('hello')"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": fast_code},
        )

        config = _create_unpatched_config(stream_function)
        config.execution_timeout = 10  # Generous timeout
        agent = Agent(config=config)
        async with agent:
            results = await collect_stream(agent, "run code")

            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text is not None
            assert "hello" in results.code_outputs[0].text
