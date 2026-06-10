import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, DeltaToolCall

from freeact.agent import Agent, ApprovalRequest, CodeExecutionOutput
from freeact.agent.call import GenericCall, ShellAction
from freeact.agent.events import CodeExecutionOutputChunk
from tests.helpers import (
    DeltaThinkingCalls,
    DeltaToolCalls,
    StreamResults,
    collect_stream,
    create_stream_function,
    patched_agent,
    unpatched_agent,
)


def create_ptc_stream_function(mcp_sources_dir: Path, s: str) -> Any:
    """Stream function that executes code calling PTC `test_tool_2` with string `s`."""
    code = "\n".join(
        [
            "import os",
            f'os.chdir("{mcp_sources_dir}")',
            "from mcptools.test import tool_2",
            f'tool_2.run(tool_2.Params(s="{s}"))',
        ]
    )
    return create_stream_function(tool_name="ipybox_execute_ipython_cell", tool_args={"code": code})


@pytest.mark.asyncio
async def test_real_code_execution(tmp_path: Path) -> None:
    """Verify ipybox_execute_ipython_cell works with a real code executor."""
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "x = 5 * 7\nprint(x)"},
    )

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "Calculate something")

        assert len(results.code_outputs) == 1
        assert results.code_outputs[0].text is not None
        assert "35" in results.code_outputs[0].text


@pytest.mark.asyncio
async def test_working_dir_reset_after_chdir(tmp_path: Path) -> None:
    """Working directory is restored after code changes it with os.chdir."""

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        turn = sum(
            1 for m in messages if isinstance(m, ModelRequest) and all(isinstance(p, ToolReturnPart) for p in m.parts)
        )
        if turn == 0:
            yield {
                0: DeltaToolCall(
                    name="ipybox_execute_ipython_cell",
                    json_args=json.dumps({"code": "import os; os.chdir('/')"}),
                    tool_call_id="call_chdir",
                )
            }
        elif turn == 1:
            yield {
                0: DeltaToolCall(
                    name="ipybox_execute_ipython_cell",
                    json_args=json.dumps({"code": "import os; print(os.getcwd())"}),
                    tool_call_id="call_getcwd",
                )
            }
        else:
            yield "Done"

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "change and check cwd")

        assert len(results.code_outputs) == 2
        # First execution: cwd reset message
        assert results.code_outputs[0].text == f"[ipybox] cwd reset to {tmp_path.resolve()}"
        # Second execution: cwd is back to working_dir
        assert results.code_outputs[1].text == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_ptc_approval_accepted(mcp_sources_dir: Path, tmp_path: Path) -> None:
    """Verify PTC is executed when approval request is accepted."""
    async with unpatched_agent(create_ptc_stream_function(mcp_sources_dir, "ptc_test"), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test prompt")

        # 2 approvals: code execution + PTC
        assert len(results.approvals) == 2
        assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
        assert results.approvals[1].tool_call.tool_name == "test_tool_2"
        assert len(results.code_outputs) == 1
        assert results.code_outputs[0].text is not None
        assert "You passed to tool 2: ptc_test" in results.code_outputs[0].text


@pytest.mark.asyncio
async def test_ptc_approval_rejected(mcp_sources_dir: Path, tmp_path: Path) -> None:
    """Verify PTC rejection ends the agent turn."""

    # Approve code execution, reject PTC
    def approve_function(req: ApprovalRequest) -> bool:
        return req.tool_call.tool_name == "ipybox_execute_ipython_cell"

    async with unpatched_agent(create_ptc_stream_function(mcp_sources_dir, "ptc_test"), tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test prompt", approve_function=approve_function)

        assert len(results.approvals) == 2
        assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
        assert results.approvals[1].tool_call.tool_name == "test_tool_2"
        # Agent turn ends with rejection response
        assert any(r.content == "Tool call rejected" for r in results.responses)


@pytest.mark.asyncio
async def test_shell_approval_rejected(tmp_path: Path) -> None:
    """Verify shell command rejection ends the agent turn."""
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "!echo hello"},
    )

    # Approve code execution, reject shell command
    def approve_function(req: ApprovalRequest) -> bool:
        return not isinstance(req.tool_call, ShellAction)

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test prompt", approve_function=approve_function)

        assert len(results.approvals) == 2
        assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
        assert isinstance(results.approvals[1].tool_call, ShellAction)
        # Agent sees the rejection error in code output
        assert len(results.code_outputs) == 1
        assert results.code_outputs[0].approval_rejected()
        # Agent turn ends with rejection response
        assert any(r.content == "Tool call rejected" for r in results.responses)


@pytest.mark.asyncio
async def test_mcp_tool_approval_accepted(mcp_servers: dict[str, dict[str, Any]], tmp_path: Path) -> None:
    """Verify an MCP tool is registered, approved and executed via _call_mcp_tool."""
    stream_function = create_stream_function(
        tool_name="test_tool_2",
        tool_args={"s": "approved"},
    )

    async with patched_agent(stream_function, mcp_servers=mcp_servers, tmp_dir=tmp_path) as agent:
        assert "test_tool-1" in agent.tool_names
        assert "test_tool_2" in agent.tool_names
        assert "test_tool_3" in agent.tool_names

        results = await collect_stream(agent, "call mcp tool")

        assert len(results.approvals) == 1
        assert results.approvals[0].tool_call.tool_name == "test_tool_2"
        assert isinstance(results.approvals[0].tool_call, GenericCall)
        assert results.approvals[0].tool_call.tool_args == {"s": "approved"}
        assert len(results.tool_outputs) == 1
        assert "You passed to tool 2: approved" in str(results.tool_outputs[0].content)


@pytest.mark.asyncio
async def test_mcp_tool_approval_rejected(mcp_servers: dict[str, dict[str, Any]], tmp_path: Path) -> None:
    """Verify tool call is not executed when approval request is rejected."""
    stream_function = create_stream_function(
        tool_name="test_tool_2",
        tool_args={"s": "should not run"},
    )

    async with patched_agent(stream_function, mcp_servers=mcp_servers, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test prompt", approve_function=lambda _: False)

        # ToolResult is not yielded if rejected
        assert len(results.tool_outputs) == 0
        # Agent turn ends with rejection response
        assert any(r.content == "Tool call rejected" for r in results.responses)


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_without_approval(tmp_path: Path) -> None:
    """Unknown tool name returns error without approval request."""
    stream_function = create_stream_function(
        tool_name="nonexistent_tool",
        tool_args={"arg": "value"},
    )

    async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # No approval request for unknown tool
        assert len(results.approvals) == 0
        # Should still get a final response
        assert len(results.responses) > 0


@pytest.mark.asyncio
async def test_ipybox_reset_success(tmp_path: Path) -> None:
    """ipybox_reset tool resets the kernel successfully."""
    stream_function = create_stream_function(tool_name="ipybox_reset", tool_args={})

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "reset kernel")

        # Should have approval request for reset
        assert len(results.approvals) == 1
        assert results.approvals[0].tool_call.tool_name == "ipybox_reset"
        # Should have tool output with success message
        assert len(results.tool_outputs) == 1
        assert "reset successfully" in str(results.tool_outputs[0].content).lower()


@pytest.mark.asyncio
async def test_ipybox_reset_exception(tmp_path: Path) -> None:
    """ipybox_reset returns error message when reset fails."""
    stream_function = create_stream_function(tool_name="ipybox_reset", tool_args={})

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        # Mock reset to raise an exception
        async def failing_reset() -> None:
            raise RuntimeError("Kernel crashed")

        agent._code_executor.reset = failing_reset

        results = await collect_stream(agent, "reset kernel")

        assert len(results.tool_outputs) == 1
        assert "Kernel reset failed" in str(results.tool_outputs[0].content)
        assert "Kernel crashed" in str(results.tool_outputs[0].content)


@pytest.mark.asyncio
async def test_mcp_tool_exception_returns_error(mcp_servers: dict[str, dict[str, Any]], tmp_path: Path) -> None:
    """MCP tool exception returns error message."""
    stream_function = create_stream_function(
        tool_name="test_tool_2",
        tool_args={"s": "test"},
    )

    async with patched_agent(stream_function, mcp_servers=mcp_servers, tmp_dir=tmp_path) as agent:
        # Mock direct_call_tool to raise an exception
        async def failing_call(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Connection failed")

        agent._tool_mapping["test_tool_2"].direct_call_tool = failing_call

        results = await collect_stream(agent, "test")

        assert len(results.tool_outputs) == 1
        assert "MCP tool call failed" in str(results.tool_outputs[0].content)
        assert "Connection failed" in str(results.tool_outputs[0].content)


@pytest.mark.asyncio
async def test_mcp_tool_result_overflow_is_saved_to_file(
    tmp_path: Path,
    mcp_servers: dict[str, dict[str, Any]],
    stored_path_from_notice: Callable[[str, Path], Path],
    collect_tool_return_parts: Callable[[list[ModelMessage]], list[ToolReturnPart]],
) -> None:
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
        session_id="session-1",
        tool_result_inline_max_bytes=32,
        tool_result_preview_chars=100,
    ) as agent:

        async def large_call(*args: Any, **kwargs: Any) -> str:
            return payload

        agent._tool_mapping["test_tool_2"].direct_call_tool = large_call
        results = await collect_stream(agent, "trigger overflow")

        assert len(results.tool_outputs) == 1
        notice = str(results.tool_outputs[0].content)
        assert "configured inline threshold (32 bytes)" in notice
        assert "Preview (~100 characters):" in notice
        assert "line-1" in notice

        tool_returns = collect_tool_return_parts(agent._message_history)
        assert len(tool_returns) == 1
        assert tool_returns[0].content == notice

        stored_path = stored_path_from_notice(notice, tmp_path)
        assert stored_path.exists()
        assert stored_path.suffix == ".txt"
        assert stored_path.read_text(encoding="utf-8") == payload


@pytest.mark.asyncio
async def test_mcp_tool_result_under_threshold_stays_inline(
    tmp_path: Path,
    mcp_servers: dict[str, dict[str, Any]],
    collect_tool_return_parts: Callable[[list[ModelMessage]], list[ToolReturnPart]],
) -> None:
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
        session_id="session-1",
        tool_result_inline_max_bytes=1024,
    ) as agent:

        async def small_call(*args: Any, **kwargs: Any) -> str:
            return payload

        agent._tool_mapping["test_tool_2"].direct_call_tool = small_call
        results = await collect_stream(agent, "no overflow")

        assert len(results.tool_outputs) == 1
        assert results.tool_outputs[0].content == payload

        tool_returns = collect_tool_return_parts(agent._message_history)
        assert len(tool_returns) == 1
        assert tool_returns[0].content == payload


@pytest.mark.asyncio
async def test_code_execution_final_output_overflow_replaced_with_notice(
    tmp_path: Path,
    stored_path_from_notice: Callable[[str, Path], Path],
    collect_tool_return_parts: Callable[[list[ModelMessage]], list[ToolReturnPart]],
) -> None:
    """Large final code-exec output is replaced with an overflow notice and stored to file."""
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "print('x')"},
    )
    payload = "alpha\nbeta\ngamma\n" + ("x" * 400)

    async def code_exec_function(self: Agent, code: str) -> AsyncIterator[CodeExecutionOutput]:
        yield CodeExecutionOutput(text=payload, images=[])

    async with patched_agent(
        stream_function,
        code_exec_function=code_exec_function,
        tmp_dir=tmp_path,
        session_id="session-1",
        tool_result_inline_max_bytes=32,
        tool_result_preview_chars=100,
    ) as agent:
        results = await collect_stream(agent, "run large output")

        assert len(results.code_outputs) == 1
        output = results.code_outputs[0]
        assert output.text is not None
        assert "configured inline threshold (32 bytes)" in output.text
        assert "Preview (~100 characters):" in output.text
        assert "alpha" in output.text
        assert output.images == []

        tool_returns = collect_tool_return_parts(agent._message_history)
        assert len(tool_returns) == 1
        assert tool_returns[0].content == output.text

        stored_path = stored_path_from_notice(output.text, tmp_path)
        assert stored_path.exists()
        assert stored_path.suffix == ".txt"
        assert stored_path.read_text(encoding="utf-8") == payload


@pytest.mark.asyncio
async def test_code_execution_chunk_does_not_create_duplicate_overflow_file(
    tmp_path: Path,
    stored_path_from_notice: Callable[[str, Path], Path],
) -> None:
    """Large streamed chunks plus final output should persist exactly one overflow file."""
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "print('x')"},
    )
    payload_chunk = "row-1\nrow-2\nrow-3\n" + ("x" * 400) + "\n"
    payload_final = payload_chunk.rstrip("\n")

    async def code_exec_function(
        self: Agent, code: str
    ) -> AsyncIterator[CodeExecutionOutput | CodeExecutionOutputChunk]:
        yield CodeExecutionOutputChunk(text=payload_chunk, agent_id=self.agent_id)
        yield CodeExecutionOutput(text=payload_final, images=[])

    async with patched_agent(
        stream_function,
        code_exec_function=code_exec_function,
        tmp_dir=tmp_path,
        session_id="session-1",
        tool_result_inline_max_bytes=32,
        tool_result_preview_chars=100,
    ) as agent:
        results = await collect_stream(agent, "run large chunk output")

        chunk_events = [event for event in results.all_events if isinstance(event, CodeExecutionOutputChunk)]
        assert len(chunk_events) == 1
        assert chunk_events[0].text == payload_chunk

        assert len(results.code_outputs) == 1
        output = results.code_outputs[0]
        assert output.text is not None
        assert "configured inline threshold (32 bytes)" in output.text
        stored_path = stored_path_from_notice(output.text, tmp_path)
        assert stored_path.exists()
        assert stored_path.suffix == ".txt"
        assert stored_path.read_text(encoding="utf-8") == payload_final

        tool_results_dir = tmp_path / ".freeact" / "sessions" / "session-1" / "tool-results"
        files = list(tool_results_dir.glob("*.txt"))
        assert len(files) == 1


@pytest.mark.asyncio
async def test_code_execution_exception_yields_error(tmp_path: Path) -> None:
    """Code executor exception yields error output."""
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "x = 1"},
    )

    async with unpatched_agent(stream_function, tmp_dir=tmp_path) as agent:
        # Mock the stream method to raise an exception
        async def failing_stream(code: str, timeout: float | None = None, chunks: bool = False) -> AsyncIterator[Any]:
            raise RuntimeError("Kernel crashed unexpectedly")
            yield  # Make it an async generator

        agent._code_executor.stream = failing_stream

        results = await collect_stream(agent, "test")

        assert len(results.code_outputs) == 1
        assert "Kernel crashed unexpectedly" in str(results.code_outputs[0].text)


@pytest.mark.asyncio
async def test_thinking_parts_yielded(tmp_path: Path) -> None:
    """ThinkingPart events are captured and yielded as ThoughtsChunk/Thoughts."""

    async def stream_function(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls | DeltaThinkingCalls]:
        yield {0: DeltaThinkingPart(content="Let me think")}
        yield {0: DeltaThinkingPart(content=" about this.")}
        yield "Here is my answer."

    async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
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
async def test_thinking_none_content_ignored(tmp_path: Path) -> None:
    """`ThinkingPartDelta` with `None` content does not cause a crash."""

    async def stream_function(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | DeltaToolCalls | DeltaThinkingCalls]:
        yield {0: DeltaThinkingPart(content="Thinking")}
        yield {0: DeltaThinkingPart(content=None)}
        yield {0: DeltaThinkingPart(content=" more.")}
        yield "Response text."

    async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        assert len(results.thoughts) == 1
        assert results.thoughts[0].content == "Thinking more."
        assert len(results.responses) == 1


@pytest.mark.asyncio
async def test_text_deltas_yielded(tmp_path: Path) -> None:
    """Multiple text yields produce ResponseChunk events."""

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        yield "Hello"
        yield " world"
        yield "!"

    async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
        results = await collect_stream(agent, "test")

        # Should have multiple response chunks
        assert len(results.response_chunks) >= 1
        # Should have final response with combined text
        assert len(results.responses) == 1
        assert results.responses[0].content == "Hello world!"


@pytest.mark.asyncio
async def test_execution_timeout_exceeded(tmp_path: Path) -> None:
    """Code execution exceeding timeout raises error."""
    # Code that would print "completed" if it ran to completion
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "import time; time.sleep(2); print('completed')"},
    )

    async with unpatched_agent(stream_function, tmp_dir=tmp_path, execution_timeout=0.5) as agent:
        results = await collect_stream(agent, "run slow code")

        # Should have code output (timeout is caught and yields output)
        assert len(results.code_outputs) == 1
        # The code should NOT have completed - "completed" should not appear
        # TimeoutError has empty str() representation, so text is empty
        assert "completed" not in (results.code_outputs[0].text or "")


@pytest.mark.asyncio
async def test_execution_timeout_excludes_ptc_approval_wait(mcp_sources_dir: Path, tmp_path: Path) -> None:
    """Execution timeout does not count PTC approval waiting time.

    Uses a 5 second execution timeout and delays PTC approval by 8 seconds.
    If approval wait counted toward the timeout, this would fail.
    """
    stream_function = create_ptc_stream_function(mcp_sources_dir, "test")

    async with unpatched_agent(stream_function, tmp_dir=tmp_path, execution_timeout=5) as agent:
        results = StreamResults()
        async for event in agent.stream("run code"):
            match event:
                case ApprovalRequest() as req:
                    results.approvals.append(req)
                    if req.tool_call.tool_name != "ipybox_execute_ipython_cell":
                        await asyncio.sleep(8)
                    req.approve(True)
                case CodeExecutionOutput() as out:
                    results.code_outputs.append(out)

        # Should succeed despite 8s PTC approval delay with 5s execution timeout
        assert len(results.approvals) == 2
        assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
        assert results.approvals[1].tool_call.tool_name == "test_tool_2"
        assert len(results.code_outputs) == 1
        assert results.code_outputs[0].text is not None
        assert "You passed to tool 2: test" in results.code_outputs[0].text


@pytest.mark.asyncio
async def test_fast_execution_within_timeout(tmp_path: Path) -> None:
    """Code completing within timeout succeeds."""
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "print('hello')"},
    )

    async with unpatched_agent(stream_function, tmp_dir=tmp_path, execution_timeout=10) as agent:
        results = await collect_stream(agent, "run code")

        assert len(results.code_outputs) == 1
        assert results.code_outputs[0].text is not None
        assert "hello" in results.code_outputs[0].text
