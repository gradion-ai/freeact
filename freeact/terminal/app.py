import asyncio
import re
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import TypeAlias

from ipybox.utils import arun
from pydantic_ai import UserContent
from rich.console import Console
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Collapsible, Markdown, RichLog, Static

from freeact.agent import Agent
from freeact.agent.call import (
    CodeAction,
    FileEdit,
    FileRead,
    FileWrite,
    GenericCall,
    ShellAction,
    ToolCall,
    extract_tool_output_text,
    parse_pattern,
    suggest_pattern,
)
from freeact.agent.config.skills import SkillMetadata
from freeact.agent.events import (
    AgentEvent,
    ApprovalRequest,
    Cancelled,
    CodeExecutionOutput,
    CodeExecutionOutputChunk,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.permissions import PermissionManager
from freeact.preproc import preprocess_prompt
from freeact.terminal.clipboard import ClipboardAdapter, ClipboardAdapterProtocol
from freeact.terminal.config import Config
from freeact.terminal.screens import FilePickerScreen, SkillPickerScreen
from freeact.terminal.widgets import (
    ApprovalBar,
    PromptInput,
    create_code_action_box,
    create_error_box,
    create_exec_output_box,
    create_file_edit_action_box,
    create_file_read_action_box,
    create_file_write_action_box,
    create_response_box,
    create_subagent_task_box,
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


@dataclass(frozen=True)
class SlashCommandContext:
    """Cursor range that covers the `/command` token in the prompt."""

    start: Location
    end: Location


@dataclass(frozen=True)
class SubagentTaskBoxState:
    """Mounted container state for a root-level `subagent_task` widget."""

    box: Collapsible
    trace_container: Vertical


ExecLogKey: TypeAlias = tuple[str, str, str]


@dataclass
class ExecOutputState:
    """Mounted execution output state for a single execution stream."""

    box: Collapsible
    log: RichLog


@dataclass
class TurnRenderState:
    """Mutable render state for one in-flight conversation turn."""

    thoughts_stream: "Markdown.MarkdownStream | None" = None
    response_stream: "Markdown.MarkdownStream | None" = None
    exec_logs: dict[ExecLogKey, ExecOutputState] = field(default_factory=dict)


@dataclass
class CollapseState:
    """Collapse policy state shared across tracked `Collapsible` widgets."""

    schedule_scroll: Callable[[], None]
    expand_all_override: bool = False
    configured_collapsed: dict[int, bool] = field(default_factory=dict)
    manual_collapsed: dict[int, bool] = field(default_factory=dict)
    forced_expanded_ids: set[int] = field(default_factory=set)
    suppressed_toggle_events: dict[int, int] = field(default_factory=dict)

    def register(self, box: Collapsible, configured_collapsed: bool, force_expanded: bool = False) -> None:
        """Start tracking a widget and apply its initial render state."""
        box_id = id(box)
        self.configured_collapsed[box_id] = configured_collapsed
        self.suppressed_toggle_events[box_id] = self.suppressed_toggle_events.get(box_id, 0) + 1
        if force_expanded:
            self.forced_expanded_ids.add(box_id)
        else:
            self.forced_expanded_ids.discard(box_id)
        self.apply(box)

    def set_configured(self, box: Collapsible, collapsed: bool) -> None:
        """Update the configured collapsed state for a tracked widget."""
        self.configured_collapsed[id(box)] = collapsed
        self.apply(box)

    def set_forced(self, box: Collapsible, enabled: bool) -> None:
        """Enable or disable forced expansion for a tracked widget."""
        box_id = id(box)
        if enabled:
            self.forced_expanded_ids.add(box_id)
        else:
            self.forced_expanded_ids.discard(box_id)
        self.apply(box)

    def apply(self, box: Collapsible) -> None:
        """Resolve and apply the current collapsed state for a widget."""
        box_id = id(box)
        configured_collapsed = self.configured_collapsed.get(box_id, box.collapsed)
        manual_collapsed = self.manual_collapsed.get(box_id)
        if self.expand_all_override:
            collapsed = False
        elif manual_collapsed is not None:
            collapsed = manual_collapsed
        elif box_id in self.forced_expanded_ids:
            collapsed = False
        else:
            collapsed = configured_collapsed

        if box.collapsed == collapsed:
            return

        self.suppressed_toggle_events[box_id] = self.suppressed_toggle_events.get(box_id, 0) + 1
        box.collapsed = collapsed
        self.schedule_scroll()

    def toggle_expand_all(self, widgets: list[object]) -> None:
        """Flip the global expand-all override and reapply all tracked widgets."""
        self.expand_all_override = not self.expand_all_override
        for widget in widgets:
            match widget:
                case Collapsible() as box:
                    self.apply(box)

    def consume_suppressed_toggle(self, box: Collapsible) -> bool:
        """Return `True` when a toggle event was caused by programmatic state."""
        box_id = id(box)
        remaining = self.suppressed_toggle_events.get(box_id, 0)
        if remaining <= 0:
            return False
        if remaining == 1:
            del self.suppressed_toggle_events[box_id]
        else:
            self.suppressed_toggle_events[box_id] = remaining - 1
        return True

    def record_manual_toggle(self, box: Collapsible, collapsed: bool) -> None:
        """Persist a user-driven collapsed state for a tracked widget."""
        box_id = id(box)
        if box_id in self.configured_collapsed:
            self.manual_collapsed[box_id] = collapsed


def _find_slash_command_context(text: str, cursor: Location) -> SlashCommandContext | None:
    """Detect a `/` at (0, 0) with cursor at (0, 1).

    Args:
        text: Prompt text content.
        cursor: Current cursor location as `(row, column)`.

    Returns:
        Token bounds for skill picker, or `None` when not applicable.
    """
    row, col = cursor
    if row != 0 or col != 1:
        return None
    lines = text.split("\n")
    if not lines or not lines[0].startswith("/"):
        return None
    line = lines[0]
    end_col = 1
    while end_col < len(line) and not line[end_col].isspace():
        end_col += 1
    return SlashCommandContext(start=(0, 1), end=(0, end_col))


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


def _load_freeact_version() -> str:
    """Resolve the installed freeact package version via metadata.

    Local build metadata (the `+...` suffix) is omitted for display because it
    can reflect an editable-install build identifier rather than the currently
    checked-out source state.
    """
    try:
        version = package_version("freeact")
    except PackageNotFoundError:
        return "unknown"
    return version.split("+", 1)[0]


def _format_display_cwd(cwd: Path | None = None, home: Path | None = None) -> str:
    """Format cwd for UI display, preferring `~/` when under home directory."""
    resolved_cwd = (cwd or Path.cwd()).expanduser().resolve()
    resolved_home = (home or Path.home()).expanduser().resolve()
    try:
        relative = resolved_cwd.relative_to(resolved_home)
    except ValueError:
        return str(resolved_cwd)
    relative_text = relative.as_posix()
    if not relative_text:
        return "~/"
    return f"~/{relative_text}"


class TerminalInterface:
    """Textual terminal interface for interactive agent conversations."""

    def __init__(
        self,
        agent: Agent,
        console: Console | None = None,
        config: Config | None = None,
        skip_permissions: bool = False,
    ) -> None:
        """Initialize a terminal session wrapper around an agent.

        Args:
            agent: Agent instance used to execute conversation turns.
            console: Compatibility parameter for legacy interfaces. Textual
                manages rendering directly, so this value is ignored.
            config: Terminal UI configuration.
            skip_permissions: Run tools without prompting for approval.
        """
        self._agent = agent
        self._config = config or Config()
        self._skip_permissions = skip_permissions
        self._permission_manager = PermissionManager(
            agent.config.working_dir,
            agent.config.freeact_dir,
        )
        _ = console

    async def run(self) -> None:
        """Run the interactive terminal UI until the user exits."""
        await arun(self._permission_manager.init)

        async with self._agent:
            app = TerminalApp(
                config=self._config,
                agent_id=self._agent.agent_id,
                agent_stream=self._agent.stream,
                cancel_fn=self._agent.cancel,
                permission_manager=self._permission_manager,
                skills_metadata=self._agent.config.skills_metadata,
                skip_permissions=self._skip_permissions,
            )
            await app.run_async()


class TerminalApp(App[None]):
    """Main Textual application for the freeact terminal UI."""

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
    #banner-metadata {
        padding: 0 1;
        color: $text-muted;
    }
    #banner-divider {
        height: 1;
        border-top: solid $panel-lighten-1;
        margin: 0 1;
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
    #input-hints {
        color: $text-muted;
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
    .subagent-task-content {
        height: auto;
    }
    .subagent-trace-container {
        height: auto;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=False, priority=True),
        Binding("ctrl+c", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("super+c", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("ctrl+shift+c", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("ctrl+insert", "screen.copy_text", "Copy", show=False, priority=True),
        Binding("escape", "cancel_turn", "Cancel", show=False, priority=True),
        Binding("enter", "approve_hotkey(1)", show=False, priority=True),
        Binding("ctrl+m", "approve_hotkey(1)", show=False, priority=True),
        Binding("y", "approve_hotkey(1)", show=False, priority=True),
        Binding("n", "approve_hotkey(0)", show=False, priority=True),
        Binding("a", "approval_rule_hotkey(2)", show=False, priority=True),
        Binding("s", "approval_rule_hotkey(3)", show=False, priority=True),
    ]

    def __init__(
        self,
        config: Config,
        agent_id: str,
        agent_stream: AgentStreamFn,
        cancel_fn: Callable[[], None] | None = None,
        permission_manager: PermissionManager | None = None,
        clipboard_adapter: ClipboardAdapterProtocol | None = None,
        skills_metadata: list[SkillMetadata] | None = None,
        skip_permissions: bool = False,
    ) -> None:
        super().__init__()
        self._config = config
        self._agent_id = agent_id
        self._agent_stream = agent_stream
        self._cancel_fn = cancel_fn
        self._skip_permissions = skip_permissions
        self._permission_manager = permission_manager or PermissionManager()
        self._clipboard_adapter = clipboard_adapter or ClipboardAdapter()
        self._skills_metadata = skills_metadata or []
        self._approval_future: asyncio.Future[tuple[int, str]] | None = None
        self._turn_in_progress = False
        self._collapse_state = CollapseState(schedule_scroll=self._schedule_scroll_conversation_to_bottom)
        self._pending_approval_widget_id: int | None = None
        self._subagent_task_boxes: dict[str, SubagentTaskBoxState] = {}
        self._banner = _load_banner()
        self._version = _load_freeact_version()
        self._cwd = _format_display_cwd()
        self._bindings.bind(
            self._config.expand_all_toggle_key,
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
            yield Static(f"Version: {self._version}\n{self._cwd}", id="banner-metadata")
            yield Static("", id="banner-divider")
        with Vertical(id="input-dock"):
            yield PromptInput(id="prompt-input", clipboard_reader=self.read_clipboard_for_paste)
            yield Static("ctrl+q: quit", id="input-hints")

    def _update_input_hints(self) -> None:
        results = self.query("#input-hints")
        if not results:
            return
        hints = results.first(Static)
        if self._turn_in_progress:
            hints.update("ctrl+q: quit  esc: interrupt")
        else:
            hints.update("ctrl+q: quit")

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

    def _schedule_scroll_conversation_to_bottom(self) -> None:
        """Re-apply bottom alignment after the next layout refresh."""
        self.call_after_refresh(self._scroll_conversation_to_bottom)

    async def _mount_and_scroll(
        self,
        target: Vertical | VerticalScroll,
        conversation: VerticalScroll,
        *widgets: "textual.widget.Widget",  # type: ignore[name-defined]  # noqa: F821
    ) -> None:
        """Mount widgets into a target container and scroll to the bottom.

        Args:
            target: Container that owns the widgets.
            conversation: Root conversation container used for scrolling.
            *widgets: Widgets to mount in order.
        """
        for widget in widgets:
            await target.mount(widget)
        conversation.scroll_end(animate=False)
        self._schedule_scroll_conversation_to_bottom()

    def on_collapsible_expanded(self, event: Collapsible.Expanded) -> None:
        if self._collapse_state.consume_suppressed_toggle(event.collapsible):
            return
        self._collapse_state.record_manual_toggle(event.collapsible, collapsed=False)

    def on_collapsible_collapsed(self, event: Collapsible.Collapsed) -> None:
        if self._collapse_state.consume_suppressed_toggle(event.collapsible):
            return
        self._collapse_state.record_manual_toggle(event.collapsible, collapsed=True)

    def _event_target(self, event: AgentEvent, conversation: VerticalScroll) -> Vertical | VerticalScroll:
        if event.parent_corr_id:
            state = self._subagent_task_boxes.get(event.parent_corr_id)
            if state is not None:
                return state.trace_container
        return conversation

    def _mark_subagent_task_active(self, corr_id: str) -> None:
        state = self._subagent_task_boxes.get(corr_id)
        if state is None:
            return
        self._collapse_state.set_forced(state.box, enabled=True)

    def _mark_subagent_task_completed(self, corr_id: str) -> None:
        state = self._subagent_task_boxes.get(corr_id)
        if state is None:
            return
        self._collapse_state.set_forced(state.box, enabled=False)
        self._collapse_state.set_configured(
            state.box,
            collapsed=self._config.collapse_completed_subagent_tasks,
        )

    def _clear_turn_subagent_task_state(self) -> None:
        for state in self._subagent_task_boxes.values():
            self._collapse_state.set_forced(state.box, enabled=False)
        self._subagent_task_boxes.clear()

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        raw_text = event.text
        text = convert_at_references(raw_text)
        text = convert_slash_commands(text, self._skills_metadata)
        content = preprocess_prompt(text)
        self._process_turn(raw_text, content)

    @work(exclusive=True)
    async def _process_turn(self, raw_text: str, content: str | Sequence[UserContent]) -> None:
        prompt_input = self.query_one("#prompt-input", PromptInput)
        conversation = self.query_one("#conversation", VerticalScroll)
        prompt_input.disabled = True
        conversation.anchor()

        user_box = create_user_input_box(raw_text)
        self._collapse_state.register(user_box, configured_collapsed=False)
        await self._mount_and_scroll(conversation, conversation, user_box)

        turn_state = TurnRenderState()

        self._turn_in_progress = True
        self._update_input_hints()
        try:
            async for event in self._agent_stream(content):
                await self._handle_turn_event(event, conversation, turn_state)
        except Exception as e:
            error_box = create_error_box(f"{type(e).__name__}: {e}")
            self._collapse_state.register(error_box, configured_collapsed=False)
            await self._mount_and_scroll(conversation, conversation, error_box)
        finally:
            self._clear_turn_subagent_task_state()
            self._turn_in_progress = False
            self._update_input_hints()
            prompt_input.disabled = False
            prompt_input.focus()

    async def _handle_turn_event(
        self,
        event: AgentEvent,
        conversation: VerticalScroll,
        turn_state: TurnRenderState,
    ) -> None:
        match event:
            case ThoughtsChunk(agent_id=aid, content=chunk) if aid == self._agent_id:
                await self._handle_main_thoughts_chunk(aid, chunk, conversation, turn_state)
            case Thoughts(agent_id=aid) if aid == self._agent_id:
                await self._handle_main_thoughts_complete(conversation, turn_state)
            case ResponseChunk(agent_id=aid, content=chunk) if aid == self._agent_id:
                await self._handle_main_response_chunk(aid, chunk, conversation, turn_state)
            case Response(agent_id=aid) if aid == self._agent_id:
                await self._handle_main_response_complete(turn_state)
            case ApprovalRequest() as request:
                await self._handle_approval(request, conversation)
            case CodeExecutionOutputChunk(agent_id=aid, text=text, corr_id=cid, parent_corr_id=parent_cid):
                await self._handle_exec_output_chunk(aid, cid, parent_cid, text, conversation, turn_state)
            case CodeExecutionOutput(
                agent_id=aid,
                text=text,
                images=images,
                truncated=truncated,
                corr_id=cid,
                parent_corr_id=parent_cid,
            ):
                await self._handle_exec_output(aid, cid, parent_cid, text, images, truncated, conversation, turn_state)
            case ToolOutput(agent_id=aid, content=tool_content, corr_id=cid):
                await self._handle_tool_output(event, aid, cid, tool_content, conversation)
            case Cancelled():
                pass

    async def _handle_main_thoughts_chunk(
        self,
        agent_id: str,
        chunk: str,
        conversation: VerticalScroll,
        turn_state: TurnRenderState,
    ) -> None:
        if turn_state.thoughts_stream is None:
            box, md = create_thoughts_box(agent_id)
            self._collapse_state.register(box, configured_collapsed=False)
            await self._mount_and_scroll(conversation, conversation, box)
            turn_state.thoughts_stream = Markdown.get_stream(md)

        stream = turn_state.thoughts_stream
        if stream is not None:
            await stream.write(chunk)

    async def _handle_main_thoughts_complete(
        self,
        conversation: VerticalScroll,
        turn_state: TurnRenderState,
    ) -> None:
        if turn_state.thoughts_stream is None:
            return
        await turn_state.thoughts_stream.stop()
        turn_state.thoughts_stream = None
        if not self._config.collapse_thoughts_on_complete:
            return
        match conversation.query(".thoughts-box").last():
            case Collapsible() as last_box:
                self._collapse_state.set_configured(last_box, collapsed=True)

    async def _handle_main_response_chunk(
        self,
        agent_id: str,
        chunk: str,
        conversation: VerticalScroll,
        turn_state: TurnRenderState,
    ) -> None:
        if turn_state.response_stream is None:
            box, md = create_response_box(agent_id)
            self._collapse_state.register(box, configured_collapsed=False)
            await self._mount_and_scroll(conversation, conversation, box)
            turn_state.response_stream = Markdown.get_stream(md)

        stream = turn_state.response_stream
        if stream is not None:
            await stream.write(chunk)

    async def _handle_main_response_complete(self, turn_state: TurnRenderState) -> None:
        if turn_state.response_stream is None:
            return
        await turn_state.response_stream.stop()
        turn_state.response_stream = None

    async def _ensure_exec_output_state(
        self,
        agent_id: str,
        corr_id: str,
        parent_corr_id: str,
        conversation: VerticalScroll,
        turn_state: TurnRenderState,
    ) -> tuple[ExecOutputState, bool]:
        exec_key = (agent_id, corr_id, parent_corr_id)
        existing = turn_state.exec_logs.get(exec_key)
        if existing is not None:
            return existing, False

        box, exec_log = create_exec_output_box(agent_id, corr_id=corr_id)
        self._collapse_state.register(box, configured_collapsed=False)
        target = self._subagent_task_boxes.get(parent_corr_id)
        mount_target = target.trace_container if target is not None else conversation
        await self._mount_and_scroll(mount_target, conversation, box)
        state = ExecOutputState(box=box, log=exec_log)
        turn_state.exec_logs[exec_key] = state
        return state, True

    async def _handle_exec_output_chunk(
        self,
        agent_id: str,
        corr_id: str,
        parent_corr_id: str,
        text: str,
        conversation: VerticalScroll,
        turn_state: TurnRenderState,
    ) -> None:
        exec_state, _ = await self._ensure_exec_output_state(
            agent_id,
            corr_id,
            parent_corr_id,
            conversation,
            turn_state,
        )
        exec_state.log.write(text)
        self._schedule_scroll_conversation_to_bottom()

    async def _handle_exec_output(
        self,
        agent_id: str,
        corr_id: str,
        parent_corr_id: str,
        text: str | None,
        images: list[Path],
        truncated: bool,
        conversation: VerticalScroll,
        turn_state: TurnRenderState,
    ) -> None:
        exec_state, created_now = await self._ensure_exec_output_state(
            agent_id,
            corr_id,
            parent_corr_id,
            conversation,
            turn_state,
        )
        rewrite_text = text if (truncated or created_now) else None
        finalize_exec_output(exec_state.log, rewrite_text, images)
        if self._config.collapse_exec_output_on_complete:
            self._collapse_state.set_configured(exec_state.box, collapsed=True)
        self._schedule_scroll_conversation_to_bottom()
        del turn_state.exec_logs[(agent_id, corr_id, parent_corr_id)]

    async def _handle_tool_output(
        self,
        event: ToolOutput,
        agent_id: str,
        corr_id: str,
        tool_content: object,
        conversation: VerticalScroll,
    ) -> None:
        output_text = extract_tool_output_text(tool_content)
        box = create_tool_output_box(output_text, agent_id, corr_id=corr_id)
        self._collapse_state.register(
            box,
            configured_collapsed=self._config.collapse_tool_outputs,
        )
        await self._mount_and_scroll(self._event_target(event, conversation), conversation, box)
        if not event.parent_corr_id and corr_id in self._subagent_task_boxes:
            self._mark_subagent_task_completed(corr_id)

    def _build_approval_box(self, request: ApprovalRequest) -> Collapsible:
        """Create the widget used to present a pending tool approval."""
        match request.tool_call:
            case CodeAction(code=code):
                return create_code_action_box(code, agent_id=request.agent_id, corr_id=request.corr_id)
            case FileEdit(path=path, edits=edits):
                return create_file_edit_action_box(path, edits, agent_id=request.agent_id, corr_id=request.corr_id)
            case FileRead(paths=paths, head=head, tail=tail):
                return create_file_read_action_box(
                    paths,
                    head,
                    tail,
                    agent_id=request.agent_id,
                    corr_id=request.corr_id,
                )
            case FileWrite(path=path, content=content):
                return create_file_write_action_box(
                    path,
                    content,
                    agent_id=request.agent_id,
                    corr_id=request.corr_id,
                )
            case ShellAction(command=command):
                return create_tool_call_box(
                    "bash",
                    {"command": command},
                    agent_id=request.agent_id,
                    corr_id=request.corr_id,
                )
            case GenericCall(tool_name="subagent_task", tool_args=tool_args):
                box, trace_container = create_subagent_task_box(
                    tool_args,
                    agent_id=request.agent_id,
                    corr_id=request.corr_id,
                )
                if request.corr_id:
                    self._subagent_task_boxes[request.corr_id] = SubagentTaskBoxState(
                        box=box,
                        trace_container=trace_container,
                    )
                return box
            case GenericCall(tool_name=tool_name, tool_args=tool_args, ptc=ptc):
                return create_tool_call_box(
                    tool_name,
                    tool_args,
                    agent_id=request.agent_id,
                    corr_id=request.corr_id,
                    ptc=ptc,
                )
            case _:
                raise ValueError(f"Unsupported tool call: {request.tool_call!r}")

    async def _handle_approval(
        self,
        request: ApprovalRequest,
        conversation: VerticalScroll,
    ) -> None:
        tc = request.tool_call
        target = self._event_target(request, conversation)
        box = self._build_approval_box(request)

        pin_pending = self._config.pin_pending_approval_action_expanded
        self._collapse_state.register(box, configured_collapsed=False, force_expanded=pin_pending)
        if pin_pending:
            self._pending_approval_widget_id = id(box)
        await self._mount_and_scroll(target, conversation, box)

        # Check pre-approval
        suggested = suggest_pattern(tc)
        pre_approved = self._skip_permissions or self._permission_manager.is_allowed(tc)

        if pre_approved:
            if self._pending_approval_widget_id == id(box):
                self._pending_approval_widget_id = None
                self._collapse_state.set_forced(box, enabled=False)
            self._collapse_state.set_configured(
                box,
                collapsed=self._collapse_for_approved_action(tc),
            )
            if request.corr_id and request.corr_id in self._subagent_task_boxes:
                self._mark_subagent_task_active(request.corr_id)
            request.approve(True)
            return

        # Prompt user for approval
        self._approval_future = asyncio.get_running_loop().create_future()
        bar = ApprovalBar(pattern=suggested)
        await self._mount_and_scroll(conversation, conversation, bar)

        decision, pattern = await self._approval_future
        self._approval_future = None

        await bar.remove()
        if self._pending_approval_widget_id == id(box):
            self._pending_approval_widget_id = None
            self._collapse_state.set_forced(box, enabled=False)

        match decision:
            case 2:
                await arun(self._permission_manager.allow_always, parse_pattern(pattern, tc))
            case 3:
                self._permission_manager.allow_session(parse_pattern(pattern, tc))

        approved = decision != 0
        if approved:
            self._collapse_state.set_configured(
                box,
                collapsed=self._collapse_for_approved_action(tc),
            )
            if request.corr_id and request.corr_id in self._subagent_task_boxes:
                self._mark_subagent_task_active(request.corr_id)
        else:
            self._collapse_state.set_configured(
                box,
                collapsed=not self._config.keep_rejected_actions_expanded,
            )
        request.approve(approved)

    def on_approval_bar_decided(self, event: ApprovalBar.Decided) -> None:
        future = self._approval_future
        if future is not None and not future.done():
            future.set_result((event.decision, event.pattern))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "approve_hotkey":
            if not self._has_pending_approval():
                return False
            bars = self.query("ApprovalBar")
            if bars and bars.last().editing:
                return False
            return True
        if action == "approval_rule_hotkey":
            if not self._has_pending_approval():
                return False
            bars = self.query("ApprovalBar")
            if not bars:
                return False
            return not bars.last().editing
        if action == "cancel_turn":
            return self._turn_in_progress and self._cancel_fn is not None
        return super().check_action(action, parameters)

    def action_cancel_turn(self) -> None:
        if self._cancel_fn is not None:
            self._cancel_fn()
        if self._approval_future is not None and not self._approval_future.done():
            self._approval_future.set_result((0, ""))

    def action_approve_hotkey(self, decision: int) -> None:
        future = self._approval_future
        if future is not None and not future.done():
            # Read pattern from the current ApprovalBar if available
            bars = self.query("ApprovalBar")
            pattern = bars.last().pattern if bars else ""
            future.set_result((decision, pattern))

    def action_approval_rule_hotkey(self, scope: int) -> None:
        bars = self.query("ApprovalBar")
        if not bars:
            return
        bars.last().action_save_rule(scope)

    def action_toggle_expand_all(self) -> None:
        self._collapse_state.toggle_expand_all(list(self.query("Collapsible")))

    def _has_pending_approval(self) -> bool:
        if self._approval_future is not None and not self._approval_future.done():
            return True
        return False

    def _collapse_for_approved_action(self, tool_call: ToolCall) -> bool:
        match tool_call:
            case CodeAction():
                return self._config.collapse_approved_code_actions
            case GenericCall(tool_name="subagent_task"):
                return False
            case _:
                return self._config.collapse_approved_tool_calls

    # --- Picker integration ---

    def on_text_area_changed(self, event: "textual.widgets.TextArea.Changed") -> None:  # type: ignore[name-defined]  # noqa: F821
        if event.text_area.id != "prompt-input":
            return
        slash_ctx = _find_slash_command_context(event.text_area.text, event.text_area.cursor_location)
        if slash_ctx is not None and self._skills_metadata:
            self._open_skill_picker(slash_ctx)
            return
        at_ctx = _find_at_reference_context(event.text_area.text, event.text_area.cursor_location)
        if at_ctx is not None:
            self._open_file_picker(at_ctx)

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

    def _open_skill_picker(self, context: SlashCommandContext) -> None:
        async def handle_result(skill_name: str | None) -> None:
            if skill_name is not None:
                prompt_input = self.query_one("#prompt-input", PromptInput)
                prompt_input.replace(
                    f"{skill_name} ",
                    context.start,
                    context.end,
                )

        self.push_screen(
            SkillPickerScreen(skills=self._skills_metadata),
            callback=handle_result,
        )


def convert_at_references(text: str) -> str:
    """Convert `@path` tokens to `<attachment path="..."/>` tags.

    Args:
        text: User prompt text that may contain `@path` tokens.

    Returns:
        Prompt text with `@path` tokens replaced by attachment tags.
    """
    return re.sub(r"@(\S+)", r'<attachment path="\1"/>', text)


def convert_slash_commands(text: str, skills: list[SkillMetadata]) -> str:
    """Convert `/skill-name args` at prompt start to `<skill>` tags.

    Args:
        text: User prompt text.
        skills: Available skill metadata entries.

    Returns:
        Text with leading slash command replaced by a skill tag, or unchanged text.
    """
    match = re.match(r"^/(\S+)([\s\S]*)", text)
    if match is None:
        return text
    name = match.group(1)
    args = match.group(2).strip()
    skills_by_name = {s.name: s for s in skills}
    skill = skills_by_name.get(name)
    if skill is None:
        return text
    return f'<skill name="{skill.name}">{args}</skill>'


__all__ = [
    "AtReferenceContext",
    "SlashCommandContext",
    "TerminalApp",
    "TerminalInterface",
    "convert_at_references",
    "convert_slash_commands",
]
