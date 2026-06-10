# Covers behavior-inventory.md sections: 20 (terminal UI: input, rendering, copy/paste, approvals, collapse management, subagent display)
import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from rich.text import Text
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.geometry import Offset
from textual.keys import Keys
from textual.pilot import Pilot
from textual.widgets import Input, Static
from textual.widgets._collapsible import CollapsibleTitle

from freeact.config import TerminalSection
from freeact.events import (
    AgentEvent,
    Cancelled,
    CodeExecutionOutput,
    CodeExecutionOutputChunk,
    Phase,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.terminal.app import (
    SlashCommandContext,
    TerminalApp,
    _find_at_trigger,
    _find_slash_command_context,
    _format_picked_path,
    convert_slash_commands,
)
from freeact.terminal.screens import FilePickerScreen, FilePickerTree, SkillPickerScreen
from freeact.terminal.view import ConversationView, _format_display_cwd, _load_freeact_version
from freeact.terminal.widgets import PromptInput
from freeact.toolcalls import CodeAction, FileEdit, FileWrite, GenericCall, ShellAction, ToolCall
from tests.unit.terminal.conftest import (
    MAIN_AGENT_ID,
    MockStreamAgent,
    StubClipboardAdapter,
    StubPermissionManager,
    approval_request,
    approval_scenario,
    code_action_call,
    create_app,
    db_query_call,
    find_screen,
    make_skill,
    no_events,
    submit_prompt,
)


async def _response_scenario(_: str) -> AsyncIterator[AgentEvent]:
    text = "Hello world response text."
    yield ResponseChunk(content=text, agent_id=MAIN_AGENT_ID)
    yield Response(content=text, agent_id=MAIN_AGENT_ID)


def _subagent_task_call(prompt: str) -> GenericCall:
    return GenericCall(tool_name="subagent_task", tool_args={"prompt": prompt}, ptc=False)


def _patch_banner(monkeypatch: pytest.MonkeyPatch, banner: Text) -> None:
    monkeypatch.setattr("freeact.terminal.view._load_banner", lambda: banner)
    monkeypatch.setattr("freeact.terminal.view._load_freeact_version", lambda: "1.2.3")
    monkeypatch.setattr("freeact.terminal.view._format_display_cwd", lambda *args, **kwargs: "~/repo")


@pytest.mark.parametrize(
    ("text", "location", "expected"),
    [
        ("Attach @docs/readme.md now", (0, 8), (0, 7)),
        ("Attach @docs/readme.md now", (0, 0), None),
        ("Attach @docs/readme.md now", (0, 9), None),
        ("user@example.com", (0, 5), None),
        ("@screenshot.png describe this", (0, 1), (0, 0)),
    ],
)
def test_find_at_trigger(text: str, location: tuple[int, int], expected: tuple[int, int] | None) -> None:
    assert _find_at_trigger(text, location) == expected


def test_format_picked_path_prefers_relative_to_cwd(tmp_path: Path) -> None:
    nested = tmp_path / "assets" / "images"
    nested.mkdir(parents=True)

    assert _format_picked_path(nested, cwd=tmp_path) == "assets/images"


def test_format_display_cwd_prefers_tilde_relative_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cwd = home / "work" / "repo"
    cwd.mkdir(parents=True)

    assert _format_display_cwd(cwd=cwd, home=home) == "~/work/repo"


def test_load_freeact_version_omits_local_build_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("freeact.terminal.view.package_version", lambda _: "0.8.1.post1.dev0+6937613")

    assert _load_freeact_version() == "0.8.1.post1.dev0"


@pytest.mark.asyncio
async def test_banner_renders_inside_conversation_scroll_container(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_banner(monkeypatch, Text("banner"))
    app = create_app(MockStreamAgent(no_events).stream)

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
    _patch_banner(monkeypatch, Text("\n".join(["banner"] * 120)))
    app = create_app(MockStreamAgent(no_events).stream)

    async with app.run_test() as pilot:
        await pilot.pause(0.05)
        conversation = app.query_one("#conversation")
        assert conversation.max_scroll_y > 0
        assert conversation.scroll_y == conversation.max_scroll_y


@pytest.mark.asyncio
async def test_enter_submits_prompt_clears_input_and_mounts_user_box() -> None:
    agent = MockStreamAgent(no_events)
    app = create_app(agent.stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot, "  hello world  ")
        await app.workers.wait_for_complete()

        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == ""
        assert not prompt.disabled
        assert len(app.query(".user-input-box")) == 1

    assert agent.prompts == ["hello world"]


@pytest.mark.asyncio
async def test_empty_prompt_submission_warns_and_does_not_start_turn() -> None:
    agent = MockStreamAgent(no_events)
    app = create_app(agent.stream)

    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause(0.05)

        assert len(app._notifications) == 1
        assert len(app.query(".user-input-box")) == 0

    assert agent.prompts == []


@pytest.mark.asyncio
async def test_alt_enter_maps_to_ctrl_j_which_inserts_newline_without_submitting() -> None:
    assert ANSI_SEQUENCES_KEYS["\x1b\r"] == (Keys.ControlJ,)

    agent = MockStreamAgent(no_events)
    app = create_app(agent.stream)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        await pilot.press("h", "i")
        await pilot.press("ctrl+j")

        assert prompt.text == "hi\n"
        assert agent.prompts == []


@pytest.mark.asyncio
async def test_thoughts_stream_collapses_on_terminal_event() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        yield ThoughtsChunk(content="thinking...", agent_id=MAIN_AGENT_ID)
        yield Thoughts(content="thinking...", agent_id=MAIN_AGENT_ID)

    app = create_app(MockStreamAgent(scenario).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        assert app.query(".thoughts-box").last().collapsed


@pytest.mark.asyncio
async def test_response_stream_only_mounts_for_main_agent() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        yield ResponseChunk(content="ignore me", agent_id="other-agent")
        yield Response(content="ignore me", agent_id="other-agent")
        yield ResponseChunk(content="show me", agent_id=MAIN_AGENT_ID)
        yield Response(content="show me", agent_id=MAIN_AGENT_ID)

    app = create_app(MockStreamAgent(scenario).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        response_boxes = app.query(".response-box")
        assert len(response_boxes) == 1
        assert MAIN_AGENT_ID in response_boxes.last().title


@pytest.mark.asyncio
async def test_markdown_link_hover_style_is_configured_per_link() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        text = "See [Textual](https://textual.textualize.io/) and [Rich](https://github.com/Textualize/rich)."
        yield ResponseChunk(content=text, agent_id=MAIN_AGENT_ID)
        yield Response(content=text, agent_id=MAIN_AGENT_ID)

    app = create_app(MockStreamAgent(scenario).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        paragraph = app.query("MarkdownParagraph").last()
        assert str(paragraph.styles.link_style) == "underline"
        assert str(paragraph.styles.link_style_hover) == "bold underline"
        assert "Markdown MarkdownBlock:hover" not in ConversationView.DEFAULT_CSS
        assert "Markdown MarkdownBlock:hover" not in TerminalApp.DEFAULT_CSS


@pytest.mark.asyncio
@pytest.mark.parametrize("copy_key", ["super+c", "ctrl+shift+c", "ctrl+insert", "ctrl+c"])
async def test_copy_shortcuts_copy_selected_response_text(copy_key: str) -> None:
    clipboard_adapter = StubClipboardAdapter()
    app = create_app(MockStreamAgent(_response_scenario).stream, clipboard_adapter=clipboard_adapter)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        paragraph = app.query("MarkdownParagraph").last()
        paragraph.text_select_all()
        await pilot.press(copy_key)

        assert app.clipboard == "Hello world response text."
        assert clipboard_adapter.copy_calls == ["Hello world response text."]


@pytest.mark.asyncio
async def test_user_input_box_text_is_selectable_and_copyable() -> None:
    clipboard_adapter = StubClipboardAdapter()
    app = create_app(MockStreamAgent(no_events).stream, clipboard_adapter=clipboard_adapter)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot, "copy me from user input")
        await app.workers.wait_for_complete()

        user_input_text = app.query(".user-input-box Static").last()
        user_input_text.text_select_all()
        assert app.screen.get_selected_text() == "copy me from user input"

        await pilot.press("ctrl+c")
        assert app.clipboard == "copy me from user input"
        assert clipboard_adapter.copy_calls == ["copy me from user input"]


@pytest.mark.asyncio
async def test_mouse_drag_selects_text_in_all_widget_types() -> None:
    """E2E: mouse drag selection works on all widget types."""
    permission_manager = StubPermissionManager(preapproved=True)

    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        code_req = approval_request(
            CodeAction(tool_name="ipybox_execute_ipython_cell", code="print('hello')"), "code-1"
        )
        yield code_req
        if await code_req.approved():
            yield CodeExecutionOutputChunk(text="hello\n", agent_id=MAIN_AGENT_ID, corr_id="code-1")
            yield CodeExecutionOutput(
                text="hello\n",
                images=[],
                truncated=False,
                agent_id=MAIN_AGENT_ID,
                corr_id="code-1",
            )
            yield ToolOutput(content="hello\n", agent_id=MAIN_AGENT_ID, corr_id="code-1")
        tool_req = approval_request(GenericCall(tool_name="db_query", tool_args={"q": "SELECT 1"}, ptc=False), "call-1")
        yield tool_req
        if await tool_req.approved():
            yield ToolOutput(content="result data", agent_id=MAIN_AGENT_ID, corr_id="call-1")
        write_req = approval_request(FileWrite(tool_name="file_write", path="out.py", content="x = 1"), "write-1")
        yield write_req
        if await write_req.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="write-1")
        edit_req = approval_request(
            FileEdit(tool_name="file_edit", path="out.py", old_text="x = 1", new_text="x = 2"),
            "edit-1",
        )
        yield edit_req
        if await edit_req.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="edit-1")

    config = TerminalSection(
        collapse_approved_code_actions=False,
        collapse_exec_output_on_complete=False,
        collapse_approved_tool_calls=False,
        collapse_tool_outputs=False,
    )
    app = create_app(MockStreamAgent(scenario).stream, permission_manager=permission_manager, config=config)

    async with app.run_test(size=(80, 80)) as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()
        await pilot.pause()

        async def assert_drag(widget: Static, length: int, expected: str, label: str) -> None:
            await pilot.mouse_down(widget, offset=Offset(0, 0))
            await pilot.mouse_up(widget, offset=Offset(length, 0))
            text = app.screen.get_selected_text()
            assert text is not None and expected in text, f"{label}: {text!r}"
            app.screen.clear_selection()

        code_w = app.query(".code-action-box .tool-call-content > Static").first()
        assert isinstance(code_w, Static)
        await assert_drag(code_w, 14, "print", "code action")

        exec_w = app.query(".exec-output-box Static").last()
        assert isinstance(exec_w, Static)
        await assert_drag(exec_w, 5, "hello", "exec output")

        db_query_boxes = [b for b in app.query(".tool-call-box") if "db_query" in b.title]
        tool_w = db_query_boxes[0].query(".tool-output-box Contents > Static").first()
        assert isinstance(tool_w, Static)
        await assert_drag(tool_w, 11, "result data", "tool output")

        write_w = app.query(".write-file-box .tool-call-content > Static").first()
        assert isinstance(write_w, Static)
        await assert_drag(write_w, 5, "x = 1", "file write")

        edit_w = app.query(".diff-box .tool-call-content > Static").first()
        assert isinstance(edit_w, Static)
        await assert_drag(edit_w, 14, "--- a/out.py", "file edit")


@pytest.mark.asyncio
@pytest.mark.parametrize("paste_key", ["ctrl+v", "super+v", "ctrl+shift+v", "shift+insert"])
async def test_paste_shortcuts_use_os_clipboard_value(paste_key: str) -> None:
    clipboard_adapter = StubClipboardAdapter(paste_values=["from-os"])
    app = create_app(MockStreamAgent(no_events).stream, clipboard_adapter=clipboard_adapter)

    async with app.run_test() as pilot:
        await pilot.press(paste_key)
        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == "from-os"
        assert clipboard_adapter.paste_calls == 1
        assert app.clipboard == "from-os"


@pytest.mark.asyncio
async def test_prompt_paste_falls_back_to_local_clipboard_when_os_unavailable() -> None:
    clipboard_adapter = StubClipboardAdapter(paste_values=[None])
    app = create_app(MockStreamAgent(no_events).stream, clipboard_adapter=clipboard_adapter)
    app._clipboard = "local-fallback"

    async with app.run_test() as pilot:
        await pilot.press("ctrl+v")
        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == "local-fallback"


@pytest.mark.asyncio
async def test_prompt_paste_preserves_empty_os_clipboard_without_local_fallback() -> None:
    clipboard_adapter = StubClipboardAdapter(paste_values=[""])
    app = create_app(MockStreamAgent(no_events).stream, clipboard_adapter=clipboard_adapter)
    app._clipboard = "local-fallback"

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt.insert("start")
        await pilot.press("ctrl+v")
        assert prompt.text == "start"
        assert app.clipboard == ""


@pytest.mark.asyncio
async def test_ctrl_q_triggers_quit_action(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(MockStreamAgent(no_events).stream)
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
    app = create_app(MockStreamAgent(approval_scenario(db_query_call(), output="ok")).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        assert len(app.query("ApprovalBar")) == 1
        await pilot.press("y")
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 1
        assert app.query(".tool-output-box").last().title == r"\[main-agent] Tool Output"


@pytest.mark.asyncio
async def test_approval_enter_works_after_clicking_other_widget() -> None:
    app = create_app(MockStreamAgent(approval_scenario(db_query_call(), output="ok")).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.click(".user-input-box")
        await pilot.press("enter")
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 1


@pytest.mark.asyncio
async def test_approval_no_keeps_action_expanded_and_skips_tool_output() -> None:
    app = create_app(MockStreamAgent(approval_scenario(db_query_call(), output="ok")).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("n")
        await app.workers.wait_for_complete()

        assert not app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("key", "calls_attr"), [("a", "allow_always_calls"), ("s", "allow_session_calls")])
async def test_approval_always_and_session_record_suggested_pattern_and_approve(key: str, calls_attr: str) -> None:
    permission_manager = StubPermissionManager()
    app = create_app(MockStreamAgent(approval_scenario(db_query_call())).stream, permission_manager=permission_manager)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press(key)
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        assert len(app.query("ApprovalBar")) == 0

    calls: list[ToolCall] = getattr(permission_manager, calls_attr)
    assert len(calls) == 1
    assert isinstance(calls[0], GenericCall)
    assert calls[0].tool_name == "database_query"


@pytest.mark.asyncio
async def test_preapproved_request_skips_approval_bar() -> None:
    app = create_app(
        MockStreamAgent(approval_scenario(db_query_call(), output="ok")).stream,
        permission_manager=StubPermissionManager(preapproved=True),
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert app.query(".tool-call-box").last().collapsed
        assert len(app.query(".tool-output-box")) == 1


@pytest.mark.asyncio
async def test_skip_permissions_skips_approval_bar() -> None:
    app = create_app(
        MockStreamAgent(approval_scenario(db_query_call(), output="ok")).stream,
        permission_manager=StubPermissionManager(preapproved=False),
        skip_permissions=True,
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        assert len(app.query("ApprovalBar")) == 0
        assert len(app.query(".tool-output-box")) == 1


@pytest.mark.asyncio
async def test_ptc_request_uses_ptc_title_in_default_terminal() -> None:
    ptc_call = GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=True)
    app = create_app(
        MockStreamAgent(approval_scenario(ptc_call)).stream,
        permission_manager=StubPermissionManager(preapproved=True),
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        assert app.query(".tool-call-box").last().title == r"\[main-agent] PTC: database_query"


@pytest.mark.asyncio
async def test_ctrl_o_toggles_expand_all_and_restores_configured_state() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        yield ThoughtsChunk(content="thinking...", agent_id=MAIN_AGENT_ID)
        yield Thoughts(content="thinking...", agent_id=MAIN_AGENT_ID)
        request = approval_request(db_query_call(), "call-1")
        yield request
        if await request.approved():
            yield ToolOutput(content="ok", agent_id=MAIN_AGENT_ID, corr_id="call-1")

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=StubPermissionManager(preapproved=True))

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
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
    app = create_app(
        MockStreamAgent(approval_scenario(db_query_call(), output="ok")).stream,
        permission_manager=StubPermissionManager(preapproved=True),
    )

    async with app.run_test() as pilot:
        await pilot.press("ctrl+o")
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        output_box = app.query(".tool-output-box").last()
        assert not output_box.collapsed

        await pilot.press("ctrl+o")
        assert output_box.collapsed


@pytest.mark.asyncio
async def test_toggle_expand_all_uses_configured_hotkey() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        yield ThoughtsChunk(content="thinking...", agent_id=MAIN_AGENT_ID)
        yield Thoughts(content="thinking...", agent_id=MAIN_AGENT_ID)

    app = create_app(MockStreamAgent(scenario).stream, config=TerminalSection(expand_all_toggle_key="f6"))

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        thoughts_box = app.query(".thoughts-box").last()
        assert thoughts_box.collapsed

        await pilot.press("f6")
        assert not thoughts_box.collapsed

        await pilot.press("f6")
        assert thoughts_box.collapsed


@pytest.mark.asyncio
async def test_pending_approval_widget_stays_expanded_until_user_decides() -> None:
    app = create_app(MockStreamAgent(approval_scenario(db_query_call(), output="ok")).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
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
@pytest.mark.parametrize(
    ("preapproved", "key", "expected_collapsed"),
    [(False, "y", False), (True, None, False), (False, "n", True)],
)
async def test_approval_behaviors_can_disable_auto_collapse(
    preapproved: bool, key: str | None, expected_collapsed: bool
) -> None:
    ui_config = TerminalSection(collapse_approved_tool_calls=False, keep_rejected_actions_expanded=False)
    app = create_app(
        MockStreamAgent(approval_scenario(db_query_call())).stream,
        config=ui_config,
        permission_manager=StubPermissionManager(preapproved=preapproved),
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        if key is not None:
            await pilot.pause(0.05)
            await pilot.press(key)
        await app.workers.wait_for_complete()
        assert app.query(".tool-call-box").last().collapsed is expected_collapsed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_call", "box_selector", "expected_collapsed"),
    [
        (db_query_call(), ".tool-call-box", True),
        (code_action_call(), ".code-action-box", False),
    ],
)
async def test_approved_code_and_tool_collapse_behaviors_are_independent(
    tool_call: ToolCall, box_selector: str, expected_collapsed: bool
) -> None:
    ui_config = TerminalSection(collapse_approved_code_actions=False, collapse_approved_tool_calls=True)
    app = create_app(MockStreamAgent(approval_scenario(tool_call)).stream, config=ui_config)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await app.workers.wait_for_complete()
        assert app.query(box_selector).last().collapsed is expected_collapsed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_call", "box_selector", "ui_config"),
    [
        (code_action_call(), ".code-action-box", TerminalSection(collapse_approved_code_actions=False)),
        (db_query_call(), ".tool-call-box", TerminalSection(collapse_approved_tool_calls=False)),
    ],
)
async def test_preapproved_action_respects_collapse_config(
    tool_call: ToolCall, box_selector: str, ui_config: TerminalSection
) -> None:
    app = create_app(
        MockStreamAgent(approval_scenario(tool_call)).stream,
        permission_manager=StubPermissionManager(preapproved=True),
        config=ui_config,
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()
        assert not app.query(box_selector).last().collapsed


@pytest.mark.asyncio
async def test_stream_exception_renders_error_and_reenables_input() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        raise RuntimeError("boom")
        if False:
            yield Response(content="", agent_id=MAIN_AGENT_ID)

    app = create_app(MockStreamAgent(scenario).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        prompt = app.query_one("#prompt-input", PromptInput)
        assert not prompt.disabled
        assert len(app.query(".error-box")) == 1


async def _open_file_picker_tree(app: TerminalApp, pilot: Pilot[Any]) -> FilePickerTree:
    await pilot.press("@")
    await pilot.pause(0.1)
    picker = find_screen(app, FilePickerScreen)
    return picker.query_one("#picker-tree", FilePickerTree)


@pytest.mark.asyncio
async def test_typing_at_opens_file_picker_screen() -> None:
    app = create_app(MockStreamAgent(no_events).stream)

    async with app.run_test() as pilot:
        await pilot.press("@")
        await pilot.pause(0.05)

        assert any(isinstance(screen, FilePickerScreen) for screen in app.screen_stack)


@pytest.mark.asyncio
async def test_file_picker_starts_at_filesystem_root() -> None:
    app = create_app(MockStreamAgent(no_events).stream)

    async with app.run_test() as pilot:
        tree = await _open_file_picker_tree(app, pilot)
        cwd = Path.cwd().resolve()
        expected_root = Path(cwd.anchor) if cwd.anchor else cwd
        assert tree.path == expected_root


@pytest.mark.asyncio
async def test_file_picker_cursor_starts_at_cwd() -> None:
    app = create_app(MockStreamAgent(no_events).stream)

    async with app.run_test() as pilot:
        tree = await _open_file_picker_tree(app, pilot)
        cursor_node = tree.cursor_node
        assert cursor_node is not None
        assert cursor_node.data is not None
        assert cursor_node.data.path.resolve() == Path.cwd().resolve()


@pytest.mark.asyncio
async def test_file_picker_selection_replaces_at_with_path() -> None:
    app = create_app(MockStreamAgent(no_events).stream)

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt.insert("See @ value")
        app._open_file_picker((0, 4))
        await pilot.pause(0.05)

        picker = find_screen(app, FilePickerScreen)
        picker.dismiss(Path.cwd() / "new")
        await pilot.pause(0.05)

        assert prompt.text == "See new value"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/plan my project", '<skill name="plan">my project</skill>'),
        ("/plan", '<skill name="plan"></skill>'),
        ("/unknown foo", "/unknown foo"),
        ("text /plan foo", "text /plan foo"),
        ("/plan arg\nmore", '<skill name="plan">arg\nmore</skill>'),
    ],
)
def test_convert_slash_commands(text: str, expected: str) -> None:
    assert convert_slash_commands(text, [make_skill("plan")]) == expected


def test_convert_slash_commands_empty_skills_list() -> None:
    assert convert_slash_commands("/plan foo", []) == "/plan foo"


@pytest.mark.asyncio
async def test_slash_command_is_converted_to_skill_tag_before_agent_receives_prompt() -> None:
    agent = MockStreamAgent(no_events)
    app = create_app(agent.stream, skills_metadata=[make_skill("greet", description="Greeting skill")])

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot, "/greet world")
        await app.workers.wait_for_complete()

    assert agent.prompts == ['<skill name="greet">world</skill>']


@pytest.mark.parametrize(
    ("text", "location", "expected"),
    [
        ("/", (0, 1), SlashCommandContext(start=(0, 1), end=(0, 1))),
        ("text /", (0, 6), None),
        ("line0\n/", (1, 1), None),
        ("/plan", (0, 3), None),
    ],
)
def test_find_slash_command_context(text: str, location: tuple[int, int], expected: SlashCommandContext | None) -> None:
    assert _find_slash_command_context(text, location) == expected


@pytest.mark.asyncio
async def test_typing_slash_at_start_opens_skill_picker() -> None:
    app = create_app(MockStreamAgent(no_events).stream, skills_metadata=[make_skill("plan")])

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.pause(0.05)

        assert any(isinstance(screen, SkillPickerScreen) for screen in app.screen_stack)


@pytest.mark.asyncio
async def test_slash_in_middle_does_not_open_skill_picker() -> None:
    app = create_app(MockStreamAgent(no_events).stream, skills_metadata=[make_skill("plan")])

    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt-input", PromptInput)
        prompt.insert("text ")
        await pilot.press("/")
        await pilot.pause(0.05)

        assert not any(isinstance(screen, SkillPickerScreen) for screen in app.screen_stack)


@pytest.mark.asyncio
async def test_skill_picker_to_submission_e2e() -> None:
    """Full flow: type /, pick skill, type args, submit, verify agent receives skill tag."""
    agent = MockStreamAgent(no_events)
    app = create_app(agent.stream, skills_metadata=[make_skill("plan")])

    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.pause(0.05)

        picker = find_screen(app, SkillPickerScreen)
        picker.dismiss("plan")
        await pilot.pause(0.05)

        prompt = app.query_one("#prompt-input", PromptInput)
        assert prompt.text == "/plan "

        prompt.insert("my project")
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert agent.prompts == ['<skill name="plan">my project</skill>']


@pytest.mark.asyncio
async def test_escape_during_turn_cancels() -> None:
    cancel_calls = 0

    def fake_cancel() -> None:
        nonlocal cancel_calls
        cancel_calls += 1

    async def slow_scenario(_: str) -> AsyncIterator[AgentEvent]:
        yield ResponseChunk(content="streaming...", agent_id=MAIN_AGENT_ID)
        await asyncio.sleep(5)
        yield Response(content="streaming...", agent_id=MAIN_AGENT_ID)

    app = create_app(MockStreamAgent(slow_scenario).stream, cancel_fn=fake_cancel)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
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

    app = create_app(MockStreamAgent(no_events).stream, cancel_fn=fake_cancel)

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

    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        request = approval_request(db_query_call(), "call-1")
        yield request
        if not await request.approved():
            yield Cancelled(agent_id=MAIN_AGENT_ID, phase=Phase.TOOL_EXECUTION)

    app = create_app(MockStreamAgent(scenario).stream, cancel_fn=fake_cancel)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        assert len(app.query("ApprovalBar")) == 1

        await pilot.press("escape")
        await app.workers.wait_for_complete()

        assert cancel_calls == 1
        assert len(app.query("ApprovalBar")) == 0
        prompt = app.query_one("#prompt-input", PromptInput)
        assert not prompt.disabled


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "expected_pattern"),
    [("git status", "git status *"), ("git add /path/to/file.py", "git add *")],
)
async def test_shell_approval_always_routes_suggested_pattern_to_shell_domain(
    command: str, expected_pattern: str
) -> None:
    permission_manager = StubPermissionManager()
    shell_call = ShellAction(tool_name="bash", command=command)
    app = create_app(MockStreamAgent(approval_scenario(shell_call)).stream, permission_manager=permission_manager)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)
        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert len(permission_manager.allow_always_calls) == 1
    assert isinstance(permission_manager.allow_always_calls[0], ShellAction)
    assert permission_manager.allow_always_calls[0].command == expected_pattern


@pytest.mark.asyncio
async def test_shell_approval_bar_displays_verbatim_command_for_bash() -> None:
    shell_call = ShellAction(tool_name="bash", command="git status")
    app = create_app(
        MockStreamAgent(approval_scenario(shell_call)).stream,
        permission_manager=StubPermissionManager(),
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)

        bars = list(app.query("ApprovalBar"))
        assert len(bars) == 1
        text = str(bars[0].content)
        assert "git status" in text
        assert "git status *" not in text

        await pilot.press("n")
        await app.workers.wait_for_complete()


@pytest.mark.asyncio
async def test_shell_approval_bar_summarizes_shell_magic_script() -> None:
    script = "echo first\necho second\necho third"
    shell_call = ShellAction(tool_name="shell_magic", command=script)
    app = create_app(
        MockStreamAgent(approval_scenario(shell_call)).stream,
        permission_manager=StubPermissionManager(),
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)

        bars = list(app.query("ApprovalBar"))
        text = str(bars[0].content)
        assert "echo first" in text
        assert "+2 more" in text
        assert "\\n" not in text
        assert "echo first\\necho second" not in text

        await pilot.press("n")
        await app.workers.wait_for_complete()


@pytest.mark.asyncio
async def test_shell_approval_a_seeds_input_with_suggested_pattern() -> None:
    permission_manager = StubPermissionManager()
    shell_call = ShellAction(tool_name="bash", command="git status")
    app = create_app(MockStreamAgent(approval_scenario(shell_call)).stream, permission_manager=permission_manager)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.05)

        input_widget = app.query_one("#approval-pattern-input", Input)
        assert input_widget.value == "git status *"

        await pilot.press("enter")
        await app.workers.wait_for_complete()

    assert len(permission_manager.allow_always_calls) == 1
    assert isinstance(permission_manager.allow_always_calls[0], ShellAction)
    assert permission_manager.allow_always_calls[0].command == "git status *"


@pytest.mark.asyncio
async def test_subagent_widgets_mount_inside_subagent_task_box_and_parent_output_stays_root() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        task_request = approval_request(_subagent_task_call("delegate"), "task-1")
        yield task_request
        if await task_request.approved():
            child_request = approval_request(db_query_call(), "child-1", agent_id="sub-abcd", parent_corr_id="task-1")
            yield child_request
            if await child_request.approved():
                yield ToolOutput(
                    content="subagent result",
                    agent_id="sub-abcd",
                    corr_id="child-1",
                    parent_corr_id="task-1",
                )
            yield ToolOutput(content="parent task result", agent_id=MAIN_AGENT_ID, corr_id="task-1")

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=StubPermissionManager(preapproved=True))

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        task_box = app.query(".subagent-task-box").last()
        nested_call_boxes = task_box.query(".tool-call-box")
        nested_output_boxes = task_box.query(".tool-output-box")
        conversation = app.query_one("#conversation")
        root_output_boxes = [box for box in app.query(".tool-output-box") if box.parent is conversation]

        assert task_box.title == r"\[main-agent] Tool Call: subagent_task"
        assert len(nested_call_boxes) == 1
        assert nested_call_boxes.last().title == r"\[sub-abcd] Tool Call: database_query"
        assert len(nested_output_boxes) == 2
        assert len(root_output_boxes) == 0


@pytest.mark.asyncio
async def test_parallel_subagent_widgets_route_to_matching_task_box() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        task_a = approval_request(_subagent_task_call("Task A"), "task-a")
        yield task_a
        assert await task_a.approved()

        task_b = approval_request(_subagent_task_call("Task B"), "task-b")
        yield task_b
        assert await task_b.approved()

        child_a = approval_request(
            GenericCall(tool_name="database_query", tool_args={"query": "SELECT 'A'"}, ptc=False),
            "call-a",
            agent_id="sub-a",
            parent_corr_id="task-a",
        )
        yield child_a
        assert await child_a.approved()
        yield ToolOutput(content="A", agent_id="sub-a", corr_id="call-a", parent_corr_id="task-a")

        child_b = approval_request(
            GenericCall(tool_name="database_query", tool_args={"query": "SELECT 'B'"}, ptc=False),
            "call-b",
            agent_id="sub-b",
            parent_corr_id="task-b",
        )
        yield child_b
        assert await child_b.approved()
        yield ToolOutput(content="B", agent_id="sub-b", corr_id="call-b", parent_corr_id="task-b")

        yield ToolOutput(content="Task A done", agent_id=MAIN_AGENT_ID, corr_id="task-a")
        yield ToolOutput(content="Task B done", agent_id=MAIN_AGENT_ID, corr_id="task-b")

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=StubPermissionManager(preapproved=True))

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        task_boxes = list(app.query(".subagent-task-box"))
        assert len(task_boxes) == 2
        task_a_box, task_b_box = task_boxes

        assert len(task_a_box.query(".tool-call-box")) == 1
        assert len(task_a_box.query(".tool-output-box")) == 2
        assert task_a_box.query(".tool-call-box").last().title == r"\[sub-a] Tool Call: database_query"

        assert len(task_b_box.query(".tool-call-box")) == 1
        assert len(task_b_box.query(".tool-output-box")) == 2
        assert task_b_box.query(".tool-call-box").last().title == r"\[sub-b] Tool Call: database_query"


@pytest.mark.asyncio
async def test_user_toggle_collapses_and_expands_box() -> None:
    app = create_app(MockStreamAgent(_response_scenario).stream)

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        response_box = app.query(".response-box").last()
        assert not response_box.collapsed

        response_box.query_one(CollapsibleTitle).focus()
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert response_box.collapsed

        await pilot.press("enter")
        await pilot.pause(0.05)
        assert not response_box.collapsed


@pytest.mark.asyncio
async def test_active_subagent_task_can_be_manually_collapsed() -> None:
    release_completion = asyncio.Event()

    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        task_request = approval_request(_subagent_task_call("delegate"), "task-1")
        yield task_request
        assert await task_request.approved()
        yield ToolOutput(content="still running", agent_id="sub-abcd", corr_id="child-1", parent_corr_id="task-1")
        await release_completion.wait()
        yield ToolOutput(content="done", agent_id=MAIN_AGENT_ID, corr_id="task-1")

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=StubPermissionManager(preapproved=True))

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)

        task_box = app.query(".subagent-task-box").last()
        assert not task_box.collapsed

        # Collapse via the title (a user toggle, not a programmatic change).
        task_box.query(CollapsibleTitle).first().focus()
        await pilot.press("enter")
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
@pytest.mark.parametrize(
    ("ui_config", "expected_collapsed"),
    [(None, True), (TerminalSection(collapse_completed_subagent_tasks=False), False)],
)
async def test_completed_subagent_task_auto_collapse_is_configurable(
    ui_config: TerminalSection | None, expected_collapsed: bool
) -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        task_request = approval_request(_subagent_task_call("delegate"), "task-1")
        yield task_request
        assert await task_request.approved()
        yield ToolOutput(content="subagent result", agent_id="sub-abcd", corr_id="child-1", parent_corr_id="task-1")
        yield ToolOutput(content="done", agent_id=MAIN_AGENT_ID, corr_id="task-1")

    app = create_app(
        MockStreamAgent(scenario).stream,
        permission_manager=StubPermissionManager(preapproved=True),
        config=ui_config,
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()
        assert app.query(".subagent-task-box").last().collapsed is expected_collapsed


@pytest.mark.asyncio
async def test_nested_subagent_approval_bar_stays_root_level_visible() -> None:
    class TaskOnlyPermissionManager(StubPermissionManager):
        def is_allowed(self, tool_call: ToolCall) -> bool:
            return isinstance(tool_call, GenericCall) and tool_call.tool_name == "subagent_task"

    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        task_request = approval_request(_subagent_task_call("delegate"), "task-1")
        yield task_request
        assert await task_request.approved()

        child_request = approval_request(
            code_action_call("print('hi')"),
            "child-1",
            agent_id="sub-abcd",
            parent_corr_id="task-1",
        )
        yield child_request
        await child_request.approved()

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=TaskOnlyPermissionManager())

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)

        conversation = app.query_one("#conversation")
        bars = list(app.query("ApprovalBar"))
        assert len(bars) == 1
        assert bars[0].parent is conversation


@pytest.mark.asyncio
async def test_subagent_task_order_stays_stable_during_nested_activity() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        task_a = approval_request(_subagent_task_call("Task A"), "task-a")
        yield task_a
        assert await task_a.approved()

        task_b = approval_request(_subagent_task_call("Task B"), "task-b")
        yield task_b
        assert await task_b.approved()

        child_a = approval_request(code_action_call("print('A')"), "child-a", agent_id="sub-a", parent_corr_id="task-a")
        yield child_a
        await child_a.approved()

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=StubPermissionManager(preapproved=True))

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)

        task_boxes = list(app.query(".subagent-task-box"))
        assert len(task_boxes) == 2
        assert task_boxes[0].title == r"\[main-agent] Tool Call: subagent_task"
        assert task_boxes[1].title == r"\[main-agent] Tool Call: subagent_task"


@pytest.mark.asyncio
async def test_code_action_exec_output_nests_inside_code_action_box() -> None:
    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        request = approval_request(code_action_call("print('hello')"), "code-1")
        yield request
        if await request.approved():
            yield CodeExecutionOutput(text="hello\n", images=[], agent_id=MAIN_AGENT_ID, corr_id="code-1")
            yield ToolOutput(content="hello\n", agent_id=MAIN_AGENT_ID, corr_id="code-1")

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=StubPermissionManager(preapproved=True))

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        code_box = app.query(".code-action-box").last()
        nested_exec_boxes = code_box.query(".exec-output-box")
        nested_output_boxes = code_box.query(".tool-output-box")
        conversation = app.query_one("#conversation")
        root_exec_boxes = [b for b in app.query(".exec-output-box") if b.parent is conversation]

        assert len(nested_exec_boxes) == 1
        assert len(nested_output_boxes) == 1
        assert len(root_exec_boxes) == 0


@pytest.mark.asyncio
async def test_shell_sub_approval_nests_inside_code_action_box() -> None:
    class CodeOnlyPermissionManager(StubPermissionManager):
        def is_allowed(self, tool_call: ToolCall) -> bool:
            return isinstance(tool_call, CodeAction)

    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        code_request = approval_request(code_action_call("run_shell('ls')"), "code-1")
        yield code_request
        assert await code_request.approved()

        shell_request = approval_request(ShellAction(tool_name="ipybox_execute_ipython_cell", command="ls"), "code-1")
        yield shell_request
        await shell_request.approved()

    app = create_app(MockStreamAgent(scenario).stream, permission_manager=CodeOnlyPermissionManager())

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await pilot.pause(0.05)
        await pilot.press("y")
        await app.workers.wait_for_complete()

        code_box = app.query(".code-action-box").last()
        assert len(code_box.query(".tool-call-box")) == 1


@pytest.mark.asyncio
async def test_mcp_tool_output_nests_inside_tool_call_box() -> None:
    mcp_call = GenericCall(tool_name="mcp_read_file", tool_args={"path": "/tmp/test.txt"}, ptc=False)
    app = create_app(
        MockStreamAgent(approval_scenario(mcp_call, output="file contents", corr_id="mcp-1")).stream,
        permission_manager=StubPermissionManager(preapproved=True),
    )

    async with app.run_test() as pilot:
        await submit_prompt(app, pilot)
        await app.workers.wait_for_complete()

        tool_call_box = app.query(".tool-call-box").last()
        nested_output_boxes = tool_call_box.query(".tool-output-box")
        conversation = app.query_one("#conversation")
        root_output_boxes = [b for b in app.query(".tool-output-box") if b.parent is conversation]

        assert len(nested_output_boxes) == 1
        assert len(root_output_boxes) == 0
