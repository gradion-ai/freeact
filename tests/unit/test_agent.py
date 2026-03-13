import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.models.function import DeltaToolCall

import freeact.agent.core as agent_core
from freeact.agent import Agent, ApprovalRequest, Cancelled, CodeExecutionOutput
from freeact.agent.call import CodeAction, GenericCall
from freeact.agent.config import Config
from tests.helpers import (
    CodeExecFunction,
    collect_stream,
    create_stream_function,
    create_test_config,
    get_tool_return_parts,
    patched_agent,
)


class TestCodeExecutionOutput:
    """Tests for CodeExecutionOutput dataclass methods."""

    def test_ptc_rejected_returns_false_when_text_is_none(self):
        """ptc_rejected() returns False when text is None."""
        output = CodeExecutionOutput(text=None, images=[])
        assert output.ptc_rejected() is False

    def test_ptc_rejected_detects_rejection(self):
        """ptc_rejected() detects ApprovalRejectedError in output."""
        output = CodeExecutionOutput(
            text="ApprovalRejectedError: Approval request for my_tool rejected",
            images=[],
        )
        assert output.ptc_rejected() is True

    def test_ptc_rejected_returns_false_for_normal_output(self):
        """ptc_rejected() returns False for normal output."""
        output = CodeExecutionOutput(text="Normal output", images=[])
        assert output.ptc_rejected() is False

    def test_format_returns_full_content(self):
        """format() returns full text when no images are present."""
        output = CodeExecutionOutput(text="Short text", images=[])
        assert output.format() == "Short text"

    def test_format_keeps_long_output_untruncated(self):
        """format() returns full long text output."""
        long_text = "x" * 1000
        output = CodeExecutionOutput(text=long_text, images=[])
        result = output.format()
        assert result == long_text

    def test_format_includes_image_markdown(self):
        """format() appends image markdown links."""
        output = CodeExecutionOutput(
            text="Output",
            images=[Path("/tmp/img1.png"), Path("/tmp/img2.png")],
        )
        result = output.format()
        assert "![Image](/tmp/img1.png)" in result
        assert "![Image](/tmp/img2.png)" in result

    def test_format_returns_empty_when_no_content(self):
        """format() returns empty string when no text or images."""
        output = CodeExecutionOutput(text=None, images=[])
        assert output.format() == ""

    def test_format_with_only_images(self):
        """format() works with only images and no text."""
        output = CodeExecutionOutput(
            text=None,
            images=[Path("/tmp/image.png")],
        )
        result = output.format()
        assert result == "![Image](/tmp/image.png)"

    def test_format_keeps_text_and_images_untruncated(self):
        """format() returns full text plus image markdown links."""
        output = CodeExecutionOutput(
            text="x" * 100,
            images=[Path("/tmp/image.png")],
        )
        result = output.format()
        assert result == f"{'x' * 100}\n![Image](/tmp/image.png)"


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
        approval = ApprovalRequest(
            tool_call=GenericCall(tool_name=tool_name, tool_args=tool_args, ptc=True),
        )
        yield approval
        if await approval.approved():
            yield CodeExecutionOutput(text=approved_result, images=[])
        else:
            yield CodeExecutionOutput(text=rejected_result, images=[])

    return execute


class _FakeMcpServer:
    def __init__(self, *, tool_prefix: str, result: object) -> None:
        self.tool_prefix = tool_prefix
        self._result = result
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def direct_call_tool(self, name: str, args: dict[str, object]) -> object:
        self.calls.append((name, args))
        return self._result


class TestMcpFilesystemResultExtraction:
    @pytest.mark.asyncio
    async def test_filesystem_read_text_file_extracts_content_from_json_string(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config())

        server = _FakeMcpServer(
            tool_prefix="filesystem",
            result=json.dumps({"content": "file text"}),
        )
        agent._tool_mapping["filesystem_read_text_file"] = server  # type: ignore[assignment]

        result = await agent._call_mcp_tool("filesystem_read_text_file", {"path": "README.md"})

        assert result == "file text"
        assert server.calls == [("read_text_file", {"path": "README.md"})]

    @pytest.mark.asyncio
    async def test_filesystem_read_multiple_files_extracts_content_from_dict(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config())

        server = _FakeMcpServer(
            tool_prefix="filesystem",
            result={"content": "merged file text"},
        )
        agent._tool_mapping["filesystem_read_multiple_files"] = server  # type: ignore[assignment]

        result = await agent._call_mcp_tool(
            "filesystem_read_multiple_files",
            {"paths": ["a.txt", "b.txt"]},
        )

        assert result == "merged file text"
        assert server.calls == [("read_multiple_files", {"paths": ["a.txt", "b.txt"]})]

    @pytest.mark.asyncio
    async def test_non_filesystem_tools_are_not_special_cased(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config())

        raw = json.dumps({"content": "should-stay-raw"})
        server = _FakeMcpServer(tool_prefix="test", result=raw)
        agent._tool_mapping["test_tool_2"] = server  # type: ignore[assignment]

        result = await agent._call_mcp_tool("test_tool_2", {"s": "x"})

        assert result == raw
        assert server.calls == [("tool_2", {"s": "x"})]


class TestSessionPersistenceConfig:
    def test_agent_generates_session_id_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        generated = uuid.uuid4()
        monkeypatch.setattr("freeact.agent.core.uuid.uuid4", lambda: generated)

        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config())

        assert agent._session_id == str(generated)
        assert agent.session_id == str(generated)

    def test_agent_uses_provided_session_id(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config(), session_id="session-1")

        assert agent.session_id == "session-1"

    def test_agent_creates_internal_session_store_when_enabled(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config())

        assert agent._session_id is not None
        assert agent._session_store is not None

    def test_agent_runs_without_session_store_when_disabled(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config(enable_persistence=False))

        assert agent._session_id is None
        assert agent.session_id is None
        assert agent._session_store is None
        assert agent._result_materializer is None

    def test_agent_rejects_session_id_when_persistence_disabled(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            with pytest.raises(ValueError, match="session_id requires config.enable_persistence=True"):
                Agent(config=create_test_config(enable_persistence=False), session_id="session-1")


class TestFilesystemMcpServerStdio:
    @pytest.mark.asyncio
    async def test_client_streams_redirects_stderr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        class _DummyStream:
            async def __aenter__(self) -> tuple[object, object]:
                return object(), object()

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

        def fake_stdio_client(*, server: object, errlog: object) -> _DummyStream:
            captured["server"] = server
            captured["errlog"] = errlog
            return _DummyStream()

        monkeypatch.setattr(agent_core, "stdio_client", fake_stdio_client)

        server = agent_core._FilesystemMCPServerStdio(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "."],
            excluded_tools=frozenset({"read_file"}),
        )

        async with server.client_streams():
            pass

        assert captured["errlog"] is not sys.stderr

    def test_create_mcp_servers_uses_filesystem_special_case(self) -> None:
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = create_test_config(
                mcp_servers={
                    "filesystem": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                        "excluded_tools": ["read_file"],
                    }
                }
            )
            agent = Agent(config=config)

        servers = agent._create_mcp_servers()
        assert isinstance(servers["filesystem"], agent_core._FilesystemMCPServerStdio)


class TestIpyboxExecution:
    """Tests for ipybox_execute_ipython_cell tool with mocked code executor."""

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
            assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
            assert isinstance(results.approvals[0].tool_call, CodeAction)
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
            assert results.approvals[0].tool_call.tool_name == "ipybox_execute_ipython_cell"
            assert results.approvals[1].tool_call.tool_name == "test_tool_2"
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
        # rejected_result must contain the class name checked by CodeExecutionOutput.ptc_rejected()
        code_exec_function = create_code_exec_with_approval_function(
            tool_name="test_tool_2",
            tool_args={"s": "ptc_rejected"},
            approved_result="You passed to tool 2: ptc_rejected",
            rejected_result="ApprovalRejectedError: Approval request for test_tool_2 rejected",
        )

        # Approve code execution, reject PTC
        def approve_function(req: ApprovalRequest) -> bool:
            return req.tool_call.tool_name == "ipybox_execute_ipython_cell"

        async with patched_agent(stream_function, code_exec_function) as agent:
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

    def test_default_execution_timeout(self):
        """Default execution_timeout is 300 seconds."""
        with patch("freeact.agent.core.ipybox.CodeExecutor"):
            config = create_test_config()
            agent = Agent(config=config)
            assert agent._execution_timeout == 300

    def test_custom_execution_timeout(self):
        """Custom execution_timeout is stored."""
        with patch("freeact.agent.core.ipybox.CodeExecutor"):
            config = create_test_config(execution_timeout=60)
            agent = Agent(config=config)
            assert agent._execution_timeout == 60

    def test_none_execution_timeout(self):
        """None execution_timeout disables timeout."""
        with patch("freeact.agent.core.ipybox.CodeExecutor"):
            config = create_test_config(execution_timeout=None)
            agent = Agent(config=config)
            assert agent._execution_timeout is None

    def test_approval_timeout_passed_to_executor(self):
        """approval_timeout is passed to CodeExecutor."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = create_test_config(approval_timeout=30)
            Agent(config=config)
            mock_executor.assert_called_once()
            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["approval_timeout"] == 30

    def test_default_approval_timeout_is_none(self):
        """Default approval_timeout is None."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = create_test_config()
            Agent(config=config)
            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["approval_timeout"] is None


class TestKernelEnvHome:
    """Tests for default HOME environment variable in kernel_env."""

    def test_default_home_env_var(self):
        """HOME from os.environ is added to kernel_env by Config."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = create_test_config()
            Agent(config=config)
            call_kwargs = mock_executor.call_args.kwargs
            # HOME is auto-added by Config._load_kernel_env()
            assert "HOME" in call_kwargs["kernel_env"]

    def test_home_env_var_not_overridden(self):
        """User-provided HOME in kernel_env is not overwritten."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = create_test_config(kernel_env={"HOME": "/custom/home"})
            Agent(config=config)
            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["kernel_env"]["HOME"] == "/custom/home"


class TestSubagentConfigPropagation:
    """Tests that subagents inherit parent runtime/safety configuration."""

    @pytest.mark.asyncio
    async def test_execute_subagent_task_propagates_runtime_and_safety_settings(self):
        """_execute_subagent_task forwards parent config to spawned subagents."""
        captured: dict[str, Any] = {}

        class FakeSubagent:
            def __init__(self, config: Config, agent_id: str | None = None, **kwargs: Any):
                captured["config"] = config
                captured["agent_id"] = agent_id
                captured.update(kwargs)
                self.agent_id = agent_id or "main"

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args: object) -> None:
                return None

            async def stream(self, prompt: str, max_turns: int | None = None):
                from freeact.agent.events import Response

                yield Response(content="done", agent_id=self.agent_id)

        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = create_test_config(
                kernel_env={"HOME": "/custom/home", "OTHER": "value"},
                images_dir=Path("/tmp/images"),
                approval_timeout=42,
            )
            agent = Agent(
                config=config,
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
    async def test_cancel_propagates_to_subagent_code_executor(self):
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

            async def stream(self, prompt: str, max_turns: int | None = None):  # type: ignore[return]
                from freeact.agent.events import Response

                yield Response(content="working", agent_id=self.agent_id)
                try:
                    await asyncio.wait_for(subagent_executor_cancelled.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
                yield Response(content="done", agent_id=self.agent_id)

        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            agent = Agent(config=create_test_config())

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


class TestSubagentDefaults:
    """Tests for subagent tool definition defaults."""

    def test_default_max_turns(self):
        """Default max_turns for subagent_task is 100."""
        import json

        from freeact.tools.utils import SUBAGENT_TOOL_DEFS_PATH

        schema = json.loads(SUBAGENT_TOOL_DEFS_PATH.read_text())
        max_turns_schema = schema[0]["parameters_json_schema"]["properties"]["max_turns"]
        assert max_turns_schema["default"] == 100


class TestIpyboxToolSchema:
    """Tests for bundled ipybox tool definition schema."""

    def test_execute_schema_has_no_max_output_chars(self):
        """ipybox_execute_ipython_cell does not expose output truncation args."""
        import json

        from freeact.tools.utils import IPYBOX_TOOL_DEFS_PATH

        schema = json.loads(IPYBOX_TOOL_DEFS_PATH.read_text())
        execute_schema = next(item for item in schema if item["name"] == "ipybox_execute_ipython_cell")
        properties = execute_schema["parameters_json_schema"]["properties"]
        assert "max_output_chars" not in properties


class TestCancellation:
    """Tests for agent cancellation via cancel() / _cancel_event."""

    @pytest.mark.asyncio
    async def test_cancel_during_tool_execution(self):
        """Cancel during code execution yields Cancelled(phase='tool_execution')."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )

        async def cancel_on_exec(self: Agent, code: str):  # type: ignore[override]
            self._cancel_event.set()
            yield CodeExecutionOutput(text="output", images=[])

        async with patched_agent(stream_function, cancel_on_exec) as agent:
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == "tool_execution"
        assert len(results.code_outputs) == 1

    @pytest.mark.asyncio
    async def test_cancel_during_llm_streaming(self):
        """Cancel during LLM streaming preserves partial response and yields Cancelled."""
        agent_ref: list[Agent | None] = [None]

        async def stream_function(messages: Any, info: Any) -> Any:
            yield "partial response"
            if agent_ref[0] is not None:
                agent_ref[0]._cancel_event.set()
            yield " more text"

        async with patched_agent(stream_function) as agent:
            agent_ref[0] = agent
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == "llm_streaming"
        assert len(results.responses) == 1

    @pytest.mark.asyncio
    async def test_cancel_during_approval_wait(self):
        """Cancel during approval wait produces interrupted tool return."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )

        async with patched_agent(stream_function) as agent:
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

    def test_approve_after_future_resolved_is_noop(self):
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
    async def test_cancel_produces_synthetic_returns_for_orphaned_calls(self):
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

        async with patched_agent(stream_function) as agent:
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
    async def test_cancel_during_execution_with_empty_output(self):
        """Cancel during code execution with no output yields interrupted tool return."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "import time; time.sleep(30)"},
        )

        async def cancel_no_output(self: Agent, code: str):  # type: ignore[override]
            self._cancel_event.set()
            # ipybox cancel() causes stream() to return without yielding CodeExecutionResult,
            # so _ipybox_execute_ipython_cell ends without yielding CodeExecutionOutput.
            return
            yield  # make this an async generator  # noqa: RUF028

        async with patched_agent(stream_function, cancel_no_output) as agent:
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 1
        assert results.cancelled[0].phase == "tool_execution"
        assert len(results.code_outputs) == 0

        tool_returns = get_tool_return_parts(agent._message_history)
        assert len(tool_returns) == 1
        assert tool_returns[0].content == "Interrupted by user"
        assert tool_returns[0].metadata.get("interrupted") is True

    @pytest.mark.asyncio
    async def test_stream_without_cancel_unchanged(self):
        """Normal stream behavior is unchanged when cancel is never set."""
        stream_function = create_stream_function(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print(1)"},
        )

        async with patched_agent(stream_function, create_code_exec_function("output")) as agent:
            results = await collect_stream(agent, "test")

        assert len(results.cancelled) == 0
        assert len(results.approvals) == 1
        assert len(results.code_outputs) == 1
        assert len(results.responses) >= 1
