import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

import pytest
from pydantic_ai import UserContent
from rich.text import Text
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.keys import Keys
from textual.pilot import Pilot
from textual.widgets import Static

from freeact.agent.call import CodeAction, GenericCall, ShellAction, ToolCall
from freeact.agent.config.skills import SkillMetadata
from freeact.agent.events import (
    AgentEvent,
    ApprovalRequest,
    Cancelled,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.terminal.app import (
    AtReferenceContext,
    SlashCommandContext,
    TerminalApp,
    _find_at_reference_context,
    _find_slash_command_context,
    _format_attachment_path,
    _format_display_cwd,
    _load_freeact_version,
    convert_at_references,
    convert_slash_commands,
)
from freeact.terminal.config import Config as TerminalConfig
from freeact.terminal.screens import FilePickerScreen, FilePickerTree, SkillPickerScreen
from freeact.terminal.widgets import PromptInput

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
        self.allow_always_calls: list[ToolCall] = []
        self.allow_session_calls: list[ToolCall] = []

    def is_allowed(self, tool_call: ToolCall) -> bool:
        return self._preapproved

    def allow_always(self, tool_call: ToolCall) -> None:
        self.allow_always_calls.append(tool_call)

    def allow_session(self, tool_call: ToolCall) -> None:
        self.allow_session_calls.append(tool_call)


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


async def _submit_prompt(app: TerminalApp, pilot: Pilot, text: str = "hello") -> None:
    prompt = app.query_one("#prompt-input", PromptInput)
    prompt.insert(text)
    await pilot.press("enter")


def _create_app(
    *,
    agent_stream: ScenarioFn,
    agent_id: str = MAIN_AGENT_ID,
    config: TerminalConfig | None = None,
    cancel_fn: Callable[[], None] | None = None,
    permission_manager: object | None = None,
    clipboard_adapter: StubClipboardAdapter | None = None,
    skills_metadata: list[SkillMetadata] | None = None,
) -> TerminalApp:
    return TerminalApp(
        config=config or TerminalConfig(),
        agent_id=agent_id,
        agent_stream=agent_stream,
        cancel_fn=cancel_fn,
        permission_manager=permission_manager,  # type: ignore[arg-type]
        clipboard_adapter=clipboard_adapter,
        skills_metadata=skills_metadata,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("See @image.png", 'See <attachment path="image.png"/>'),
        ("@a.png and @b.jpg", '<attachment path="a.png"/> and <attachment path="b.jpg"/>'),
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


def test_format_display_cwd_prefers_tilde_relative_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cwd = home / "work" / "repo"
    cwd.mkdir(parents=True)

    assert _format_display_cwd(cwd=cwd, home=home) == "~/work/repo"


def test_load_freeact_version_omits_local_build_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("freeact.terminal.app.package_version", lambda _: "0.8.1.post1.dev0+6937613")

    assert _load_freeact_version() == "0.8.1.post1.dev0"


@pytest.mark.asyncio
async def test_banner_renders_inside_conversation_scroll_container(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("freeact.terminal.app._load_banner", lambda: Text("banner"))
    monkeypatch.setattr("freeact.terminal.app._load_freeact_version", lambda: "1.2.3")
    monkeypatch.setattr("freeact.terminal.app._format_display_cwd", lambda: "~/repo")
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        conversation = app.query_one("#conversation")
        banner = app.query_one("#banner", Static)
        metadata = app.query_one("#banner-metadata", Static)
        divider = app.query_one("#banner-divider", Static)
        assert banner.parent is conversation
        assert metadata.parent is conversation
        assert divider.parent is conversation
        assert "Version: 1.2.3" in str(metadata.render())
        assert "cwd:" not in str(metadata.render())
        assert "~/repo" in str(metadata.render())
        assert conversation.max_scroll_y == 0
        assert banner.region.y < metadata.region.y < divider.region.y


@pytest.mark.asyncio
async def test_banner_viewport_starts_scrolled_to_bottom(monkeypatch: pytest.MonkeyPatch) -> None:
    tall_banner = Text("\n".join(["banner"] * 120))
    monkeypatch.setattr("freeact.terminal.app._load_banner", lambda: tall_banner)
    monkeypatch.setattr("freeact.terminal.app._load_freeact_version", lambda: "1.2.3")
    monkeypatch.setattr("freeact.terminal.app._format_display_cwd", lambda: "~/repo")
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        conversation = app.query_one("#conversation")
        assert conversation.max_scroll_y > 0
        assert conversation.scroll_y == conversation.max_scroll_y


@pytest.mark.asyncio
async def test_enter_submits_prompt_clears_input_and_mounts_user_box() -> None:
    agent = MockStreamAgent(_no_events)
    app = _create_app(agent_stream=agent.stream, agent_id=MAIN_AGENT_ID)

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
    app = _create_app(agent_stream=agent.stream, agent_id=MAIN_AGENT_ID)

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
    app = _create_app(agent_stream=agent.stream, agent_id=MAIN_AGENT_ID)

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

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

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

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

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

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        paragraph = app.query("MarkdownParagraph").last()
        assert str(paragraph.styles.link_style) == "underline"
        assert str(paragraph.styles.link_style_hover) == "bold underline"
        assert "Markdown MarkdownBlock:hover" not in TerminalApp.DEFAULT_CSS


@pytest.mark.asyncio
@pytest.mark.parametrize("copy_key", ["super+c", "ctrl+shift+c", "ctrl+insert", "ctrl+c"])
async def test_copy_shortcuts_copy_selected_response_text(copy_key: str) -> None:
    clipboard_adapter = StubClipboardAdapter()
    app = _create_app(
        agent_stream=MockStreamAgent(_response_only_scenario).stream,
        agent_id=MAIN_AGENT_ID,
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
    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
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
    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
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
    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
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
    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
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
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID)
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
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

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
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

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
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

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
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert len(permission_manager.allow_always_calls) == 1
    assert isinstance(permission_manager.allow_always_calls[0], GenericCall)
    assert permission_manager.allow_always_calls[0].tool_name == "database_query"


@pytest.mark.asyncio
async def test_approval_session_calls_allow_session() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("s")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert len(permission_manager.allow_session_calls) == 1
    assert isinstance(permission_manager.allow_session_calls[0], GenericCall)
    assert permission_manager.allow_session_calls[0].tool_name == "database_query"


@pytest.mark.asyncio
async def test_preapproved_request_skips_approval_bar() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 1


@pytest.mark.asyncio
async def test_ptc_request_uses_ptc_title_in_default_terminal() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=True),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-ptc",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        assert app.query(".tool-call-box").last().title == r"\[main-agent] \[call-ptc] PTC: database_query"


@pytest.mark.asyncio
async def test_ctrl_o_toggles_expand_all_and_restores_configured_state() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        yield ThoughtsChunk(content="thinking...", agent_id=MAIN_AGENT_ID)
        yield Thoughts(content="thinking...", agent_id=MAIN_AGENT_ID)
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
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
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
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
    ui_config = TerminalConfig(expand_all_toggle_key="f6")
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID, config=ui_config)

    async with app.run_test() as pilot:
        assert not app._expand_all_override
        await pilot.press("f6")
        assert app._expand_all_override


@pytest.mark.asyncio
async def test_pending_approval_widget_stays_expanded_until_user_decides() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

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
async def test_approval_behaviors_can_disable_auto_collapse() -> None:
    ui_config = TerminalConfig(
        collapse_approved_tool_calls=False,
        keep_rejected_actions_expanded=False,
    )

    async def approved_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-approved",
        )
        yield request
        await request.approved()

    approved_app = _create_app(
        agent_stream=MockStreamAgent(approved_scenario).stream,
        agent_id=MAIN_AGENT_ID,
        config=ui_config,
    )

    async with approved_app.run_test() as pilot:
        await _submit_prompt(approved_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await approved_app.workers.wait_for_complete()
        assert not approved_app.query(".tool-call-box").last().collapsed

    preapproved_app = _create_app(
        agent_stream=MockStreamAgent(approved_scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=StubPermissionManager(preapproved=True),  # type: ignore[arg-type]
        config=ui_config,
    )

    async with preapproved_app.run_test() as pilot:
        await _submit_prompt(preapproved_app, pilot)
        await preapproved_app.workers.wait_for_complete()
        assert not preapproved_app.query(".tool-call-box").last().collapsed

    async def rejected_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-rejected",
        )
        yield request
        await request.approved()

    rejected_app = _create_app(
        agent_stream=MockStreamAgent(rejected_scenario).stream,
        agent_id=MAIN_AGENT_ID,
        config=ui_config,
    )

    async with rejected_app.run_test() as pilot:
        await _submit_prompt(rejected_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("n")
        await rejected_app.workers.wait_for_complete()
        assert rejected_app.query(".tool-call-box").last().collapsed


@pytest.mark.asyncio
async def test_approved_code_and_tool_collapse_behaviors_are_independent() -> None:
    ui_config = TerminalConfig(
        collapse_approved_code_actions=False,
        collapse_approved_tool_calls=True,
    )

    async def tool_call_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="tool-call",
        )
        yield request
        await request.approved()

    tool_app = _create_app(
        agent_stream=MockStreamAgent(tool_call_scenario).stream,
        agent_id=MAIN_AGENT_ID,
        config=ui_config,
    )

    async with tool_app.run_test() as pilot:
        await _submit_prompt(tool_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await tool_app.workers.wait_for_complete()
        assert tool_app.query(".tool-call-box").last().collapsed

    async def code_action_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=CodeAction(tool_name="ipybox_execute_ipython_cell", code="print('ok')"),
            agent_id=MAIN_AGENT_ID,
            corr_id="code-action",
        )
        yield request
        await request.approved()

    code_app = _create_app(
        agent_stream=MockStreamAgent(code_action_scenario).stream,
        agent_id=MAIN_AGENT_ID,
        config=ui_config,
    )

    async with code_app.run_test() as pilot:
        await _submit_prompt(code_app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await code_app.workers.wait_for_complete()
        assert not code_app.query(".code-action-box").last().collapsed


@pytest.mark.asyncio
async def test_preapproved_code_action_respects_collapse_approved_code_actions() -> None:
    ui_config = TerminalConfig(
        collapse_approved_code_actions=False,
    )

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=CodeAction(tool_name="ipybox_execute_ipython_cell", code="print('ok')"),
            agent_id=MAIN_AGENT_ID,
            corr_id="code-preapproved",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=StubPermissionManager(preapproved=True),  # type: ignore[arg-type]
        config=ui_config,
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()
        assert not app.query(".code-action-box").last().collapsed


@pytest.mark.asyncio
async def test_preapproved_tool_call_respects_collapse_approved_tool_calls() -> None:
    ui_config = TerminalConfig(
        collapse_approved_tool_calls=False,
    )

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="tool-preapproved",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=StubPermissionManager(preapproved=True),  # type: ignore[arg-type]
        config=ui_config,
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

    app = _create_app(agent_stream=MockStreamAgent(scenario).stream, agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        prompt = app.query_one("#prompt-input", PromptInput)
        assert not prompt.disabled
        assert len(app.query(".error-box")) == 1


@pytest.mark.asyncio
async def test_typing_at_opens_file_picker_screen() -> None:
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        await pilot.press("@")
        await pilot.pause(0.05)

        assert any(isinstance(screen, FilePickerScreen) for screen in app.screen_stack)


@pytest.mark.asyncio
async def test_file_picker_starts_at_filesystem_root() -> None:
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID)

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
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID)

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
    app = _create_app(agent_stream=MockStreamAgent(_no_events).stream, agent_id=MAIN_AGENT_ID)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt.insert("See @old value")
        app._open_file_picker(AtReferenceContext(start=(0, 5), end=(0, 8)))
        await pilot.pause(0.05)

        picker = next(screen for screen in app.screen_stack if isinstance(screen, FilePickerScreen))
        picker.dismiss(Path.cwd() / "new")
        await pilot.pause(0.05)

        assert prompt.text == "See @new value"


# --- convert_slash_commands tests ---


def _make_skill(name: str, tmp_path: Path, description: str = "A skill") -> SkillMetadata:
    skill_dir = tmp_path / name
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(f"---\nname: {name}\ndescription: {description}\n---\n# {name}")
    return SkillMetadata(name=name, description=description, path=skill_file)


def test_convert_slash_commands_known_skill(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    result = convert_slash_commands("/plan my project", [skill])
    assert result == '<skill name="plan">my project</skill>'


def test_convert_slash_commands_no_arguments(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    result = convert_slash_commands("/plan", [skill])
    assert result == '<skill name="plan"></skill>'


def test_convert_slash_commands_unknown_skill(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    result = convert_slash_commands("/unknown foo", [skill])
    assert result == "/unknown foo"


def test_convert_slash_commands_not_at_start(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    result = convert_slash_commands("text /plan foo", [skill])
    assert result == "text /plan foo"


def test_convert_slash_commands_empty_skills_list() -> None:
    result = convert_slash_commands("/plan foo", [])
    assert result == "/plan foo"


def test_convert_slash_commands_multiline_arguments(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    result = convert_slash_commands("/plan arg\nmore", [skill])
    assert result == '<skill name="plan">arg\nmore</skill>'


@pytest.mark.asyncio
async def test_slash_command_is_converted_to_skill_tag_before_agent_receives_prompt(tmp_path: Path) -> None:
    skill = _make_skill("greet", tmp_path, description="Greeting skill")
    agent = MockStreamAgent(_no_events)
    app = _create_app(
        agent_stream=agent.stream,
        agent_id=MAIN_AGENT_ID,
        skills_metadata=[skill],
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot, "/greet world")
        await app.workers.wait_for_complete()

    assert len(agent.prompts) == 1
    assert agent.prompts[0] == '<skill name="greet">world</skill>'


# --- _find_slash_command_context tests ---


def test_find_slash_command_context_at_start() -> None:
    text = "/"
    context = _find_slash_command_context(text, (0, 1))
    assert context is not None
    assert context == SlashCommandContext(start=(0, 1), end=(0, 1))


def test_find_slash_command_context_not_at_start() -> None:
    text = "text /"
    assert _find_slash_command_context(text, (0, 6)) is None


def test_find_slash_command_context_not_first_row() -> None:
    text = "line0\n/"
    assert _find_slash_command_context(text, (1, 1)) is None


def test_find_slash_command_context_cursor_not_after_slash() -> None:
    text = "/plan"
    assert _find_slash_command_context(text, (0, 3)) is None


# --- Skill picker TUI tests ---


@pytest.mark.asyncio
async def test_typing_slash_at_start_opens_skill_picker(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
        skills_metadata=[skill],
    )

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.pause(0.05)

        assert any(isinstance(screen, SkillPickerScreen) for screen in app.screen_stack)


@pytest.mark.asyncio
async def test_skill_picker_selection_inserts_skill_name(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
        skills_metadata=[skill],
    )

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.pause(0.05)

        picker = next(screen for screen in app.screen_stack if isinstance(screen, SkillPickerScreen))
        picker.dismiss("plan")
        await pilot.pause(0.05)

        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == "/plan "


@pytest.mark.asyncio
async def test_slash_in_middle_does_not_open_skill_picker(tmp_path: Path) -> None:
    skill = _make_skill("plan", tmp_path)
    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
        skills_metadata=[skill],
    )

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt.insert("text ")
        await pilot.press("/")
        await pilot.pause(0.05)

        assert not any(isinstance(screen, SkillPickerScreen) for screen in app.screen_stack)


@pytest.mark.asyncio
async def test_skill_picker_to_submission_e2e(tmp_path: Path) -> None:
    """Full flow: type /, pick skill, type args, submit, verify agent receives skill tag."""
    skill = _make_skill("plan", tmp_path)
    agent = MockStreamAgent(_no_events)
    app = _create_app(
        agent_stream=agent.stream,
        agent_id=MAIN_AGENT_ID,
        skills_metadata=[skill],
    )

    async with app.run_test() as pilot:
        # Type / to open picker
        await pilot.press("/")
        await pilot.pause(0.05)

        # Pick the skill
        picker = next(screen for screen in app.screen_stack if isinstance(screen, SkillPickerScreen))
        picker.dismiss("plan")
        await pilot.pause(0.05)

        # Prompt should now be "/plan "
        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == "/plan "

        # Type arguments and submit
        prompt.insert("my project")
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert len(agent.prompts) == 1
    assert agent.prompts[0] == '<skill name="plan">my project</skill>'


# --- Escape key cancellation tests ---


@pytest.mark.asyncio
async def test_escape_during_turn_cancels() -> None:
    cancel_calls = 0

    def fake_cancel() -> None:
        nonlocal cancel_calls
        cancel_calls += 1

    turn_started = asyncio.Event()

    async def slow_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        turn_started.set()
        yield ResponseChunk(content="streaming...", agent_id=MAIN_AGENT_ID)
        # Wait long enough for Escape to be pressed
        await asyncio.sleep(5)
        yield Response(content="streaming...", agent_id=MAIN_AGENT_ID)

    agent = MockStreamAgent(slow_scenario)
    app = _create_app(
        agent_stream=agent.stream,
        agent_id=MAIN_AGENT_ID,
        cancel_fn=fake_cancel,
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("escape")
        await pilot.pause(0.05)

        assert cancel_calls == 1


@pytest.mark.asyncio
async def test_escape_when_idle_does_nothing() -> None:
    cancel_calls = 0

    def fake_cancel() -> None:
        nonlocal cancel_calls
        cancel_calls += 1

    app = _create_app(
        agent_stream=MockStreamAgent(_no_events).stream,
        agent_id=MAIN_AGENT_ID,
        cancel_fn=fake_cancel,
    )

    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause(0.05)

        assert cancel_calls == 0


@pytest.mark.asyncio
async def test_escape_resolves_pending_approval() -> None:
    cancel_calls = 0

    def fake_cancel() -> None:
        nonlocal cancel_calls
        cancel_calls += 1

    async def approval_scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        approved = await request.approved()
        if not approved:
            yield Cancelled(agent_id=MAIN_AGENT_ID, phase="tool_execution")

    agent = MockStreamAgent(approval_scenario)
    app = _create_app(
        agent_stream=agent.stream,
        agent_id=MAIN_AGENT_ID,
        cancel_fn=fake_cancel,
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        assert len(app.query("ApprovalBar")) == 1

        await pilot.press("escape")
        await app.workers.wait_for_complete()

        assert cancel_calls == 1
        assert len(app.query("ApprovalBar")) == 0
        prompt = app.query_one("#prompt-input", PromptInput)
        assert not prompt.disabled


# --- Pattern and domain routing tests ---


@pytest.mark.asyncio
async def test_approval_always_passes_pattern_to_allow_always() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="github_search_repositories", tool_args={"query": "test"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    # Pattern should be the suggested pattern (full tool name)
    assert len(permission_manager.allow_always_calls) == 1
    assert isinstance(permission_manager.allow_always_calls[0], GenericCall)
    assert permission_manager.allow_always_calls[0].tool_name == "github_search_repositories"


@pytest.mark.asyncio
async def test_approval_session_passes_pattern_to_allow_session() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="github_search_repositories", tool_args={"query": "test"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("s")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert len(permission_manager.allow_session_calls) == 1
    assert isinstance(permission_manager.allow_session_calls[0], GenericCall)
    assert permission_manager.allow_session_calls[0].tool_name == "github_search_repositories"


@pytest.mark.asyncio
async def test_shell_approval_request_routes_to_shell_domain() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=ShellAction(tool_name="bash", command="git status"),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    # Shell domain should be used with suggested pattern
    assert len(permission_manager.allow_always_calls) == 1
    assert isinstance(permission_manager.allow_always_calls[0], ShellAction)
    assert permission_manager.allow_always_calls[0].command == "git status *"


@pytest.mark.asyncio
async def test_shell_approval_uses_suggest_shell_pattern() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=ShellAction(tool_name="bash", command="git add /path/to/file.py"),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert len(permission_manager.allow_always_calls) == 1
    assert isinstance(permission_manager.allow_always_calls[0], ShellAction)
    assert permission_manager.allow_always_calls[0].command == "git add *"


@pytest.mark.asyncio
async def test_always_enters_edit_mode_and_enter_saves_and_approves() -> None:
    permission_manager = StubPermissionManager()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        request = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="call-1",
        )
        yield request
        await request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)

        # Press 'a' to enter edit mode for always-allow
        await pilot.press("a")
        await pilot.pause(0.05)

        # Enter saves the pattern and approves in one step
        await pilot.press("enter")
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert len(permission_manager.allow_always_calls) == 1
        assert isinstance(permission_manager.allow_always_calls[0], GenericCall)
        assert permission_manager.allow_always_calls[0].tool_name == "database_query"


@pytest.mark.asyncio
async def test_subagent_widgets_mount_inside_subagent_task_box_and_parent_output_stays_root() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        task_request = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "delegate"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-1",
        )
        yield task_request
        if await task_request.approved():
            child_request = ApprovalRequest(
                tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False),
                agent_id="sub-abcd",
                corr_id="child-1",
                parent_corr_id="task-1",
            )
            yield child_request
            if await child_request.approved():
                yield ToolOutput(
                    content="subagent result",
                    agent_id="sub-abcd",
                    corr_id="child-1",
                    parent_corr_id="task-1",
                )
            yield ToolOutput(content="parent task result", agent_id=MAIN_AGENT_ID, corr_id="task-1")

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        task_box = app.query(".subagent-task-box").last()
        nested_call_box = task_box.query(".tool-call-box").last()
        nested_output_box = task_box.query(".tool-output-box").last()
        conversation = app.query_one("#conversation")
        root_output_boxes = [box for box in app.query(".tool-output-box") if box.parent is conversation]

        assert task_box.title == r"\[main-agent] \[task-1] Tool Call: subagent_task"
        assert nested_call_box.title == r"\[sub-abcd] \[child-1] Tool Call: database_query"
        assert nested_output_box.title == r"\[sub-abcd] \[child-1] Tool Output"
        assert len(root_output_boxes) == 1
        assert root_output_boxes[0].title == r"\[main-agent] \[task-1] Tool Output"


@pytest.mark.asyncio
async def test_parallel_subagent_widgets_route_to_matching_task_box() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        task_a = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "Task A"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-a",
        )
        yield task_a
        assert await task_a.approved()

        task_b = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "Task B"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-b",
        )
        yield task_b
        assert await task_b.approved()

        child_a = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 'A'"}, ptc=False),
            agent_id="sub-a",
            corr_id="call-a",
            parent_corr_id="task-a",
        )
        yield child_a
        assert await child_a.approved()
        yield ToolOutput(content="A", agent_id="sub-a", corr_id="call-a", parent_corr_id="task-a")

        child_b = ApprovalRequest(
            tool_call=GenericCall(tool_name="database_query", tool_args={"query": "SELECT 'B'"}, ptc=False),
            agent_id="sub-b",
            corr_id="call-b",
            parent_corr_id="task-b",
        )
        yield child_b
        assert await child_b.approved()
        yield ToolOutput(content="B", agent_id="sub-b", corr_id="call-b", parent_corr_id="task-b")

        yield ToolOutput(content="Task A done", agent_id=MAIN_AGENT_ID, corr_id="task-a")
        yield ToolOutput(content="Task B done", agent_id=MAIN_AGENT_ID, corr_id="task-b")

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        task_boxes = {box.title: box for box in app.query(".subagent-task-box")}
        task_a_box = task_boxes[r"\[main-agent] \[task-a] Tool Call: subagent_task"]
        task_b_box = task_boxes[r"\[main-agent] \[task-b] Tool Call: subagent_task"]

        assert len(task_a_box.query(".tool-call-box")) == 1
        assert len(task_a_box.query(".tool-output-box")) == 1
        assert task_a_box.query(".tool-call-box").last().title == r"\[sub-a] \[call-a] Tool Call: database_query"
        assert task_a_box.query(".tool-output-box").last().title == r"\[sub-a] \[call-a] Tool Output"

        assert len(task_b_box.query(".tool-call-box")) == 1
        assert len(task_b_box.query(".tool-output-box")) == 1
        assert task_b_box.query(".tool-call-box").last().title == r"\[sub-b] \[call-b] Tool Call: database_query"
        assert task_b_box.query(".tool-output-box").last().title == r"\[sub-b] \[call-b] Tool Output"


@pytest.mark.asyncio
async def test_active_subagent_task_can_be_manually_collapsed() -> None:
    permission_manager = StubPermissionManager(preapproved=True)
    release_completion = asyncio.Event()

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        task_request = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "delegate"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-1",
        )
        yield task_request
        assert await task_request.approved()
        yield ToolOutput(content="still running", agent_id="sub-abcd", corr_id="child-1", parent_corr_id="task-1")
        await release_completion.wait()
        yield ToolOutput(content="done", agent_id=MAIN_AGENT_ID, corr_id="task-1")

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)

        task_box = app.query(".subagent-task-box").last()
        assert not task_box.collapsed

        task_box.collapsed = True
        await pilot.pause(0.05)
        assert task_box.collapsed

        await pilot.press("ctrl+o")
        assert not task_box.collapsed
        await pilot.press("ctrl+o")
        assert task_box.collapsed

        release_completion.set()
        await app.workers.wait_for_complete()
        assert task_box.collapsed


@pytest.mark.asyncio
async def test_completed_subagent_task_auto_collapse_is_configurable() -> None:
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        task_request = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "delegate"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-1",
        )
        yield task_request
        assert await task_request.approved()
        yield ToolOutput(content="subagent result", agent_id="sub-abcd", corr_id="child-1", parent_corr_id="task-1")
        yield ToolOutput(content="done", agent_id=MAIN_AGENT_ID, corr_id="task-1")

    collapsed_app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
    )

    async with collapsed_app.run_test() as pilot:
        await _submit_prompt(collapsed_app, pilot)
        await collapsed_app.workers.wait_for_complete()
        assert collapsed_app.query(".subagent-task-box").last().collapsed

    expanded_app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=permission_manager,  # type: ignore[arg-type]
        config=TerminalConfig(collapse_completed_subagent_tasks=False),
    )

    async with expanded_app.run_test() as pilot:
        await _submit_prompt(expanded_app, pilot)
        await expanded_app.workers.wait_for_complete()
        assert not expanded_app.query(".subagent-task-box").last().collapsed


@pytest.mark.asyncio
async def test_nested_subagent_approval_bar_stays_root_level_visible() -> None:
    class TaskOnlyPermissionManager(StubPermissionManager):
        def is_allowed(self, tool_call: ToolCall) -> bool:
            return isinstance(tool_call, GenericCall) and tool_call.tool_name == "subagent_task"

    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        task_request = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "delegate"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-1",
        )
        yield task_request
        assert await task_request.approved()

        child_request = ApprovalRequest(
            tool_call=CodeAction(tool_name="ipybox_execute_ipython_cell", code="print('hi')"),
            agent_id="sub-abcd",
            corr_id="child-1",
            parent_corr_id="task-1",
        )
        yield child_request
        await child_request.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=TaskOnlyPermissionManager(),  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)

        conversation = app.query_one("#conversation")
        bars = list(app.query("ApprovalBar"))
        assert len(bars) == 1
        assert bars[0].parent is conversation


@pytest.mark.asyncio
async def test_active_subagent_task_moves_to_bottom_on_nested_activity() -> None:
    async def scenario(_: PromptContent) -> AsyncIterator[AgentEvent]:
        task_a = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "Task A"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-a",
        )
        yield task_a
        assert await task_a.approved()

        task_b = ApprovalRequest(
            tool_call=GenericCall(tool_name="subagent_task", tool_args={"prompt": "Task B"}, ptc=False),
            agent_id=MAIN_AGENT_ID,
            corr_id="task-b",
        )
        yield task_b
        assert await task_b.approved()

        child_a = ApprovalRequest(
            tool_call=CodeAction(tool_name="ipybox_execute_ipython_cell", code="print('A')"),
            agent_id="sub-a",
            corr_id="child-a",
            parent_corr_id="task-a",
        )
        yield child_a
        await child_a.approved()

    app = _create_app(
        agent_stream=MockStreamAgent(scenario).stream,
        agent_id=MAIN_AGENT_ID,
        permission_manager=StubPermissionManager(preapproved=True),  # type: ignore[arg-type]
    )

    async with app.run_test() as pilot:
        await _submit_prompt(app, pilot)
        await pilot.pause(0.05)

        task_boxes = list(app.query(".subagent-task-box"))
        assert len(task_boxes) == 2
        assert task_boxes[-1].title == r"\[main-agent] \[task-a] Tool Call: subagent_task"
