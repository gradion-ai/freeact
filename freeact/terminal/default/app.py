import asyncio
import re
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from pydantic_ai import UserContent
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Collapsible, Markdown, Static

from freeact.agent.events import (
    AgentEvent,
    ApprovalRequest,
    CodeExecutionOutput,
    CodeExecutionOutputChunk,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.media import parse_prompt
from freeact.permissions import PermissionManager
from freeact.terminal.default.clipboard import ClipboardAdapter, ClipboardAdapterProtocol
from freeact.terminal.default.config import DEFAULT_TERMINAL_UI_CONFIG, TerminalUiConfig
from freeact.terminal.default.screens import FilePickerScreen
from freeact.terminal.default.tool_adapter import ToolAdapter
from freeact.terminal.default.tool_data import (
    ActionData,
    CodeActionData,
    FileEditData,
    FileReadData,
    FileWriteData,
    GenericToolCallData,
)
from freeact.terminal.default.widgets import (
    ApprovalBar,
    PromptInput,
    create_code_action_box,
    create_error_box,
    create_exec_output_box,
    create_file_edit_action_box,
    create_file_read_action_box,
    create_file_write_action_box,
    create_response_box,
    create_thoughts_box,
    create_tool_call_box,
    create_tool_output_box,
    create_user_input_box,
    finalize_exec_output,
)

AgentStreamFn: TypeAlias = Callable[[str | Sequence[UserContent]], AsyncIterator[AgentEvent]]
Location: TypeAlias = tuple[int, int]
_BANNER_PATH = Path(__file__).with_name("banner.txt")


@dataclass(frozen=True)
class AtReferenceContext:
    """Cursor range that covers the current `@path` token in the prompt."""

    start: Location
    end: Location


def _format_attachment_path(path: Path, cwd: Path | None = None) -> str:
    """Format a selected path for insertion after `@`.

    Args:
        path: Selected filesystem path.
        cwd: Base path used for relative formatting. Defaults to `Path.cwd()`.

    Returns:
        Relative path when `path` is under `cwd`; otherwise an absolute path.
    """
    resolved = path.expanduser().resolve()
    base = (cwd or Path.cwd()).resolve()
    try:
        relative = resolved.relative_to(base)
    except ValueError:
        return str(resolved)
    if str(relative) == ".":
        return "."
    return str(relative)


def _find_at_reference_context(text: str, cursor: Location) -> AtReferenceContext | None:
    """Locate the active `@path` token when cursor is immediately after `@`.

    Args:
        text: Prompt text content.
        cursor: Current cursor location as `(row, column)`.

    Returns:
        Token bounds for replacement, or `None` when no token is active.
    """
    row, col = cursor
    lines = text.split("\n")
    if row >= len(lines):
        return None
    line = lines[row]
    if col <= 0 or col > len(line):
        return None
    if line[col - 1] != "@":
        return None

    end_col = col
    while end_col < len(line) and not line[end_col].isspace():
        end_col += 1
    return AtReferenceContext(
        start=(row, col),
        end=(row, end_col),
    )


def _load_banner() -> Text | None:
    """Load startup banner text from the bundled ANSI art file.

    Returns:
        Parsed Rich `Text` banner, or `None` when the banner is unavailable.
    """
    try:
        banner_ansi = _BANNER_PATH.read_text().strip("\n")
    except OSError:
        return None
    if not banner_ansi:
        return None
    return Text.from_ansi(banner_ansi)


class FreeactApp(App[None]):
    """Main Textual application for the default freeact terminal UI."""

    DEFAULT_CSS = """
    #banner-top-spacer {
        height: 1;
    }
    #banner {
        padding: 0 1;
    }
    #banner-spacer {
        height: 1;
    }
    #conversation {
        height: 1fr;
        align-vertical: bottom;
        scrollbar-size: 1 1;
    }
    #input-dock {
        dock: bottom;
        height: auto;
        max-height: 14;
        padding: 0 1;
    }
    Collapsible.-collapsed {
        padding: 0 0 0 1;
        border-top: none;
    }
    Collapsible.-collapsed CollapsibleTitle {
        padding: 0 1;
        background: transparent;
    }
    .exec-output-box RichLog {
        height: auto;
        max-height: 50;
    }
    Markdown MarkdownBlock {
        link-style: underline;
        link-background: transparent;
        link-style-hover: bold underline;
        link-background-hover: transparent;
    }
    .error-box {
        border-top: solid $error;
    }
    .error-text {
        color: $error;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("super+c", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("ctrl+shift+c", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("ctrl+insert", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("enter", "approve_hotkey(1)", show=False, priority=True),
        Binding("ctrl+m", "approve_hotkey(1)", show=False, priority=True),
        Binding("y", "approve_hotkey(1)", show=False, priority=True),
        Binding("n", "approve_hotkey(0)", show=False, priority=True),
        Binding("a", "approve_hotkey(2)", show=False, priority=True),
        Binding("s", "approve_hotkey(3)", show=False, priority=True),
    ]

    def __init__(
        self,
        agent_stream: AgentStreamFn,
        permission_manager: PermissionManager | None = None,
        main_agent_id: str = "",
        ui_config: TerminalUiConfig = DEFAULT_TERMINAL_UI_CONFIG,
        clipboard_adapter: ClipboardAdapterProtocol | None = None,
    ) -> None:
        super().__init__()
        self._agent_stream = agent_stream
        self._permission_manager = permission_manager or PermissionManager()
        self._main_agent_id = main_agent_id
        self._ui_config = ui_config
        self._clipboard_adapter = clipboard_adapter or ClipboardAdapter()
        self._approval_future: asyncio.Future[int] | None = None
        self._tool_adapter = ToolAdapter()
        self._expand_all_override = False
        self._policy_collapsed: dict[int, bool] = {}
        self._forced_expanded_ids: set[int] = set()
        self._pending_approval_widget_id: int | None = None
        self._banner = _load_banner()
        self._bindings.bind(
            self._ui_config.keys.toggle_expand_all,
            "toggle_expand_all",
            show=False,
            priority=True,
        )

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="conversation"):
            if self._banner is not None:
                yield Static("", id="banner-top-spacer")
                yield Static(self._banner, id="banner")
                yield Static("", id="banner-spacer")
        with Vertical(id="input-dock"):
            yield PromptInput(id="prompt-input", clipboard_reader=self.read_clipboard_for_paste)

    def copy_to_clipboard(self, text: str) -> None:
        """Copy to OS clipboard and mirror into Textual's local clipboard cache."""
        self._clipboard_adapter.copy(text)
        self._clipboard = text

    def read_clipboard_for_paste(self) -> str:
        """Read from OS clipboard first, falling back to Textual local clipboard."""
        system_clipboard = self._clipboard_adapter.paste()
        if system_clipboard is not None:
            self._clipboard = system_clipboard
            return system_clipboard
        return self.clipboard

    def on_mount(self) -> None:
        self.query_one("#prompt-input", PromptInput).focus()
        self.call_after_refresh(self._scroll_conversation_to_bottom)

    def _scroll_conversation_to_bottom(self) -> None:
        """Position the conversation viewport at the latest content."""
        conversation = self.query_one("#conversation", VerticalScroll)
        conversation.scroll_end(animate=False)

    async def _mount_and_scroll(self, conversation: VerticalScroll, *widgets: "textual.widget.Widget") -> None:  # type: ignore[name-defined]  # noqa: F821
        """Mount widgets into the conversation and scroll to the bottom.

        Args:
            conversation: Conversation container that owns rendered widgets.
            *widgets: Widgets to mount in order.
        """
        for widget in widgets:
            await conversation.mount(widget)
        conversation.scroll_end(animate=False)

    def _register_box(self, box: Collapsible, policy_collapsed: bool, force_expanded: bool = False) -> None:
        box_id = id(box)
        self._policy_collapsed[box_id] = policy_collapsed
        if force_expanded:
            self._forced_expanded_ids.add(box_id)
        else:
            self._forced_expanded_ids.discard(box_id)
        self._apply_render_state(box)

    def _set_policy_collapsed(self, box: Collapsible, collapsed: bool) -> None:
        self._policy_collapsed[id(box)] = collapsed
        self._apply_render_state(box)

    def _set_force_expanded(self, box: Collapsible, enabled: bool) -> None:
        box_id = id(box)
        if enabled:
            self._forced_expanded_ids.add(box_id)
        else:
            self._forced_expanded_ids.discard(box_id)
        self._apply_render_state(box)

    def _apply_render_state(self, box: Collapsible) -> None:
        box_id = id(box)
        policy_collapsed = self._policy_collapsed.get(box_id, box.collapsed)
        if box_id in self._forced_expanded_ids or self._expand_all_override:
            box.collapsed = False
            return
        box.collapsed = policy_collapsed

    def _reapply_all_collapsible_states(self) -> None:
        for widget in self.query("Collapsible"):
            match widget:
                case Collapsible() as box:
                    self._apply_render_state(box)

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        raw_text = event.text
        content = parse_prompt(convert_at_references(raw_text))
        self._process_turn(raw_text, content)

    @work(exclusive=True)
    async def _process_turn(self, raw_text: str, content: str | Sequence[UserContent]) -> None:
        prompt_input = self.query_one("#prompt-input", PromptInput)
        conversation = self.query_one("#conversation", VerticalScroll)
        prompt_input.disabled = True
        conversation.anchor()

        user_box = create_user_input_box(raw_text)
        self._register_box(user_box, policy_collapsed=False)
        await self._mount_and_scroll(conversation, user_box)

        thoughts_stream: "Markdown.MarkdownStream | None" = None
        response_stream: "Markdown.MarkdownStream | None" = None
        exec_log = None
        tool_calls: dict[str, ActionData] = {}

        try:
            async for event in self._agent_stream(content):
                match event:
                    case ThoughtsChunk(agent_id=aid, content=chunk) if aid == self._main_agent_id:
                        if thoughts_stream is None:
                            box, md = create_thoughts_box(aid)
                            self._register_box(box, policy_collapsed=False)
                            await self._mount_and_scroll(conversation, box)
                            thoughts_stream = Markdown.get_stream(md)

                        await thoughts_stream.write(chunk)

                    case Thoughts(agent_id=aid) if aid == self._main_agent_id:
                        if thoughts_stream is not None:
                            await thoughts_stream.stop()
                            thoughts_stream = None
                            if self._ui_config.expand_collapse.collapse_thoughts_on_complete:
                                match conversation.query(".thoughts-box").last():
                                    case Collapsible() as last_box:
                                        self._set_policy_collapsed(last_box, collapsed=True)

                    case ResponseChunk(agent_id=aid, content=chunk) if aid == self._main_agent_id:
                        if response_stream is None:
                            box, md = create_response_box(aid)
                            self._register_box(box, policy_collapsed=False)
                            await self._mount_and_scroll(conversation, box)
                            response_stream = Markdown.get_stream(md)

                        await response_stream.write(chunk)

                    case Response(agent_id=aid) if aid == self._main_agent_id:
                        if response_stream is not None:
                            await response_stream.stop()
                            response_stream = None

                    case ApprovalRequest() as request:
                        request_action_data = self._tool_adapter.map_action(request.tool_name, request.tool_args)
                        if request.corr_id:
                            tool_calls[request.corr_id] = request_action_data
                        await self._handle_approval(request, request_action_data, conversation)

                    case CodeExecutionOutputChunk(agent_id=aid, text=text, corr_id=cid):
                        if exec_log is None:
                            box, exec_log = create_exec_output_box(aid, corr_id=cid)
                            self._register_box(box, policy_collapsed=False)
                            await self._mount_and_scroll(conversation, box)
                        exec_log.write(text)

                    case CodeExecutionOutput(agent_id=aid, text=text, images=images):
                        if exec_log is not None:
                            finalize_exec_output(exec_log, text, images)
                            if self._ui_config.expand_collapse.collapse_exec_output_on_complete:
                                match conversation.query(".exec-output-box").last():
                                    case Collapsible() as last_box:
                                        self._set_policy_collapsed(last_box, collapsed=True)
                        exec_log = None

                    case ToolOutput(agent_id=aid, content=tool_content, corr_id=cid):
                        output_action_data = tool_calls.get(cid) if cid else None
                        output_data = self._tool_adapter.map_output(output_action_data, tool_content)
                        box = create_tool_output_box(output_data, aid, corr_id=cid)
                        self._register_box(
                            box,
                            policy_collapsed=self._ui_config.expand_collapse.collapse_tool_outputs,
                        )
                        await self._mount_and_scroll(conversation, box)
        except Exception as e:
            error_box = create_error_box(f"{type(e).__name__}: {e}")
            self._register_box(error_box, policy_collapsed=False)
            await self._mount_and_scroll(conversation, error_box)
        finally:
            prompt_input.disabled = False
            prompt_input.focus()

    async def _handle_approval(
        self,
        request: ApprovalRequest,
        action_data: ActionData,
        conversation: VerticalScroll,
    ) -> None:
        match action_data:
            case CodeActionData(code=code):
                box = create_code_action_box(code, agent_id=request.agent_id, corr_id=request.corr_id)
            case FileEditData(path=path, edits=edits):
                box = create_file_edit_action_box(path, edits, agent_id=request.agent_id, corr_id=request.corr_id)
            case FileReadData(paths=paths, head=head, tail=tail):
                box = create_file_read_action_box(
                    paths,
                    head,
                    tail,
                    agent_id=request.agent_id,
                    corr_id=request.corr_id,
                )
            case FileWriteData(path=path, content=content):
                box = create_file_write_action_box(
                    path,
                    content,
                    agent_id=request.agent_id,
                    corr_id=request.corr_id,
                )
            case GenericToolCallData(tool_name=tool_name, tool_args=tool_args):
                box = create_tool_call_box(tool_name, tool_args, agent_id=request.agent_id, corr_id=request.corr_id)
            case _:
                raise ValueError(f"Unsupported action data: {action_data!r}")

        pin_pending = self._ui_config.expand_collapse.pin_pending_approval_action_expanded
        self._register_box(box, policy_collapsed=False, force_expanded=pin_pending)
        if pin_pending:
            self._pending_approval_widget_id = id(box)
        await self._mount_and_scroll(conversation, box)

        # Check if pre-approved
        if self._permission_manager.is_allowed(request.tool_name, request.tool_args):
            if self._pending_approval_widget_id == id(box):
                self._pending_approval_widget_id = None
                self._set_force_expanded(box, enabled=False)
            self._set_policy_collapsed(
                box,
                collapsed=self._collapse_for_approved_action(action_data),
            )
            request.approve(True)
            return

        # Prompt user for approval
        self._approval_future = asyncio.get_running_loop().create_future()
        bar = ApprovalBar()
        await self._mount_and_scroll(conversation, bar)
        bar.focus()

        decision = await self._approval_future
        self._approval_future = None

        await bar.remove()
        if self._pending_approval_widget_id == id(box):
            self._pending_approval_widget_id = None
            self._set_force_expanded(box, enabled=False)

        match decision:
            case 2:
                await self._permission_manager.allow_always(request.tool_name)
            case 3:
                self._permission_manager.allow_session(request.tool_name)

        approved = decision != 0
        if approved:
            self._set_policy_collapsed(
                box,
                collapsed=self._collapse_for_approved_action(action_data),
            )
        else:
            self._set_policy_collapsed(
                box,
                collapsed=not self._ui_config.expand_collapse.keep_rejected_actions_expanded,
            )
        request.approve(approved)

    def on_approval_bar_decided(self, event: ApprovalBar.Decided) -> None:
        self.action_approve_hotkey(event.decision)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "approve_hotkey":
            return self._has_pending_approval()
        return super().check_action(action, parameters)

    def action_approve_hotkey(self, decision: int) -> None:
        future = self._approval_future
        if future is not None and not future.done():
            future.set_result(decision)

    def action_toggle_expand_all(self) -> None:
        self._expand_all_override = not self._expand_all_override
        self._reapply_all_collapsible_states()

    def _has_pending_approval(self) -> bool:
        if self._approval_future is not None and not self._approval_future.done():
            return True
        return False

    def _collapse_for_approved_action(self, action_data: ActionData) -> bool:
        match action_data:
            case CodeActionData():
                return self._ui_config.expand_collapse.collapse_approved_code_actions
            case _:
                return self._ui_config.expand_collapse.collapse_approved_tool_calls

    # --- File picker integration ---

    def on_text_area_changed(self, event: "textual.widgets.TextArea.Changed") -> None:  # type: ignore[name-defined]  # noqa: F821
        if event.text_area.id != "prompt-input":
            return
        context = _find_at_reference_context(event.text_area.text, event.text_area.cursor_location)
        if context is not None:
            self._open_file_picker(context)

    def _open_file_picker(self, context: AtReferenceContext) -> None:
        async def handle_result(path: Path | None) -> None:
            if path is not None:
                prompt_input = self.query_one("#prompt-input", PromptInput)
                prompt_input.replace(
                    _format_attachment_path(path),
                    context.start,
                    context.end,
                )

        self.push_screen(
            FilePickerScreen(),
            callback=handle_result,
        )


def convert_at_references(text: str) -> str:
    """Convert `@path` tokens to `<attachment>...</attachment>` tags.

    Args:
        text: User prompt text that may contain `@path` tokens.

    Returns:
        Prompt text with `@path` tokens replaced by attachment tags.
    """
    return re.sub(r"@(\S+)", r"<attachment>\1</attachment>", text)
