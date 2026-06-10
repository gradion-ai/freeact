import asyncio
import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import ipybox
import pytest
from pydantic_ai.models.function import DeltaToolCall

from freeact.agent import Agent, ApprovalRequest, Cancelled, CodeExecutionOutput, Response
from freeact.agent.call import CodeAction, GenericCall
from freeact.agent.config import Config
from freeact.tools.utils import IPYBOX_TOOL_DEFS_PATH, SUBAGENT_TOOL_DEFS_PATH
from tests.helpers import (
    CodeExecFunction,
    collect_stream,
    create_stream_function,
    create_test_config,
    get_tool_return_parts,
    patched_agent,
)


def build_agent(tmp_path: Path, config: Config | None = None, **agent_kwargs: Any) -> Agent:
    """Create an Agent with a mocked (uninstantiated) CodeExecutor class."""
    with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
        mock_executor.return_value = MagicMock()
        return Agent(config=config if config is not None else create_test_config(tmp_path), **agent_kwargs)


def executor_call_kwargs(tmp_path: Path, **config_overrides: Any) -> dict[str, Any]:
    """Create an Agent and return the kwargs passed to the CodeExecutor constructor."""
    with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
        mock_executor.return_value = MagicMock()
        Agent(config=create_test_config(tmp_path, **config_overrides))
        mock_executor.assert_called_once()
        return mock_executor.call_args.kwargs


def create_code_exec_function(output_text: str) -> CodeExecFunction:
    """Returns an execute function that yields a single output element."""

    async def execute(self: Agent, code: str) -> Any:
        yield CodeExecutionOutput(text=output_text, images=[])

    return execute


def create_code_exec_with_approval_function(
    tool_name: str, tool_args: dict[str, Any], approved_result: str, rejected_result: str
) -> CodeExecFunction:
    """Returns an execute function that simulates a PTC approval flow."""

    async def execute(self: Agent, code: str) -> Any:
        approval = ApprovalRequest(
            tool_call=GenericCall(tool_name=tool_name, tool_args=tool_args, ptc=True),
        )
        yield approval
        if await approval.approved():
            yield CodeExecutionOutput(text=approved_result, images=[])
        else:
            yield CodeExecutionOutput(text=rejected_result, images=[])

    return execute


class TestCodeExecutionOutput:
    """Tests for CodeExecutionOutput dataclass methods."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (None, False),
            ("ApprovalRejectedError: Approval request for my_tool rejected", True),
            ("Normal output", False),
        ],
    )
    def test_approval_rejected(self, text: str | None, expected: bool) -> None:
        assert CodeExecutionOutput(text=text, images=[]).approval_rejected() is expected

    @pytest.mark.parametrize(
        ("text", "images", "expected"),
        [
            ("Short text", [], "Short text"),
            ("x" * 1000, [], "x" * 1000),
            (None, [], ""),
            (None, [Path("/tmp/image.png")], "![Image](/tmp/image.png)"),
            ("x" * 100, [Path("/tmp/image.png")], f"{'x' * 100}\n![Image](/tmp/image.png)"),
            (
                "Output",
                [Path("/tmp/img1.png"), Path("/tmp/img2.png")],
                "Output\n![Image](/tmp/img1.png)\n![Image](/tmp/img2.png)",
            ),
        ],
    )
    def test_format(self, text: str | None, images: list[Path], expected: str) -> None:
        assert CodeExecutionOutput(text=text, images=images).format() == expected


class _FakeMcpServer:
    def __init__(self, *, tool_prefix: str, result: object = None, error: Exception | None = None) -> None:
        self.tool_prefix = tool_prefix
        self._result = result
        self._error = error
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def direct_call_tool(self, name: str, args: dict[str, object]) -> object:
        self.calls.append((name, args))
        if self._error is not None:
            raise self._error
        return self._result


class TestMcpToolCall:
    @pytest.mark.asyncio
    async def test_call_mcp_tool_returns_result_directly(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path)
        server = _FakeMcpServer(tool_prefix="filesystem", result="file text")
        agent._tool_mapping["filesystem_read_text_file"] = server  # type: ignore[assignment]

        result = await agent._call_mcp_tool("filesystem_read_text_file", {"path": "README.md"})

        assert result == "file text"
        assert server.calls == [("read_text_file", {"path": "README.md"})]

    @pytest.mark.asyncio
    async def test_call_mcp_tool_returns_error_on_exception(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path)
        server = _FakeMcpServer(tool_prefix="test", error=RuntimeError("connection failed"))
        agent._tool_mapping["test_tool_2"] = server  # type: ignore[assignment]

        result = await agent._call_mcp_tool("test_tool_2", {"s": "x"})
        assert "MCP tool call failed" in str(result)


class TestSessionPersistenceConfig:
    def test_agent_generates_session_id_when_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        generated = uuid.uuid4()
        monkeypatch.setattr("freeact.agent.core.uuid.uuid4", lambda: generated)

        agent = build_agent(tmp_path)

        assert agent._session_id == str(generated)
        assert agent.session_id == str(generated)

    def test_agent_uses_provided_session_id(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path, session_id="session-1")

        assert agent.session_id == "session-1"

    def test_agent_creates_internal_session_store_when_enabled(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path)

        assert agent._session_id is not None
        assert agent._session_store is not None

    def test_agent_runs_without_session_store_when_disabled(self, tmp_path: Path) -> None:
        agent = build_agent(tmp_path, create_test_config(tmp_path, enable_persistence=False))

        assert agent._session_id is None
        assert agent.session_id is None
        assert agent._session_store is None
        assert agent._result_materializer is None

    def test_agent_rejects_session_id_when_persistence_disabled(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="session_id requires config.enable_persistence=True"):
            build_agent(tmp_path, create_test_config(tmp_path, enable_persistence=False), session_id="session-1")


class TestIpyboxExecution:
    """Tests for ipybox_execute_ipython_cell tool with mocked code executor."""

    @pytest.mark.asyncio
    async def test_approval_accepted(self, tmp_path: Path) -> None:
        """Verify tool call is executed when approval request is accepted."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('approved execution')"},
        )

        async with patched_agent(
            stream_function, create_code_exec_function("approved execution"), tmp_dir=tmp_path
        ) as agent:
            results = await collect_stream(agent, "test prompt")

            assert len(results.approvals) == 1
            assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
            assert isinstance(results.approvals[0].tool_call, CodeAction)
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "approved execution"

    @pytest.mark.asyncio
    async def test_approval_rejected(self, tmp_path: Path) -> None:
        """Verify tool call is not executed when approval request is rejected."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('should not run')"},
        )

        async with patched_agent(
            stream_function, create_code_exec_function("should not be called"), tmp_dir=tmp_path
        ) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=lambda _: False)

            # CodeExecutionResult is not yielded if code execution is rejected
            assert len(results.code_outputs) == 0
            # Agent turn ends with rejection response
            assert any(r.content == "Tool call rejected" for r in results.responses)

    @pytest.mark.asyncio
    async def test_ptc_approval_accepted(self, tmp_path: Path) -> None:
        """Verify PTC is executed when approval request is accepted."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "from test.tool_2 import Params, run; run(Params(s='ptc_approved'))"},
        )
        code_exec_function = create_code_exec_with_approval_function(
            tool_name="test_tool_2",
            tool_args={"s": "ptc_approved"},
            approved_result="You passed to tool 2: ptc_approved",
            rejected_result="Tool call rejected",
        )

        async with patched_agent(stream_function, code_exec_function, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt")

            assert len(results.approvals) == 2
            assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_call.tool_name == "test_tool_2"
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text == "You passed to tool 2: ptc_approved"

    @pytest.mark.asyncio
    async def test_ptc_approval_rejected(self, tmp_path: Path) -> None:
        """Verify PTC is not executed when approval request is rejected."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "from test.tool_2 import Params, run; run(Params(s='ptc_rejected'))"},
        )
        # rejected_result must contain the class name checked by CodeExecutionOutput.approval_rejected()
        code_exec_function = create_code_exec_with_approval_function(
            tool_name="test_tool_2",
            tool_args={"s": "ptc_rejected"},
            approved_result="You passed to tool 2: ptc_rejected",
            rejected_result="ApprovalRejectedError: Approval request for test_tool_2 rejected",
        )

        # Approve code execution, reject PTC
        def approve_function(req: ApprovalRequest) -> bool:
            return req.tool_call.tool_name == "ipybox_execute_ipython_cell"

        async with patched_agent(stream_function, code_exec_function, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test prompt", approve_function=approve_function)

            assert len(results.approvals) == 2
            assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_call.tool_name == "test_tool_2"
            assert len(results.code_outputs) == 1
            assert results.code_outputs[0].text is not None
            assert "ApprovalRejectedError:" in results.code_outputs[0].text
            # Agent turn ends with rejection response
            assert any(r.content == "Tool call rejected" for r in results.responses)


class TestTimeoutParameters:
    """Tests for execution_timeout and approval_timeout parameters."""

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            ({}, 300),
            ({"execution_timeout": 60}, 60),
            ({"execution_timeout": None}, None),
        ],
    )
    def test_execution_timeout(self, overrides: dict[str, Any], expected: float | None, tmp_path: Path) -> None:
        agent = build_agent(tmp_path, create_test_config(tmp_path, **overrides))
        assert agent._execution_timeout == expected

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            ({}, None),
            ({"approval_timeout": 30}, 30),
        ],
    )
    def test_approval_timeout_passed_to_executor(
        self, overrides: dict[str, Any], expected: float | None, tmp_path: Path
    ) -> None:
        assert executor_call_kwargs(tmp_path, **overrides)["approval_timeout"] == expected


class TestKernelEnvHome:
    """Tests for default HOME environment variable in kernel_env."""

    def test_default_home_env_var(self, tmp_path: Path) -> None:
        """HOME from os.environ is added to kernel_env by Config."""
        assert "HOME" in executor_call_kwargs(tmp_path)["kernel_env"]

    def test_home_env_var_not_overridden(self, tmp_path: Path) -> None:
        """User-provided HOME in kernel_env is not overwritten."""
        kwargs = executor_call_kwargs(tmp_path, kernel_env={"HOME": "/custom/home"})
        assert kwargs["kernel_env"]["HOME"] == "/custom/home"


class TestSubagentConfigPropagation:
    """Tests that subagents inherit parent runtime/safety configuration."""

    @pytest.mark.asyncio
    async def test_execute_subagent_task_propagates_runtime_and_safety_settings(self, tmp_path: Path) -> None:
        """_execute_subagent_task forwards parent config to spawned subagents."""
        captured: dict[str, Any] = {}

        class FakeSubagent:
            def __init__(self, config: Config, agent_id: str | None = None, **kwargs: Any):
                captured["config"] = config
                captured["agent_id"] = agent_id
                captured.update(kwargs)
                self.agent_id = agent_id or "main"

            async def __aenter__(self) -> "FakeSubagent":
                return self

            async def __aexit__(self, *args: object) -> None:
                return None

            async def stream(self, prompt: str, max_turns: int | None = None) -> Any:
                yield Response(content="done", agent_id=self.agent_id)

        config = create_test_config(
            tmp_path,
            kernel_env={"HOME": "/custom/home", "OTHER": "value"},
            images_dir=Path("/tmp/images"),
            approval_timeout=42,
        )
        agent = build_agent(
            tmp_path,
            config,
            sandbox=True,
            sandbox_config=Path("/tmp/sandbox.cfg"),
            session_id="session-1",
        )

        with patch("freeact.agent.core.Agent", FakeSubagent):
            events = [event async for event in agent._execute_subagent_task("subtask", max_turns=3, corr_id="call-1")]

        assert len(events) >= 1
        sub_config = captured["config"]
        assert sub_config.kernel_env == {"HOME": "/custom/home", "OTHER": "value"}
        assert sub_config.kernel_env is not config.kernel_env
        assert captured["agent_id"].startswith("sub-")
        assert sub_config.enable_subagents is False
        assert captured["session_id"] == "session-1"
        assert captured["sandbox"] is True
        assert captured["sandbox_config"] == Path("/tmp/sandbox.cfg")

    @pytest.mark.asyncio
    async def test_cancel_propagates_to_subagent_code_executor(self, tmp_path: Path) -> None:
        """Parent cancel triggers cancel on subagent's code executor."""
        subagent_executor_cancelled = asyncio.Event()

        class FakeSubagent:
            def __init__(self, config: Config, agent_id: str | None = None, **kwargs: Any):
                self.agent_id = agent_id or "main"
                mock_exec = MagicMock()
                mock_exec.cancel = lambda: subagent_executor_cancelled.set()
                self._code_executor = mock_exec

            async def __aenter__(self) -> "FakeSubagent":
                return self

            async def __aexit__(self, *args: object) -> None:
                return None

            async def stream(self, prompt: str, max_turns: int | None = None) -> Any:
                yield Response(content="working", agent_id=self.agent_id)
                try:
                    await asyncio.wait_for(subagent_executor_cancelled.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
                yield Response(content="done", agent_id=self.agent_id)

        agent = build_agent(tmp_path)

        async def set_cancel_later() -> None:
            await asyncio.sleep(0.05)
            agent._cancel_event.set()

        with patch("freeact.agent.core.Agent", FakeSubagent):
            cancel_task = asyncio.create_task(set_cancel_later())
            # consume events to drive the subagent stream to completion
            async for _ in agent._execute_subagent_task("subtask", max_turns=3, corr_id="call-1"):
                pass
            await cancel_task

        assert subagent_executor_cancelled.is_set()


def test_subagent_task_default_max_turns() -> None:
    """Default max_turns for subagent_task is 100."""
    schema = json.loads(SUBAGENT_TOOL_DEFS_PATH.read_text())
    max_turns_schema = schema[0]["parameters_json_schema"]["properties"]["max_turns"]
    assert max_turns_schema["default"] == 100


def test_ipybox_execute_schema_has_no_max_output_chars() -> None:
    """ipybox_execute_ipython_cell does not expose output truncation args."""
    schema = json.loads(IPYBOX_TOOL_DEFS_PATH.read_text())
    execute_schema = next(item for item in schema if item["name"] == "ipybox_execute_ipython_cell")
    properties = execute_schema["parameters_json_schema"]["properties"]
    assert "max_output_chars" not in properties


class TestCancellation:
    """Tests for agent cancellation via cancel() / _cancel_event."""

    @pytest.mark.asyncio
    async def test_cancel_during_tool_execution(self, tmp_path: Path) -> None:
        """Cancel during code execution yields Cancelled(phase='tool_execution')."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )

        async def cancel_on_exec(self: Agent, code: str) -> Any:  # type: ignore[override]
            self._cancel_event.set()
            yield CodeExecutionOutput(text="output", images=[])

        async with patched_agent(stream_function, cancel_on_exec, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == "tool_execution"
        assert len(results.code_outputs) == 1

    @pytest.mark.asyncio
    async def test_cancel_during_llm_streaming(self, tmp_path: Path) -> None:
        """Cancel during LLM streaming preserves partial response and yields Cancelled."""
        agent_ref: list[Agent | None] = [None]

        async def stream_function(messages: Any, info: Any) -> Any:
            yield "partial response"
            if agent_ref[0] is not None:
                agent_ref[0]._cancel_event.set()
            yield " more text"

        async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
            agent_ref[0] = agent
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == "llm_streaming"
        assert len(results.responses) == 1

    @pytest.mark.asyncio
    async def test_cancel_during_approval_wait(self, tmp_path: Path) -> None:
        """Cancel during approval wait produces interrupted tool return."""
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
                        agent._cancel_event.set()

        cancelled = [e for e in events if isinstance(e, Cancelled)]
        assert len(cancelled) == 1
        assert cancelled[0].phase == "tool_execution"

        tool_returns = get_tool_return_parts(agent._message_history)
        assert len(tool_returns) == 1
        assert tool_returns[0].content == "Interrupted by user"
        assert tool_returns[0].metadata.get("interrupted") is True

    def test_approve_after_future_resolved_is_noop(self) -> None:
        """approve() after future already resolved is a no-op (no InvalidStateError).

        When cancel races with terminal approval, both paths may try to
        resolve the same ApprovalRequest._future. The second call must
        not raise InvalidStateError.
        """
        approval = ApprovalRequest(
            agent_id="main",
            corr_id="test",
            tool_call=CodeAction(tool_name="ipybox_execute_ipython_cell", code="print(1)"),
        )
        # Simulate _await_approval_or_cancel resolving the future first
        approval._future.set_result(False)
        assert approval._future.done()
        # Simulate terminal calling approve() after cancel unblocks _handle_approval
        approval.approve(False)  # no InvalidStateError
        approval.approve(True)  # also safe with different value

    @pytest.mark.asyncio
    async def test_cancel_produces_synthetic_returns_for_orphaned_calls(self, tmp_path: Path) -> None:
        """Cancel during LLM streaming with tool calls generates synthetic returns."""
        agent_ref: list[Agent | None] = [None]

        async def stream_function(messages: Any, info: Any) -> Any:
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
                    agent_ref[0]._cancel_event.set()
                yield "done"

        async with patched_agent(stream_function, tmp_dir=tmp_path) as agent:
            agent_ref[0] = agent
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == "llm_streaming"

        tool_returns = get_tool_return_parts(agent._message_history)
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

        async def cancel_no_output(self: Agent, code: str) -> Any:  # type: ignore[override]
            self._cancel_event.set()
            # ipybox cancel() causes stream() to return without yielding CodeExecutionResult,
            # so _ipybox_execute_ipython_cell ends without yielding CodeExecutionOutput.
            return
            yield  # make this an async generator  # noqa: RUF028

        async with patched_agent(stream_function, cancel_no_output, tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == "tool_execution"
        assert len(results.code_outputs) == 0

        tool_returns = get_tool_return_parts(agent._message_history)
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

        async with patched_agent(stream_function, create_code_exec_function("output"), tmp_dir=tmp_path) as agent:
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 0
        assert len(results.approvals) == 1
        assert len(results.code_outputs) == 1
        assert len(results.responses) >= 1


class TestGeneratorExitRejectsIpyboxApproval:
    """Tests that GeneratorExit during pending ipybox approvals rejects them.

    When the agent generator is closed while a shell, shell_magic, or PTC
    approval is pending, the ipybox ApprovalRequest must be rejected so the
    tool server's approval channel is properly unblocked.
    """

    @staticmethod
    def _make_ipybox_approval(
        server_name: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> tuple[ipybox.ApprovalRequest, asyncio.Event]:
        """Create an ipybox ApprovalRequest with a mock respond that tracks rejection."""
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

    @staticmethod
    def _make_agent_with_mock_stream(tmp_path: Path, mock_stream: Any) -> Agent:
        """Create an agent with a mock code executor stream."""
        agent = build_agent(tmp_path)
        agent._code_executor = MagicMock()
        agent._code_executor.stream = mock_stream
        agent._code_executor_lock = asyncio.Lock()
        return agent

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
        """GeneratorExit during a pending approval rejects the ipybox ApprovalRequest."""
        ipybox_approval, rejected = self._make_ipybox_approval(server_name, tool_name, tool_args)

        async def mock_stream(code: str, timeout: float | None = None, chunks: bool = False) -> Any:
            yield ipybox_approval
            # Simulate kernel blocked on request_sync waiting for approval
            await asyncio.Event().wait()

        agent = self._make_agent_with_mock_stream(tmp_path, mock_stream)

        gen = agent._ipybox_execute_ipython_cell(code)
        event = await gen.__anext__()
        assert isinstance(event, ApprovalRequest)
        assert event.tool_call.tool_name == expected_tool_name

        # Close the generator without resolving the freeact approval
        await gen.aclose()  # type: ignore[attr-defined]

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

        async def mock_stream(code: str, timeout: float | None = None, chunks: bool = False) -> Any:
            yield ipybox_approval
            decision = await ipybox_approval.response()
            if decision:
                yield ipybox.CodeExecutionResult(text="output", images=[])
            else:
                yield ipybox.CodeExecutionResult(text="rejected", images=[])

        agent = self._make_agent_with_mock_stream(tmp_path, mock_stream)

        gen = agent._ipybox_execute_ipython_cell("!rm -rf /")
        event = await gen.__anext__()
        assert isinstance(event, ApprovalRequest)

        # Reject via normal path (simulate user pressing 'n')
        event.approve(False)

        # Consume remaining events
        events = [e async for e in gen]
        assert len(events) == 1  # CodeExecutionOutput
        assert isinstance(events[0], CodeExecutionOutput)

        # reject() should have been called exactly once (not by GeneratorExit handler)
        assert reject_count == 1
