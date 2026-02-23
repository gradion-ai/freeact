import asyncio
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import ipybox
import pytest
import pytest_asyncio
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, DeltaToolCall

from freeact.agent import Agent, ApprovalRequest, CodeExecutionOutput, Response
from freeact.agent.events import CodeExecutionOutputChunk
from freeact.agent.store import SessionStore
from freeact.tools.pytools import MCPTOOLS_DIR
from tests.helpers import (
    DeltaThinkingCalls,
    DeltaToolCalls,
    StreamResults,
    collect_stream,
    create_stream_function,
    create_test_config,
    get_tool_return_parts,
    patched_agent,
    unpatched_agent,
)
from tests.integration.mcp_server import STDIO_SERVER_PATH


def _stored_path_from_notice(content: str, working_dir: Path) -> Path:
    match = re.search(r"^Full content saved to: (.+)$", content, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("Missing stored-file reference in overflow notice")
    return working_dir / match.group(1)


def _collect_tool_return_parts(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    parts: list[ToolReturnPart] = []
    for message in messages:
        match message:
            case ModelRequest(parts=req_parts):
                for part in req_parts:
                    if isinstance(part, ToolReturnPart):
                        parts.append(part)
            case _:
                continue
    return parts


@pytest_asyncio.fixture
async def mcp_sources_dir(tmp_path):
    """Pre-generate MCP sources for PTC testing."""
    await ipybox.generate_mcp_sources(
        "test",
        {"command": "python", "args": [str(STDIO_SERVER_PATH)]},
        tmp_path / MCPTOOLS_DIR,
    )
    return tmp_path


class TestIpyboxExecution:
    """Tests for ipybox_execute_ipython_cell tool with real code executor."""

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

    @pytest.mark.asyncio
    async def test_mcp_tool_result_overflow_is_saved_to_file(self, tmp_path: Path, mcp_servers):
        """Large MCP results are replaced with notice text and stored in session tool-results."""
        stream_function = create_stream_function(
            tool_name="test_tool_2",
            tool_args={"s": "large"},
        )
        payload = "line-1\nline-2\nline-3\n" + ("x" * 300)

        async with patched_agent(
            stream_function,
            mcp_servers=mcp_servers,
            tmp_dir=tmp_path,
            session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
            tool_result_inline_max_bytes=32,
            tool_result_preview_lines=2,
        ) as agent:

            async def large_call(*args, **kwargs):
                return payload

            agent._tool_mapping["test_tool_2"].direct_call_tool = large_call
            results = await collect_stream(agent, "trigger overflow")

            assert len(results.tool_outputs) == 1
            notice = str(results.tool_outputs[0].content)
            assert "configured inline threshold (32 bytes)" in notice
            assert "Preview (first and last 2 lines):" in notice
            assert "line-1" in notice
            assert "line-2" in notice
            assert "line-3" in notice

            tool_returns = _collect_tool_return_parts(agent._message_history)
            assert len(tool_returns) == 1
            assert tool_returns[0].content == notice

            stored_path = _stored_path_from_notice(notice, tmp_path)
            assert stored_path.exists()
            assert stored_path.suffix == ".txt"
            assert stored_path.read_text(encoding="utf-8") == payload

    @pytest.mark.asyncio
    async def test_mcp_tool_result_under_threshold_stays_inline(self, tmp_path: Path, mcp_servers):
        """Small MCP results remain inline and are not replaced with overflow notices."""
        stream_function = create_stream_function(
            tool_name="test_tool_2",
            tool_args={"s": "small"},
        )
        payload = "small result"

        async with patched_agent(
            stream_function,
            mcp_servers=mcp_servers,
            tmp_dir=tmp_path,
            session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
            tool_result_inline_max_bytes=1024,
        ) as agent:

            async def small_call(*args, **kwargs):
                return payload

            agent._tool_mapping["test_tool_2"].direct_call_tool = small_call
            results = await collect_stream(agent, "no overflow")

            assert len(results.tool_outputs) == 1
            assert results.tool_outputs[0].content == payload

            tool_returns = _collect_tool_return_parts(agent._message_history)
            assert len(tool_returns) == 1
            assert tool_returns[0].content == payload


class TestToolResultOverflowInCodeExecution:
    @pytest.mark.asyncio
    async def test_code_execution_final_output_overflow_replaced_with_notice(self, tmp_path: Path):
        """Large final code-exec output is replaced with an overflow notice and stored to file."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('x')"},
        )
        payload = "alpha\nbeta\ngamma\n" + ("x" * 400)

        async def code_exec_function(self, code: str):
            yield CodeExecutionOutput(text=payload, images=[])

        async with patched_agent(
            stream_function,
            code_exec_function=code_exec_function,
            tmp_dir=tmp_path,
            session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
            tool_result_inline_max_bytes=32,
            tool_result_preview_lines=2,
        ) as agent:
            results = await collect_stream(agent, "run large output")

            assert len(results.code_outputs) == 1
            output = results.code_outputs[0]
            assert output.text is not None
            assert "configured inline threshold (32 bytes)" in output.text
            assert "Preview (first and last 2 lines):" in output.text
            assert "alpha" in output.text
            assert "beta" in output.text
            assert "gamma" in output.text
            assert output.images == []

            tool_returns = _collect_tool_return_parts(agent._message_history)
            assert len(tool_returns) == 1
            assert tool_returns[0].content == output.text

            stored_path = _stored_path_from_notice(output.text, tmp_path)
            assert stored_path.exists()
            assert stored_path.suffix == ".txt"
            assert stored_path.read_text(encoding="utf-8") == payload

    @pytest.mark.asyncio
    async def test_code_execution_chunk_does_not_create_duplicate_overflow_file(self, tmp_path: Path):
        """Large streamed chunks plus final output should persist exactly one overflow file."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('x')"},
        )
        payload_chunk = "row-1\nrow-2\nrow-3\n" + ("x" * 400) + "\n"
        payload_final = payload_chunk.rstrip("\n")

        async def code_exec_function(self, code: str):
            yield CodeExecutionOutputChunk(text=payload_chunk, agent_id=self.agent_id)
            yield CodeExecutionOutput(text=payload_final, images=[])

        async with patched_agent(
            stream_function,
            code_exec_function=code_exec_function,
            tmp_dir=tmp_path,
            session_store=SessionStore(tmp_path / ".freeact" / "sessions", "session-1"),
            tool_result_inline_max_bytes=32,
            tool_result_preview_lines=2,
        ) as agent:
            results = await collect_stream(agent, "run large chunk output")

            chunk_events = [event for event in results.all_events if isinstance(event, CodeExecutionOutputChunk)]
            assert len(chunk_events) == 1
            assert chunk_events[0].text == payload_chunk

            assert len(results.code_outputs) == 1
            output = results.code_outputs[0]
            assert output.text is not None
            assert "configured inline threshold (32 bytes)" in output.text
            stored_path = _stored_path_from_notice(output.text, tmp_path)
            assert stored_path.exists()
            assert stored_path.suffix == ".txt"
            assert stored_path.read_text(encoding="utf-8") == payload_final

            tool_results_dir = tmp_path / ".freeact" / "sessions" / "session-1" / "tool-results"
            files = list(tool_results_dir.glob("*.txt"))
            assert len(files) == 1


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

    @pytest.mark.asyncio
    async def test_thinking_none_content_ignored(self):
        """`ThinkingPartDelta` with `None` content does not cause a crash."""

        async def stream_function_with_none_thinking(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | DeltaToolCalls | DeltaThinkingCalls]:
            yield {0: DeltaThinkingPart(content="Thinking")}
            yield {0: DeltaThinkingPart(content=None)}
            yield {0: DeltaThinkingPart(content=" more.")}
            yield "Response text."

        async with patched_agent(stream_function_with_none_thinking) as agent:
            results = await collect_stream(agent, "test")

            assert len(results.thoughts) == 1
            assert results.thoughts[0].content == "Thinking more."
            assert len(results.responses) == 1


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

    @pytest.mark.asyncio
    async def test_execution_timeout_exceeded(self):
        """Code execution exceeding timeout raises error."""
        # Code that would print "completed" if it ran to completion
        slow_code = "import time; time.sleep(2); print('completed')"
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": slow_code},
        )

        config = create_test_config(
            stream_function=stream_function,
            execution_timeout=0.5,  # 500ms timeout
        )
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

        # Use a 5 second execution timeout. We delay PTC approval by 8 seconds,
        # which is longer than the timeout. If approval wait counted toward
        # timeout, this would fail.
        config = create_test_config(stream_function=stream_function, execution_timeout=5)
        agent = Agent(config=config)

        async def delayed_ptc_approve(agent, prompt):
            """Collect stream, approve code action immediately, delay PTC approval."""
            results = StreamResults()
            async for event in agent.stream(prompt):
                match event:
                    case ApprovalRequest() as req:
                        results.approvals.append(req)
                        if req.tool_name == "ipybox_execute_ipython_cell":
                            req.approve(True)
                        else:
                            await asyncio.sleep(8)
                            req.approve(True)
                    case CodeExecutionOutput() as out:
                        results.code_outputs.append(out)
                    case Response() as resp:
                        results.responses.append(resp)
            return results

        async with agent:
            results = await delayed_ptc_approve(agent, "run code")

            # Should succeed despite 8s PTC approval delay with 5s execution timeout
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

        config = create_test_config(
            stream_function=stream_function,
            execution_timeout=10,  # Generous timeout
        )
        agent = Agent(config=config)
        async with agent:
            results = await collect_stream(agent, "run code")

            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text is not None
            assert "hello" in results.code_outputs[0].text
