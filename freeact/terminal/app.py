import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static, TextArea

from freeact.config import SkillMetadata, TerminalSection
from freeact.events import AgentEvent
from freeact.permissions import PermissionManager
from freeact.terminal.approvals import ApprovalController
from freeact.terminal.clipboard import ClipboardAdapter, ClipboardAdapterProtocol
from freeact.terminal.dispatcher import EventDispatcher
from freeact.terminal.screens import FilePickerScreen, SkillPickerScreen
from freeact.terminal.view import ConversationView
from freeact.terminal.widgets import ApprovalBar, PromptInput, create_error_box, create_user_input_box

AgentStreamFn: TypeAlias = Callable[[str], AsyncIterator[AgentEvent]]
Location: TypeAlias = tuple[int, int]


@dataclass(frozen=True)
class SlashCommandContext:
    """Cursor range that covers the `/command` token in the prompt."""

    start: Location
    end: Location


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


def _find_at_trigger(text: str, cursor: Location) -> Location | None:
    """Return the position of `@` when cursor is immediately after it at a word boundary.

    Only triggers when `@` is at the start of the line or preceded by whitespace.

    Args:
        text: Prompt text content.
        cursor: Current cursor location as `(row, column)`.

    Returns:
        Position of the `@` character, or `None` when no trigger is active.
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

    at_col = col - 1
    if at_col > 0 and not line[at_col - 1].isspace():
        return None

    return (row, at_col)


def _format_picked_path(path: Path, cwd: Path | None = None) -> str:
    """Format a file picker selection as a path string for prompt insertion.

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


class TerminalApp(App[None]):
    """Main Textual application for the freeact terminal UI."""

    DEFAULT_CSS = """
    #input-dock {
        dock: bottom;
        height: auto;
        max-height: 14;
        padding: 0 1;
    }
    #input-hints {
        color: $text-muted;
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
        *,
        agent_id: str,
        stream: AgentStreamFn,
        cancel: Callable[[], None],
        skills_metadata: list[SkillMetadata],
        terminal_config: TerminalSection,
        permissions: PermissionManager,
        skip_permissions: bool,
        working_dir: Path,
        clipboard_adapter: ClipboardAdapterProtocol | None = None,
    ) -> None:
        """Initialize the terminal application.

        Args:
            agent_id: Identifier of the main agent.
            stream: Callable starting one agent turn for a prompt.
            cancel: Callable cancelling the current agent turn.
            skills_metadata: Available skills for the skill picker.
            terminal_config: Terminal UI configuration.
            permissions: Permission manager for approval pre-checks and rules.
            skip_permissions: Run tools without prompting for approval.
            working_dir: Working directory shown in the banner and used for
                file picker path formatting.
            clipboard_adapter: OS clipboard adapter override (used in tests).
        """
        super().__init__()
        self._agent_id = agent_id
        self._stream = stream
        self._cancel = cancel
        self._skills_metadata = skills_metadata
        self._terminal_config = terminal_config
        self._skip_permissions = skip_permissions
        self._working_dir = working_dir
        self._clipboard_adapter = clipboard_adapter or ClipboardAdapter()
        self._turn_in_progress = False
        self._view = ConversationView(working_dir, id="conversation")
        self._approvals = ApprovalController(
            view=self._view,
            permissions=permissions,
            config=terminal_config,
            skip_permissions=skip_permissions,
        )
        self._bindings.bind(
            terminal_config.expand_all_toggle_key,
            "toggle_expand_all",
            show=False,
            priority=True,
        )

    def compose(self) -> ComposeResult:
        yield self._view
        with Vertical(id="input-dock"):
            yield PromptInput(id="prompt-input", clipboard_reader=self.read_clipboard_for_paste)
            yield Static("ctrl+q: quit", id="input-hints")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", PromptInput).focus()
        self.call_after_refresh(self._view.scroll_to_latest)

    def _update_input_hints(self) -> None:
        results = self.query("#input-hints")
        if not results:
            return
        hints = results.first(Static)
        if self._turn_in_progress:
            hints.update("ctrl+q: quit  esc: interrupt")
        elif self.query_one("#prompt-input", PromptInput).text:
            hints.update("ctrl+q: quit  esc: clear")
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

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        self._process_turn(event.text)

    @work(exclusive=True)
    async def _process_turn(self, text: str) -> None:
        prompt_input = self.query_one("#prompt-input", PromptInput)
        prompt_input.disabled = True
        self._view.anchor()

        await self._view.mount_box(create_user_input_box(text))

        dispatcher = EventDispatcher(
            agent_id=self._agent_id,
            view=self._view,
            approvals=self._approvals,
            config=self._terminal_config,
        )
        content = convert_slash_commands(text, self._skills_metadata)

        self._turn_in_progress = True
        self._update_input_hints()
        try:
            async for event in self._stream(content):
                await dispatcher.dispatch(event)
        except Exception as e:
            await self._view.mount_box(create_error_box(f"{type(e).__name__}: {e}"))
        finally:
            dispatcher.finish()
            self._turn_in_progress = False
            self._update_input_hints()
            prompt_input.disabled = False
            prompt_input.focus()

    def on_approval_bar_decided(self, event: ApprovalBar.Decided) -> None:
        self._approvals.on_decided(event.decision, event.pattern)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "approve_hotkey":
            return self._approvals.pending and not self._approvals.bar_editing
        if action == "approval_rule_hotkey":
            return self._approvals.pending and self._approvals.has_bar and not self._approvals.bar_editing
        if action == "cancel_turn":
            return self._turn_in_progress
        return super().check_action(action, parameters)

    def action_cancel_turn(self) -> None:
        self._cancel()
        self._approvals.reject_pending()

    def action_approve_hotkey(self, decision: int) -> None:
        self._approvals.resolve(decision)

    def action_approval_rule_hotkey(self, scope: int) -> None:
        self._approvals.open_rule_editor(scope)

    def action_toggle_expand_all(self) -> None:
        self._view.toggle_expand_all()

    # --- Picker integration ---

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id != "prompt-input":
            return
        self._update_input_hints()
        slash_ctx = _find_slash_command_context(event.text_area.text, event.text_area.cursor_location)
        if slash_ctx is not None and self._skills_metadata:
            self._open_skill_picker(slash_ctx)
            return
        at_pos = _find_at_trigger(event.text_area.text, event.text_area.cursor_location)
        if at_pos is not None:
            self._open_file_picker(at_pos)

    def _open_file_picker(self, at_pos: Location) -> None:
        at_end: Location = (at_pos[0], at_pos[1] + 1)

        async def handle_result(path: Path | None) -> None:
            if path is not None:
                prompt_input = self.query_one("#prompt-input", PromptInput)
                prompt_input.replace(
                    _format_picked_path(path, self._working_dir),
                    at_pos,
                    at_end,
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
