# Covers behavior-inventory.md sections: 1 (lifecycle), 2 (events), 3 (code execution),
# 5 (approvals incl. abandonment INVARIANT), 6 (cancellation INVARIANTs), 8 (overflow flags)
import asyncio
import json
from pathlib import Path
from typing import Any

import ipybox
import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import DeltaToolCall

from freeact import ApprovalRequest, Cancelled, CodeExecutionOutput, Phase
from freeact.agent import Agent
from freeact.agent.tooldefs import SUBAGENT_TOOL_DEFS_PATH, load_tool_definitions
from freeact.toolcalls import CodeAction
from tests.helpers import (
    ApprovalRecorder,
    FakeCodeExecutor,
    collect_stream,
    create_stream_function,
    create_test_runtime,
    get_tool_return_parts,
    ipybox_ptc_approval,
    ipybox_shell_approval,
    patched_agent,
)


def build_agent(tmp_path: Path, **agent_kwargs: Any) -> Agent:
    """Create an agent (kernel replaced by a fake) without starting it."""
    runtime = create_test_runtime(tmp_path, **agent_kwargs.pop("section_overrides", {}))
    agent = Agent(runtime, **agent_kwargs)
    agent._executor._code_executor = FakeCodeExecutor()  # type: ignore[assignment]
    return agent


def simple_output_script(output_text: str) -> Any:
    async def script(code: str) -> Any:
        yield ipybox.CodeExecutionResult(text=output_text, images=[])

    return script


class TestSessionPersistenceConfig:
    def test_agent_generates_session_id_when_missing(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path)
        assert agent.session_id is not None

    def test_agent_uses_provided_session_id(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path, session_id="session-1")
        assert agent.session_id == "session-1"

    def test_agent_runs_without_session_when_disabled(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path, section_overrides={"enable_persistence": False})
        assert agent.session_id is None

    def test_agent_rejects_session_id_when_persistence_disabled(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="session_id requires enable_persistence=True"):
            build_agent(tmp_path, session_id="session-1", section_overrides={"enable_persistence": False})


class TestIpyboxExecution:
    @pytest.mark.asyncio
    async def test_approval_accepted(self, tmp_path: Path) -> None:
        """Tool call is executed when approval request is accepted."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('approved execution')"},
        )
        executor = FakeCodeExecutor(simple_output_script("approved execution"))

        async with patched_agent(stream_function, executor, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt")

            assert len(results.approvals) == 1
            assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
            assert isinstance(results.approvals[0].tool_call, CodeAction)
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "approved execution"
            assert results.code_outputs[0].approval_rejected is False

    @pytest.mark.asyncio
    async def test_approval_rejected(self, tmp_path: Path) -> None:
        """Tool call is not executed when approval request is rejected; turn ends."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('should not run')"},
        )
        executor = FakeCodeExecutor(simple_output_script("should not be called"))

        async with patched_agent(stream_function, executor, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=lambda _: False)

            assert len(results.code_outputs) == 0
            assert executor.stream_calls == []
            assert any(r.content == "Tool call rejected" for r in results.responses)

    @pytest.mark.asyncio
    async def test_ptc_approval_accepted(self, tmp_path: Path) -> None:
        """PTC executes when its nested approval is accepted."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "from test.tool_2 import Params, run; run(Params(s='x'))"},
        )
        recorder = ApprovalRecorder()

        async def script(code: str) -> Any:
            approval = ipybox_ptc_approval("test", "tool_2", {"s": "x"}, recorder)
            yield approval
            if await approval.response():
                yield ipybox.CodeExecutionResult(text="You passed to tool 2: x", images=[])
            else:
                yield ipybox.CodeExecutionResult(text="ApprovalRejectedError: rejected", images=[])

        async with patched_agent(stream_function, FakeCodeExecutor(script), tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt")

            assert [a.tool_call.tool_name for a in results.approvals] == [
                "ipybox_execute_ipython_cell",
                "test_tool_2",
            ]
            assert results.approvals[1].tool_call.ptc is True  # type: ignore[attr-defined]
            assert recorder.decisions == [True]
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "You passed to tool 2: x"

    @pytest.mark.asyncio
    async def test_ptc_approval_rejected(self, tmp_path: Path) -> None:
        """PTC rejection surfaces the in-kernel error and ends the turn."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "from test.tool_2 import Params, run; run(Params(s='x'))"},
        )
        recorder = ApprovalRecorder()

        async def script(code: str) -> Any:
            approval = ipybox_ptc_approval("test", "tool_2", {"s": "x"}, recorder)
            yield approval
            if await approval.response():
                yield ipybox.CodeExecutionResult(text="ok", images=[])
            else:
                yield ipybox.CodeExecutionResult(
                    text="ApprovalRejectedError: Approval request for test_tool_2 rejected", images=[]
                )

        def approve_function(req: ApprovalRequest) -> bool:
            return req.tool_call.tool_name == "ipybox_execute_ipython_cell"

        async with patched_agent(stream_function, FakeCodeExecutor(script), tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=approve_function)

            assert recorder.decisions == [False]
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].approval_rejected is True
            assert results.code_outputs[0].text is not None
            assert "ApprovalRejectedError:" in results.code_outputs[0].text
            assert any(r.content == "Tool call rejected" for r in results.responses)

    @pytest.mark.asyncio
    async def test_shell_approvals_split_composite_command(self, tmp_path: Path) -> None:
        """Composite shell commands yield one approval per sub-command."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "!ls && pwd"},
        )
        recorder = ApprovalRecorder()

        async def script(code: str) -> Any:
            approval = ipybox_shell_approval("ls && pwd", recorder)
            yield approval
            await approval.response()
            yield ipybox.CodeExecutionResult(text="done", images=[])

        async with patched_agent(stream_function, FakeCodeExecutor(script), tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt")

            shell_approvals = [a for a in results.approvals if a.tool_call.tool_name == "bash"]
            assert [a.tool_call.command for a in shell_approvals] == ["ls", "pwd"]  # type: ignore[attr-defined]
            assert recorder.decisions == [True]

    @pytest.mark.asyncio
    async def test_composite_partial_rejection_rejects_whole_command(self, tmp_path: Path) -> None:
        """Rejecting any sub-command rejects the whole composite and ends the turn."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "!ls && rm -rf /"},
        )
        recorder = ApprovalRecorder()

        async def script(code: str) -> Any:
            approval = ipybox_shell_approval("ls && rm -rf /", recorder)
            yield approval
            if await approval.response():
                yield ipybox.CodeExecutionResult(text="done", images=[])
            else:
                yield ipybox.CodeExecutionResult(text="ApprovalRejectedError: shell rejected", images=[])

        def approve_function(req: ApprovalRequest) -> bool:
            return req.tool_call.tool_name != "bash" or req.tool_call.command == "ls"  # type: ignore[attr-defined]

        async with patched_agent(stream_function, FakeCodeExecutor(script), tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=approve_function)

            assert recorder.decisions == [False]
            assert any(r.content == "Tool call rejected" for r in results.responses)

    @pytest.mark.asyncio
    async def test_execution_timeout_passed_to_kernel(self, tmp_path: Path) -> None:
        """The configured execution timeout is enforced by the kernel stream."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )
        executor = FakeCodeExecutor()

        async with patched_agent(stream_function, executor, tmp_dir=tmp_path, execution_timeout=60) as agent:
            await collect_stream(agent, "test")

        assert executor.stream_calls[0]["timeout"] == 60

    @pytest.mark.asyncio
    async def test_execution_timeout_disabled(self, tmp_path: Path) -> None:
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )
        executor = FakeCodeExecutor()

        async with patched_agent(stream_function, executor, tmp_dir=tmp_path, execution_timeout=0) as agent:
            await collect_stream(agent, "test")

        assert executor.stream_calls[0]["timeout"] is None

    @pytest.mark.asyncio
    async def test_kernel_exception_yields_error_output(self, tmp_path: Path) -> None:
        """Kernel exceptions become error text in the output event, not a crash."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )

        async def script(code: str) -> Any:
            raise RuntimeError("kernel blew up")
            yield  # noqa: RUF027

        async with patched_agent(stream_function, FakeCodeExecutor(script), tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test")

            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "kernel blew up"

    @pytest.mark.asyncio
    async def test_kernel_reset(self, tmp_path: Path) -> None:
        stream_function = create_stream_function(tool_name="ipybox_reset", tool_args={})
        executor = FakeCodeExecutor()

        async with patched_agent(stream_function, executor, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "reset please")

        assert executor.reset_calls == 1
        assert any("Kernel reset successfully" in str(t.content) for t in results.tool_outputs)

    @pytest.mark.asyncio
    async def test_kernel_reset_failure_returns_error(self, tmp_path: Path) -> None:
        stream_function = create_stream_function(tool_name="ipybox_reset", tool_args={})
        executor = FakeCodeExecutor()
        executor.reset_error = RuntimeError("nope")

        async with patched_agent(stream_function, executor, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "reset please")

        assert any("Kernel reset failed: nope" in str(t.content) for t in results.tool_outputs)

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_without_approval(self, tmp_path: Path) -> None:
        stream_function = create_stream_function(tool_name="nonexistent_tool", tool_args={})

        async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test")

            assert len(results.approvals) == 0
            from pydantic_ai.messages import ModelRequest, ToolReturnPart

            tool_returns = [
                part
                for message in agent._session.messages
                if isinstance(message, ModelRequest)
                for part in message.parts
                if isinstance(part, ToolReturnPart)
            ]
            assert len(tool_returns) == 1
            assert "Unknown tool name" in str(tool_returns[0].content)


class TestCancellation:
    @pytest.mark.asyncio
    async def test_cancel_during_tool_execution(self, tmp_path: Path) -> None:
        """Cancel during code execution yields Cancelled(phase=tool_execution)."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )
        agent_ref: list[Agent | None] = [None]

        async def script(code: str) -> Any:
            assert agent_ref[0] is not None
            agent_ref[0]._cancel.set()
            yield ipybox.CodeExecutionResult(text="output", images=[])

        async with patched_agent(stream_function, FakeCodeExecutor(script), tmp_dir=tmp_path) as agent:
            agent_ref[0] = agent
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == Phase.TOOL_EXECUTION
        assert len(results.code_outputs) == 1

    @pytest.mark.asyncio
    async def test_cancel_during_llm_streaming(self, tmp_path: Path) -> None:
        """Cancel during LLM streaming preserves partial response and yields Cancelled."""
        agent_ref: list[Agent | None] = [None]

        async def stream_function(messages: Any, info: Any) -> Any:
            yield "partial response"
            if agent_ref[0] is not None:
                agent_ref[0]._cancel.set()
            yield " more text"

        async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
            agent_ref[0] = agent
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == Phase.LLM_STREAMING
        assert len(results.responses) == 1

    @pytest.mark.asyncio
    async def test_cancel_during_approval_wait(self, tmp_path: Path) -> None:
        """Cancel during approval wait produces an interrupted tool return."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )

        async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
            events: list[Any] = []
            async for event in agent.stream("test"):
                events.append(event)
                match event:
                    case ApprovalRequest():
                        agent._cancel.set()

        cancelled = [e for e in events if isinstance(e, Cancelled)]
        assert len(cancelled) == 1
        assert cancelled[0].phase == Phase.TOOL_EXECUTION

        tool_returns = get_tool_return_parts(agent._session.messages)
        assert len(tool_returns) == 1
        assert tool_returns[0].content == "Interrupted by user"
        assert tool_returns[0].metadata.get("interrupted") is True

    @pytest.mark.asyncio
    async def test_cancel_produces_synthetic_returns_for_orphaned_calls(self, tmp_path: Path) -> None:
        """INVARIANT: after cancellation every issued tool call has a return in history."""
        agent_ref: list[Agent | None] = [None]

        async def stream_function(messages: list[ModelMessage], info: Any) -> Any:
            if not get_tool_return_parts(messages):
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print(1)"}),
                        tool_call_id="call_1",
                    ),
                    1: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print(2)"}),
                        tool_call_id="call_2",
                    ),
                }
                if agent_ref[0] is not None:
                    agent_ref[0]._cancel.set()
                yield "done"

        async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
            agent_ref[0] = agent
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == Phase.LLM_STREAMING

        tool_returns = get_tool_return_parts(agent._session.messages)
        assert len(tool_returns) == 2
        for tr in tool_returns:
            assert tr.content == "Interrupted by user"
            assert tr.metadata.get("interrupted") is True

    @pytest.mark.asyncio
    async def test_cancel_during_execution_with_empty_output(self, tmp_path: Path) -> None:
        """Cancel during code execution with no output yields interrupted tool return."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "import time; time.sleep(30)"},
        )
        agent_ref: list[Agent | None] = [None]

        async def script(code: str) -> Any:
            assert agent_ref[0] is not None
            agent_ref[0]._cancel.set()
            # ipybox cancel() causes stream() to return without yielding a result
            return
            yield

        async with patched_agent(stream_function, FakeCodeExecutor(script), tmp_dir=tmp_path) as agent:
            agent_ref[0] = agent
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == Phase.TOOL_EXECUTION
        assert len(results.code_outputs) == 0

        tool_returns = get_tool_return_parts(agent._session.messages)
        assert len(tool_returns) == 1
        assert tool_returns[0].content == "Interrupted by user"
        assert tool_returns[0].metadata.get("interrupted") is True

    @pytest.mark.asyncio
    async def test_stream_without_cancel_unchanged(self, tmp_path: Path) -> None:
        """Normal stream behavior is unchanged when cancel is never set."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )
        executor = FakeCodeExecutor(simple_output_script("output"))

        async with patched_agent(stream_function, executor, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 0
        assert len(results.approvals) == 1
        assert len(results.code_outputs) == 1
        assert len(results.responses) >= 1

    @pytest.mark.asyncio
    async def test_cancel_method_cancels_kernel(self, tmp_path: Path) -> None:
        executor = FakeCodeExecutor()
        runtime = create_test_runtime(tmp_path)
        agent = Agent(runtime)
        agent._executor._code_executor = executor  # type: ignore[assignment]

        agent.cancel()

        assert agent._cancel.is_set()
        assert executor.cancelled is True


class TestGeneratorExitRejectsIpyboxApproval:
    """INVARIANT: abandoning the stream while an in-kernel approval is pending
    rejects the ipybox approval exactly once, unblocking the tool server."""

    @staticmethod
    def _make_ipybox_approval(
        server_name: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> tuple[ipybox.ApprovalRequest, asyncio.Event]:
        rejected = asyncio.Event()

        async def mock_respond(decision: bool) -> None:
            if not decision:
                rejected.set()

        approval = ipybox.ApprovalRequest(
            server_name=server_name,
            tool_name=tool_name,
            tool_args=tool_args,
            respond=mock_respond,
        )
        return approval, rejected

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("server_name", "tool_name", "tool_args", "code", "expected_tool_name"),
        [
            ("ipybox", "shell", {"cmd": "ls -la"}, "!ls -la", "bash"),
            (
                "test_server",
                "my_tool",
                {"key": "value"},
                "from test.my_tool import run; run()",
                "test_server_my_tool",
            ),
            (
                "ipybox",
                "shell_magic",
                {"cmd": "echo hello\necho world"},
                "%%bash\necho hello\necho world",
                "shell_magic",
            ),
        ],
    )
    async def test_pending_approval_rejected_on_generator_exit(
        self,
        server_name: str,
        tool_name: str,
        tool_args: dict[str, Any],
        code: str,
        expected_tool_name: str,
        tmp_path: Path,
    ) -> None:
        ipybox_approval, rejected = self._make_ipybox_approval(server_name, tool_name, tool_args)

        async def script(code: str) -> Any:
            yield ipybox_approval
            # Simulate kernel blocked waiting for the approval response
            await asyncio.Event().wait()

        agent = build_agent(tmp_path)
        agent._executor._code_executor = FakeCodeExecutor(script)  # type: ignore[assignment]

        gen = agent._executor._execute_code(code, "corr-1")
        event = await gen.__anext__()
        assert isinstance(event, ApprovalRequest)
        assert event.tool_call.tool_name == expected_tool_name

        # Close the generator without resolving the freeact approval
        await gen.aclose()

        # The ipybox ApprovalRequest must have been rejected
        assert rejected.is_set()
        assert ipybox_approval._decision.done()
        assert ipybox_approval._decision.result() is False

    @pytest.mark.asyncio
    async def test_shell_approval_not_double_rejected(self, tmp_path: Path) -> None:
        """Normal rejection path still works (no double reject)."""
        reject_count = 0

        async def counting_respond(decision: bool) -> None:
            nonlocal reject_count
            if not decision:
                reject_count += 1

        ipybox_approval = ipybox.ApprovalRequest(
            server_name="ipybox",
            tool_name="shell",
            tool_args={"cmd": "rm -rf /"},
            respond=counting_respond,
        )

        async def script(code: str) -> Any:
            yield ipybox_approval
            decision = await ipybox_approval.response()
            if decision:
                yield ipybox.CodeExecutionResult(text="output", images=[])
            else:
                yield ipybox.CodeExecutionResult(text="rejected", images=[])

        agent = build_agent(tmp_path)
        agent._executor._code_executor = FakeCodeExecutor(script)  # type: ignore[assignment]

        gen = agent._executor._execute_code("!rm -rf /", "corr-1")
        event = await gen.__anext__()
        assert isinstance(event, ApprovalRequest)

        # Reject via normal path (simulate user pressing 'n')
        event.approve(False)

        # Consume remaining events
        events = [e async for e in gen]
        assert len(events) == 1
        assert isinstance(events[0], CodeExecutionOutput)
        assert events[0].approval_rejected is True

        # reject() called exactly once (not again by GeneratorExit handler)
        assert reject_count == 1

    @pytest.mark.asyncio
    async def test_abandoned_stream_rejects_pending_approval_via_agent(self, tmp_path: Path) -> None:
        """End-to-end: closing agent.stream() while a top-level approval is
        pending resolves that approval as rejected (nothing hangs)."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )

        async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
            stream = agent.stream("test")
            pending: ApprovalRequest | None = None
            async for event in stream:
                match event:
                    case ApprovalRequest() as req:
                        pending = req
                        break
            assert pending is not None
            await stream.aclose()

            # The pending approval resolves as rejected once abandoned
            assert await asyncio.wait_for(pending.approved(), timeout=2) is False


class TestEvents:
    def test_format_with_images(self) -> None:
        out = CodeExecutionOutput(text="hello", images=[Path("/tmp/a.png")])
        assert out.format() == "hello\n![Image](/tmp/a.png)"

    def test_format_empty(self) -> None:
        out = CodeExecutionOutput(text=None, images=[])
        assert out.format() == ""

    def test_subagent_task_default_max_turns_in_schema(self) -> None:
        tool_defs = load_tool_definitions(SUBAGENT_TOOL_DEFS_PATH)
        assert len(tool_defs) == 1
        schema = tool_defs[0].parameters_json_schema
        assert schema["properties"]["max_turns"]["default"] == 100
