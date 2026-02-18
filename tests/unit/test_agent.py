import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from freeact.agent import Agent, ApprovalRequest, CodeExecutionOutput
from freeact.agent.config import Config
from freeact.agent.config.config import _ConfigPaths
from tests.conftest import (
    CodeExecFunction,
    collect_stream,
    create_stream_function,
    patched_agent,
)


def _create_test_config(**overrides: Any) -> Config:
    """Create a Config with a temp .freeact dir and optional attribute overrides."""
    tmp_dir = Path(tempfile.mkdtemp())
    freeact_dir = _ConfigPaths(tmp_dir).freeact_dir
    freeact_dir.mkdir()
    (freeact_dir / "config.json").write_text(json.dumps({"model": "test"}))
    config = Config(working_dir=tmp_dir)
    config.mcp_servers = {}
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


class TestCodeExecutionOutput:
    """Tests for CodeExecutionOutput dataclass methods."""

    def test_ptc_rejected_returns_false_when_text_is_none(self):
        """ptc_rejected() returns False when text is None."""
        output = CodeExecutionOutput(text=None, images=[])
        assert output.ptc_rejected() is False

    def test_ptc_rejected_detects_rejection_pattern(self):
        """ptc_rejected() detects ToolRunnerError pattern."""
        output = CodeExecutionOutput(
            text="ToolRunnerError: Approval request for my_tool rejected",
            images=[],
        )
        assert output.ptc_rejected() is True

    def test_ptc_rejected_returns_false_for_normal_output(self):
        """ptc_rejected() returns False for normal output."""
        output = CodeExecutionOutput(text="Normal output", images=[])
        assert output.ptc_rejected() is False

    def test_format_returns_full_content_when_under_limit(self):
        """format() returns full content when under max_chars."""
        output = CodeExecutionOutput(text="Short text", images=[])
        assert output.format(max_chars=100) == "Short text"

    def test_format_truncates_long_output(self):
        """format() truncates output exceeding max_chars with 80/20 split."""
        long_text = "x" * 1000
        output = CodeExecutionOutput(text=long_text, images=[])
        result = output.format(max_chars=100)
        assert len(result) == 100
        assert result.startswith("x" * 80)
        assert "..." in result
        # 20% of 100 = 20, minus 3 for "..." = 17
        assert result.endswith("x" * 17)

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

    def test_format_truncates_with_images(self):
        """format() truncates when text plus image markdown exceeds limit."""
        output = CodeExecutionOutput(
            text="x" * 100,
            images=[Path("/tmp/image.png")],
        )
        # Text is 100 chars, image markdown is ~24 chars, total ~125
        result = output.format(max_chars=50)
        assert len(result) == 50
        assert "..." in result


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


class TestTimeoutParameters:
    """Tests for execution_timeout and approval_timeout parameters."""

    def test_default_execution_timeout(self):
        """Default execution_timeout is 300 seconds."""
        with patch("freeact.agent.core.ipybox.CodeExecutor"):
            config = _create_test_config()
            agent = Agent(config=config)
            assert agent._execution_timeout == 300

    def test_custom_execution_timeout(self):
        """Custom execution_timeout is stored."""
        with patch("freeact.agent.core.ipybox.CodeExecutor"):
            config = _create_test_config(execution_timeout=60)
            agent = Agent(config=config)
            assert agent._execution_timeout == 60

    def test_none_execution_timeout(self):
        """None execution_timeout disables timeout."""
        with patch("freeact.agent.core.ipybox.CodeExecutor"):
            config = _create_test_config(execution_timeout=None)
            agent = Agent(config=config)
            assert agent._execution_timeout is None

    def test_approval_timeout_passed_to_executor(self):
        """approval_timeout is passed to CodeExecutor."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = _create_test_config(approval_timeout=30)
            Agent(config=config)
            mock_executor.assert_called_once()
            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["approval_timeout"] == 30

    def test_default_approval_timeout_is_none(self):
        """Default approval_timeout is None."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = _create_test_config()
            Agent(config=config)
            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["approval_timeout"] is None


class TestKernelEnvHome:
    """Tests for default HOME environment variable in kernel_env."""

    def test_default_home_env_var(self):
        """HOME from os.environ is added to kernel_env by Config."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = _create_test_config()
            Agent(config=config)
            call_kwargs = mock_executor.call_args.kwargs
            # HOME is auto-added by Config._load_kernel_env()
            assert "HOME" in call_kwargs["kernel_env"]

    def test_home_env_var_not_overridden(self):
        """User-provided HOME in kernel_env is not overwritten."""
        with patch("freeact.agent.core.ipybox.CodeExecutor") as mock_executor:
            mock_executor.return_value = MagicMock()
            config = _create_test_config(kernel_env={"HOME": "/custom/home"})
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
            config = _create_test_config(
                kernel_env={"HOME": "/custom/home", "OTHER": "value"},
                images_dir=Path("/tmp/images"),
                approval_timeout=42,
            )
            agent = Agent(
                config=config,
                sandbox=True,
                sandbox_config=Path("/tmp/sandbox.cfg"),
            )

        with patch("freeact.agent.core.Agent", FakeSubagent):
            events = [event async for event in agent._execute_subagent_task("subtask", max_turns=3)]

        assert len(events) >= 1
        sub_config = captured["config"]
        assert sub_config.kernel_env == {"HOME": "/custom/home", "OTHER": "value"}
        assert sub_config.kernel_env is not config.kernel_env
        assert captured["agent_id"].startswith("sub-")
        assert sub_config.enable_subagents is False
        assert captured["sandbox"] is True
        assert captured["sandbox_config"] == Path("/tmp/sandbox.cfg")
