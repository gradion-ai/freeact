from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

import pytest
from pydantic_ai import UserContent
from rich.text import Text
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.keys import Keys
from textual.pilot import Pilot
from textual.widgets import Static

from freeact.agent.events import (
    AgentEvent,
    ApprovalRequest,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.terminal.default.app import (
    AtReferenceContext,
    FreeactApp,
    _find_at_reference_context,
    _format_attachment_path,
    convert_at_references,
)
from freeact.terminal.default.config import ExpandCollapsePolicy, TerminalKeyConfig, TerminalUiConfig
from freeact.terminal.default.screens import FilePickerScreen, FilePickerTree
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


class StubClipboardAdapter:
    """Clipboard adapter stub with programmable paste responses."""

    def __init__(self, paste_values: list[str | None] | None = None) -> None:
        self.copy_calls: list[str] = []
        self.paste_calls = 0
        self._paste_values = paste_values or []

    def copy(self, text: str) -> bool:
        self.copy_calls.append(text)
        return True

    def paste(self) -> str | None:
        self.paste_calls += 1
        if self._paste_values:
            return self._paste_values.pop(0)
        return None


async def _no_events(_: PromptContent) -> AsyncIterator[AgentEvent]:
    if False:
        yield Response(content="", agent_id=MAIN_AGENT_ID)


async def _response_only_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
    text = "Hello world response text."
    yield ResponseChunk(content=text, agent_id=MAIN_AGENT_ID)
    yield Response(content=text, agent_id=MAIN_AGENT_ID)


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


def test_find_at_reference_context_extracts_token_range() -> None:
    text = "Attach @docs/readme.md now"
    context = _find_at_reference_context(text, (0, text.index("@") + 1))

    assert context is not None
    assert context.start == (0, text.index("@") + 1)
    assert context.end == (0, text.index(" now"))


def test_find_at_reference_context_requires_cursor_after_at() -> None:
    text = "Attach @docs/readme.md now"
    assert _find_at_reference_context(text, (0, 0)) is None
    assert _find_at_reference_context(text, (0, text.index("@") + 2)) is None


def test_format_attachment_path_prefers_relative_to_cwd(tmp_path: Path) -> None:
    nested = tmp_path / "assets" / "images"
    nested.mkdir(parents=True)

    assert _format_attachment_path(nested, cwd=tmp_path) == "assets/images"


@pytest.mark.asyncio
async def test_banner_renders_inside_conversation_scroll_container(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("freeact.terminal.default.app._load_banner", lambda: Text("banner"))
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        conversation = app.query_one("#conversation")
        banner = app.query_one("#banner", Static)
        assert banner.parent is conversation
        assert conversation.max_scroll_y == 0
        assert banner.region.y >= conversation.region.bottom - 3


@pytest.mark.asyncio
async def test_banner_viewport_starts_scrolled_to_bottom(monkeypatch: pytest.MonkeyPatch) -> None:
    tall_banner = Text("\n".join(["banner"] * 120))
    monkeypatch.setattr("freeact.terminal.default.app._load_banner", lambda: tall_banner)
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        conversation = app.query_one("#conversation")
        assert conversation.max_scroll_y > 0
        assert conversation.scroll_y == conversation.max_scroll_y


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
async def test_markdown_link_hover_style_is_configured_per_link() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        text = "See [Textual](https://textual.textualize.io/) and [Rich](https://github.com/Textualize/rich)."
        yield ResponseChunk(content=text, agent_id=MAIN_AGENT_ID)
        yield Response(content=text, agent_id=MAIN_AGENT_ID)

    app = FreeactApp(agent_stream=MockStreamAgent(scenario).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        paragraph = app.query("MarkdownParagraph").last()
        assert str(paragraph.styles.link_style) == "underline"
        assert str(paragraph.styles.link_style_hover) == "bold underline"
        assert "Markdown MarkdownBlock:hover" not in FreeactApp.DEFAULT_CSS


@pytest.mark.asyncio
@pytest.mark.parametrize("copy_key", ["super+c", "ctrl+shift+c", "ctrl+insert", "ctrl+c"])
async def test_copy_shortcuts_copy_selected_response_text(copy_key: str) -> None:
    clipboard_adapter = StubClipboardAdapter()
    app = FreeactApp(
        agent_stream=MockStreamAgent(_response_only_scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        clipboard_adapter=clipboard_adapter,
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        paragraph = app.query("MarkdownParagraph").last()
        paragraph.text_select_all()
        await pilot.press(copy_key)

        assert app.clipboard == "Hello world response text."
        assert clipboard_adapter.copy_calls == ["Hello world response text."]


@pytest.mark.asyncio
async def test_user_input_box_text_is_selectable_and_copyable() -> None:
    clipboard_adapter = StubClipboardAdapter()
    app = FreeactApp(
        agent_stream=MockStreamAgent(_no_events).stream,
        main_agent_id=MAIN_AGENT_ID,
        clipboard_adapter=clipboard_adapter,
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot, "copy me from user input")
        await app.workers.wait_for_complete()

        user_input_text = app.query(".user-input-box Static").last()
        user_input_text.text_select_all()
        assert app.screen.get_selected_text() == "copy me from user input"

        await pilot.press("ctrl+c")
        assert app.clipboard == "copy me from user input"
        assert clipboard_adapter.copy_calls == ["copy me from user input"]


@pytest.mark.asyncio
@pytest.mark.parametrize("paste_key", ["ctrl+v", "super+v", "ctrl+shift+v", "shift+insert"])
async def test_paste_shortcuts_use_os_clipboard_value(paste_key: str) -> None:
    clipboard_adapter = StubClipboardAdapter(paste_values=["from-os"])
    app = FreeactApp(
        agent_stream=MockStreamAgent(_no_events).stream,
        main_agent_id=MAIN_AGENT_ID,
        clipboard_adapter=clipboard_adapter,
    )

    async with app.run_test() as pilot:
        await pilot.press(paste_key)
        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == "from-os"
        assert clipboard_adapter.paste_calls == 1
        assert app.clipboard == "from-os"


@pytest.mark.asyncio
async def test_prompt_paste_falls_back_to_local_clipboard_when_os_unavailable() -> None:
    clipboard_adapter = StubClipboardAdapter(paste_values=[None])
    app = FreeactApp(
        agent_stream=MockStreamAgent(_no_events).stream,
        main_agent_id=MAIN_AGENT_ID,
        clipboard_adapter=clipboard_adapter,
    )
    app._clipboard = "local-fallback"

    async with app.run_test() as pilot:
        await pilot.press("ctrl+v")
        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == "local-fallback"


@pytest.mark.asyncio
async def test_prompt_paste_preserves_empty_os_clipboard_without_local_fallback() -> None:
    clipboard_adapter = StubClipboardAdapter(paste_values=[""])
    app = FreeactApp(
        agent_stream=MockStreamAgent(_no_events).stream,
        main_agent_id=MAIN_AGENT_ID,
        clipboard_adapter=clipboard_adapter,
    )
    app._clipboard = "local-fallback"

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt.insert("start")
        await pilot.press("ctrl+v")
        assert prompt.text == "start"
        assert app.clipboard == ""


@pytest.mark.asyncio
async def test_ctrl_q_triggers_quit_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID)
    quit_calls = 0

    async def fake_quit() -> None:
        nonlocal quit_calls
        quit_calls += 1

    monkeypatch.setattr(app, "action_quit", fake_quit)

    async with app.run_test() as pilot:
        await pilot.press("ctrl+q")

    assert quit_calls == 1


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
        assert app.query(".tool-output-box").last().title == r"\[main-agent] \[call-1] Tool Output"


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
async def test_ctrl_o_toggles_expand_all_and_restores_policy() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        yield ThoughtsChunk(content="thinking...", agent_id=MAIN_AGENT_ID)
        yield Thoughts(content="thinking...", agent_id=MAIN_AGENT_ID)
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

        thoughts_box = app.query(".thoughts-box").last()
        output_box = app.query(".tool-output-box").last()
        assert thoughts_box.collapsed
        assert output_box.collapsed

        await pilot.press("ctrl+o")
        assert not thoughts_box.collapsed
        assert not output_box.collapsed

        await pilot.press("ctrl+o")
        assert thoughts_box.collapsed
        assert output_box.collapsed


@pytest.mark.asyncio
async def test_new_collapsible_boxes_render_expanded_while_expand_all_override_is_enabled() -> None:
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
        await pilot.press("ctrl+o")
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        output_box = app.query(".tool-output-box").last()
        assert not output_box.collapsed

        await pilot.press("ctrl+o")
        assert output_box.collapsed


@pytest.mark.asyncio
async def test_toggle_expand_all_uses_configured_hotkey() -> None:
    ui_config = TerminalUiConfig(keys=TerminalKeyConfig(toggle_expand_all="f6"))
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID, ui_config=ui_config)

    async with app.run_test() as pilot:
        assert not app._expand_all_override
        await pilot.press("f6")
        assert app._expand_all_override


@pytest.mark.asyncio
async def test_pending_approval_widget_stays_expanded_until_user_decides() -> None:
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

        action_box = app.query(".tool-call-box").last()
        assert not action_box.collapsed

        await pilot.press("ctrl+o")
        await pilot.press("ctrl+o")
        assert not action_box.collapsed

        await pilot.press("y")
        await app.workers.wait_for_complete()
        assert action_box.collapsed


@pytest.mark.asyncio
async def test_approval_policies_can_disable_auto_collapse() -> None:
    policy = ExpandCollapsePolicy(
        collapse_approved_tool_calls=False,
        keep_rejected_actions_expanded=False,
    )
    ui_config = TerminalUiConfig(expand_collapse=policy)

    async def approved_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-approved",
        )
        yield request
        await request.approved()

    approved_app = FreeactApp(
        agent_stream=MockStreamAgent(approved_scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        ui_config=ui_config,
    )

    async with approved_app.run_test() as pilot:
        await _submit_prompt(approved_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await approved_app.workers.wait_for_complete()
        assert not approved_app.query(".tool-call-box").last().collapsed

    preapproved_app = FreeactApp(
        agent_stream=MockStreamAgent(approved_scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        permission_manager=StubPermissionManager(preapproved=True),  # type: ignore[arg-type]
        ui_config=ui_config,
    )

    async with preapproved_app.run_test() as pilot:
        await _submit_prompt(preapproved_app, pilot)
        await preapproved_app.workers.wait_for_complete()
        assert not preapproved_app.query(".tool-call-box").last().collapsed

    async def rejected_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="call-rejected",
        )
        yield request
        await request.approved()

    rejected_app = FreeactApp(
        agent_stream=MockStreamAgent(rejected_scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        ui_config=ui_config,
    )

    async with rejected_app.run_test() as pilot:
        await _submit_prompt(rejected_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("n")
        await rejected_app.workers.wait_for_complete()
        assert rejected_app.query(".tool-call-box").last().collapsed


@pytest.mark.asyncio
async def test_approved_code_and_tool_collapse_policies_are_independent() -> None:
    policy = ExpandCollapsePolicy(
        collapse_approved_code_actions=False,
        collapse_approved_tool_calls=True,
    )
    ui_config = TerminalUiConfig(expand_collapse=policy)

    async def tool_call_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="tool-call",
        )
        yield request
        await request.approved()

    tool_app = FreeactApp(
        agent_stream=MockStreamAgent(tool_call_scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        ui_config=ui_config,
    )

    async with tool_app.run_test() as pilot:
        await _submit_prompt(tool_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await tool_app.workers.wait_for_complete()
        assert tool_app.query(".tool-call-box").last().collapsed

    async def code_action_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('ok')"},
            agent_id=MAIN_AGENT_ID,
            corr_id="code-action",
        )
        yield request
        await request.approved()

    code_app = FreeactApp(
        agent_stream=MockStreamAgent(code_action_scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        ui_config=ui_config,
    )

    async with code_app.run_test() as pilot:
        await _submit_prompt(code_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await code_app.workers.wait_for_complete()
        assert not code_app.query(".code-action-box").last().collapsed


@pytest.mark.asyncio
async def test_preapproved_code_action_respects_collapse_approved_code_actions() -> None:
    policy = ExpandCollapsePolicy(
        collapse_approved_code_actions=False,
    )
    ui_config = TerminalUiConfig(expand_collapse=policy)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "print('ok')"},
            agent_id=MAIN_AGENT_ID,
            corr_id="code-preapproved",
        )
        yield request
        await request.approved()

    app = FreeactApp(
        agent_stream=MockStreamAgent(scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        permission_manager=StubPermissionManager(preapproved=True),  # type: ignore[arg-type]
        ui_config=ui_config,
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()
        assert not app.query(".code-action-box").last().collapsed


@pytest.mark.asyncio
async def test_preapproved_tool_call_respects_collapse_approved_tool_calls() -> None:
    policy = ExpandCollapsePolicy(
        collapse_approved_tool_calls=False,
    )
    ui_config = TerminalUiConfig(expand_collapse=policy)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_name="database_query",
            tool_args={"query": "SELECT 1"},
            agent_id=MAIN_AGENT_ID,
            corr_id="tool-preapproved",
        )
        yield request
        await request.approved()

    app = FreeactApp(
        agent_stream=MockStreamAgent(scenario).stream,
        main_agent_id=MAIN_AGENT_ID,
        permission_manager=StubPermissionManager(preapproved=True),  # type: ignore[arg-type]
        ui_config=ui_config,
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()
        assert not app.query(".tool-call-box").last().collapsed


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


@pytest.mark.asyncio
async def test_file_picker_starts_at_filesystem_root() -> None:
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.press("@")
        await pilot.pause(0.05)

        picker = next(screen for screen in app.screen_stack if isinstance(screen, FilePickerScreen))
        tree = picker.query_one("#picker-tree", FilePickerTree)
        cwd = Path.cwd().resolve()
        expected_root = Path(cwd.anchor) if cwd.anchor else cwd
        assert tree.path == expected_root


@pytest.mark.asyncio
async def test_file_picker_cursor_starts_at_cwd() -> None:
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.press("@")
        await pilot.pause(0.1)

        picker = next(screen for screen in app.screen_stack if isinstance(screen, FilePickerScreen))
        tree = picker.query_one("#picker-tree", FilePickerTree)
        cursor_node = tree.cursor_node
        assert cursor_node is not None
        assert cursor_node.data is not None
        assert cursor_node.data.path.resolve() == Path.cwd().resolve()


@pytest.mark.asyncio
async def test_file_picker_selection_replaces_existing_at_token() -> None:
    app = FreeactApp(agent_stream=MockStreamAgent(_no_events).stream, main_agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt.insert("See @old value")
        app._open_file_picker(AtReferenceContext(start=(0, 5), end=(0, 8)))
        await pilot.pause(0.05)

        picker = next(screen for screen in app.screen_stack if isinstance(screen, FilePickerScreen))
        picker.dismiss(Path.cwd() / "new")
        await pilot.pause(0.05)

        assert prompt.text == "See @new value"
