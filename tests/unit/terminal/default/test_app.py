from collections.abc import AsyncIterator, Callable, Sequence

import pytest
from pydantic_ai import UserContent
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.keys import Keys
from textual.pilot import Pilot

from freeact.agent.events import (
    AgentEvent,
    ApprovalRequest,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.terminal.default.app import FreeactApp, convert_at_references
from freeact.terminal.default.screens import FilePickerScreen
from freeact.terminal.default.widgets import PromptInput

MAIN_AGENT_ID = "main-agent"

PromptContent = str | Sequence[UserContent]
ScenarioFn = Callable[[PromptContent], AsyncIterator[AgentEvent]]


class MockStreamAgent:
    """Deterministic agent stream helper for Textual app tests."""

    def __init__(self, scenario: ScenarioFn) -> None:
        self._scenario = scenario
        self.prompts: list[PromptContent] = []

    async def stream(self, content: PromptContent) -> AsyncIterator[AgentEvent]:
        self.prompts.append(content)
        async for event in self._scenario(content):
            yield event


class StubPermissionManager:
    """Permission manager stub with configurable pre-approval behavior."""

    def __init__(self, preapproved: bool = False) -> None:
        self._preapproved = preapproved
        self.allow_always_calls: list[str] = []
        self.allow_session_calls: list[str] = []

    def is_allowed(self, tool_name: str, tool_args: dict[str, object] | None = None) -> bool:
        return self._preapproved

    async def allow_always(self, tool_name: str) -> None:
        self.allow_always_calls.append(tool_name)

    def allow_session(self, tool_name: str) -> None:
        self.allow_session_calls.append(tool_name)


async def _no_events(_: PromptContent) -> AsyncIterator[AgentEvent]:
    if False:
        yield Response(content="", agent_id=MAIN_AGENT_ID)


async def _submit_prompt(app: FreeactApp, pilot: Pilot, text: str = "hello") -> None:
    prompt = app.query_one("#prompt-input", PromptInput)
    prompt.insert(text)
    await pilot.press("enter")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("See @image.png", "See <attachment>image.png</attachment>"),
        ("@a.png and @b.jpg", "<attachment>a.png</attachment> and <attachment>b.jpg</attachment>"),
    ],
)
def test_convert_at_references(text: str, expected: str) -> None:
    assert convert_at_references(text) == expected


@pytest.mark.asyncio
async def test_enter_submits_prompt_clears_input_and_mounts_user_box() -> None:
    agent = MockStreamAgent(_no_events)
    app = FreeactApp(agent_stream=agent.stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot, "  hello world  ")
        await app.workers.wait_for_complete()

        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == ""
        assert not prompt.disabled
        assert len(app.query(".user-input-box")) == 1

    assert agent.prompts == ["hello world"]


@pytest.mark.asyncio
async def test_ctrl_j_inserts_newline_without_submitting() -> None:
    agent = MockStreamAgent(_no_events)
    app = FreeactApp(agent_stream=agent.stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        await pilot.press("h", "i")
        await pilot.press("ctrl+j")

        assert prompt.text == "hi\n"
        assert agent.prompts == []


@pytest.mark.asyncio
async def test_alt_enter_contract_maps_to_ctrl_j_and_ctrl_j_inserts_newline() -> None:
    assert ANSI_SEQUENCES_KEYS["\x1b\r"] == (Keys.ControlJ,)

    agent = MockStreamAgent(_no_events)
    app = FreeactApp(agent_stream=agent.stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        await pilot.press("x")
        await pilot.press("ctrl+j")
        assert prompt.text == "x\n"


@pytest.mark.asyncio
async def test_thoughts_stream_collapses_on_terminal_event() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        yield ThoughtsChunk(content="thinking...", agent_id=MAIN_AGENT_ID)
        yield Thoughts(content="thinking...", agent_id=MAIN_AGENT_ID)

    app = FreeactApp(agent_stream=MockStreamAgent(scenario).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        box = app.query(".thoughts-box").last()
        assert box.collapsed


@pytest.mark.asyncio
async def test_response_stream_only_mounts_for_main_agent() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        yield ResponseChunk(content="ignore me", agent_id="other-agent")
        yield Response(content="ignore me", agent_id="other-agent")
        yield ResponseChunk(content="show me", agent_id=MAIN_AGENT_ID)
        yield Response(content="show me", agent_id=MAIN_AGENT_ID)

    app = FreeactApp(agent_stream=MockStreamAgent(scenario).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        response_boxes = app.query(".response-box")
        assert len(response_boxes) == 1
        assert MAIN_AGENT_ID in response_boxes.last().title


@pytest.mark.asyncio
async def test_approval_yes_collapses_action_and_mounts_tool_output() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = FreeactApp(agent_stream=MockStreamAgent(scenario).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        assert len(app.query("ApprovalBar")) == 1
        await pilot.press("y")
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 1


@pytest.mark.asyncio
async def test_approval_enter_works_after_clicking_other_widget() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = FreeactApp(agent_stream=MockStreamAgent(scenario).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.click(".user-input-box")
        await pilot.press("enter")
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 1


@pytest.mark.asyncio
async def test_approval_no_keeps_action_expanded_and_skips_tool_output() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = FreeactApp(agent_stream=MockStreamAgent(scenario).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("n")
        await app.workers.wait_for_complete()

        assert not app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 0


@pytest.mark.asyncio
async def test_approval_always_calls_allow_always() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = FreeactApp(
        agent_stream=MockStreamAgent(scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("a")
        await app.workers.wait_for_complete()

    assert permission_manager.allow_always_calls == ["database_query"]


@pytest.mark.asyncio
async def test_approval_session_calls_allow_session() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = FreeactApp(
        agent_stream=MockStreamAgent(scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("s")
        await app.workers.wait_for_complete()

    assert permission_manager.allow_session_calls == ["database_query"]


@pytest.mark.asyncio
async def test_preapproved_request_skips_approval_bar() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = FreeactApp(
        agent_stream=MockStreamAgent(scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 1


@pytest.mark.asyncio
async def test_stream_exception_renders_error_and_reenables_input() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        raise RuntimeError("boom")
        if False:
            yield Response(content="", agent_id=MAIN_AGENT_ID)

    app = FreeactApp(agent_stream=MockStreamAgent(scenario).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        prompt = app.query_one("#prompt-input", PromptInput)
        assert not prompt.disabled
        assert len(app.query(".error-box")) == 1


@pytest.mark.asyncio
async def test_typing_at_opens_file_picker_screen() -> None:
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.press("@")
        await pilot.pause(0.05)

        assert any(isinstance(screen, FilePickerScreen) for screen in app.screen_stack)
