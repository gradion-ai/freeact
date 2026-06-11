from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.segment import Segment
from rich.style import Style as RichStyle
from rich.syntax import Syntax
from rich.text import Span as RichSpan
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.binding import Binding
from textual.containers import Vertical
from textual.content import Content
from textual.events import Key
from textual.keys import Keys
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Input, Markdown, RichLog, Static, TextArea

from freeact.terminal.view import TrackedCollapsible

# Register Alt+Enter (ESC + CR) to produce the same key event as Ctrl+J,
# which PromptInput handles as newline insertion. Without this, the xterm
# parser drops the \x1b\r sequence entirely in basic keyboard mode.
ANSI_SEQUENCES_KEYS["\x1b\r"] = (Keys.ControlJ,)  # type: ignore[index]

_PROMPT_GUTTER = "> "
_GUTTER_WIDTH = len(_PROMPT_GUTTER)


class PromptInput(TextArea):
    """Prompt input area with submit-on-enter behavior.

    Pressing `Enter` submits the prompt. `Alt+Enter` (mapped to `ctrl+j`)
    inserts a newline so users can compose multi-line input.
    """

    BINDINGS = [
        Binding("super+v", "paste", "Paste", show=False, priority=True),
        Binding("ctrl+shift+v", "paste", "Paste", show=False, priority=True),
        Binding("shift+insert", "paste", "Paste", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    PromptInput {
        height: auto;
        max-height: 12;
        min-height: 3;
        border: solid $border-blurred;
    }
    PromptInput:focus {
        border: solid $border;
    }
    """

    class Submitted(Message):
        """Message emitted when the prompt is submitted."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, clipboard_reader: Callable[[], str] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.show_line_numbers = False
        self.soft_wrap = True
        self._clipboard_reader = clipboard_reader

    @property
    def gutter_width(self) -> int:  # type: ignore[override]
        return _GUTTER_WIDTH

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        gutter_text = _PROMPT_GUTTER if y == 0 else " " * _GUTTER_WIDTH
        gutter_style = self.get_component_rich_style("text-area--gutter")
        return Strip(
            [Segment(gutter_text, gutter_style), *strip._segments],
            strip.cell_length + _GUTTER_WIDTH,
        )

    async def _on_key(self, event: Key) -> None:
        if event.key == "escape":
            if self.text:
                event.prevent_default()
                event.stop()
                self.clear()
            return

        if event.key in ("ctrl+j", "newline"):
            event.prevent_default()
            event.stop()
            self.insert("\n")
            return

        if event.key in ("enter", "ctrl+m"):
            event.prevent_default()
            event.stop()
            text = self.text.strip()
            if not text:
                self.notify("Please enter a non-empty message", severity="warning")
                return
            self.post_message(self.Submitted(text))
            self.clear()

    def action_paste(self) -> None:
        """Paste text using the app-provided clipboard reader when available."""
        if self.read_only:
            return
        clipboard = self._clipboard_reader() if self._clipboard_reader is not None else self.app.clipboard
        if result := self._replace_via_keyboard(clipboard, *self.selection):
            self.move_cursor(result.end_location)
            self.focus()


class ApprovalBar(Static):
    """Inline approval prompt with keyboard shortcuts and editable pattern."""

    can_focus = True

    DEFAULT_CSS = """
    ApprovalBar {
        height: auto;
        padding: 0 0 0 1;
        text-style: bold;
        color: $warning;
    }
    ApprovalBar Input {
        width: auto;
        min-width: 20;
        height: 1;
        border: none;
        padding: 0;
        margin: 0 1 0 0;
        background: $surface;
    }
    ApprovalBar Input:focus {
        border: none;
    }
    """

    class Decided(Message):
        """Message emitted when an approval decision is made."""

        def __init__(self, decision: int, pattern: str = "") -> None:
            super().__init__()
            self.decision = decision
            self.pattern = pattern

    BINDINGS = [
        ("y", "decide(1)", "Yes"),
        ("enter", "decide(1)", "Yes"),
        ("n", "decide(0)", "No"),
        ("a", "save_rule(2)", "Always"),
        ("s", "save_rule(3)", "Session"),
    ]

    def __init__(self, pattern: str = "", display_text: str = "", **kwargs: Any) -> None:
        self._pattern = pattern
        self._display_text = display_text
        self._editing = False
        self._pending_decision: int = 0
        super().__init__(self._render_text(), markup=False, **kwargs)

    def _render_text(self) -> str:
        body = self._display_text or self._pattern
        if body:
            return f"Approve? [Y/n/a/s] {body}"
        return "Approve? [Y/n/a/s]"

    def action_decide(self, decision: int) -> None:
        self.post_message(self.Decided(decision, pattern=self._pattern))

    def action_save_rule(self, scope: int) -> None:
        """Enter edit mode for the pattern before saving a rule."""
        self._editing = True
        self._pending_decision = scope
        self.update("")
        input_widget = Input(value=self._pattern, id="approval-pattern-input", select_on_focus=False)
        self.mount(input_widget)
        input_widget.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Save the edited pattern and approve."""
        self._pattern = event.value
        self._editing = False
        event.input.remove()
        self.post_message(self.Decided(self._pending_decision, pattern=self._pattern))

    @property
    def editing(self) -> bool:
        """Whether the pattern input is currently active."""
        return self._editing

    @property
    def pattern(self) -> str:
        """Current pattern value."""
        return self._pattern

    @property
    def display_text(self) -> str:
        """Current display text override (empty string falls back to pattern).

        Named to avoid clashing with the inherited Textual `Widget.display`
        reactive (which controls visibility).
        """
        return self._display_text

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self._editing and action in ("decide", "save_rule"):
            return False
        return super().check_action(action, parameters)


def _syntax_to_content(syntax: Syntax) -> Content:
    """Convert a Rich Syntax renderable to a Textual Content object.

    Textual's selection API only works with `Text` or `Content` visuals.
    Rich `Syntax` produces a `RichVisual` that bypasses selection entirely.
    This converts Syntax to Content, preserving foreground syntax colors
    while stripping explicit backgrounds from token spans. Without this,
    Syntax backgrounds override the selection highlight style.
    """
    text = syntax.highlight(syntax.code)
    new_spans = []
    for span in text._spans:
        style = span.style
        if isinstance(style, RichStyle) and style.bgcolor:
            style = RichStyle(color=style.color, bold=style.bold, italic=style.italic, underline=style.underline)
            new_spans.append(RichSpan(span.start, span.end, style))
        else:
            new_spans.append(span)
    text._spans = new_spans
    if isinstance(text.style, RichStyle) and text.style.bgcolor:
        text.style = RichStyle(
            color=text.style.color, bold=text.style.bold, italic=text.style.italic, underline=text.style.underline
        )
    return Content.from_rich_text(text)


def syntax_content(code: str, lexer: str) -> Static:
    """Create a selectable, syntax-highlighted Static widget.

    Args:
        code: Source text to highlight.
        lexer: Pygments lexer name (for example `"python"`, `"bash"`).

    Returns:
        Static widget rendering the highlighted text as selectable Content.
    """
    return Static(_syntax_to_content(Syntax(code, lexer, theme="monokai")))


def diff_content(path: str, old_text: str, new_text: str) -> Static:
    """Render a file edit as a unified diff preview.

    Args:
        path: Target file path for the edit action.
        old_text: Text to find and replace.
        new_text: Replacement text.

    Returns:
        Static widget rendering the diff as selectable highlighted Content.
    """
    diff_lines = [
        f"--- a/{path}",
        f"+++ b/{path}",
        "@@ edit @@",
    ]
    for line in old_text.splitlines():
        diff_lines.append(f"-{line}")
    for line in new_text.splitlines():
        diff_lines.append(f"+{line}")
    return syntax_content("\n".join(diff_lines), "diff")


def _titled(label: str, agent_id: str) -> str:
    """Format a widget title with an agent prefix.

    Args:
        label: Base title label for the widget.
        agent_id: Agent identifier to include as a prefix.

    Returns:
        Title string formatted for collapsible box headers.
    """
    parts: list[str] = []
    if agent_id:
        parts.append(f"\\[{agent_id}]")
    parts.append(label)
    return " ".join(parts)


def create_box(
    *children: Widget,
    title: str,
    agent_id: str = "",
    collapsed: bool = False,
    classes: str = "",
) -> TrackedCollapsible:
    """Create a titled collapsible box wrapping the given content widgets.

    Args:
        *children: Content widgets to display inside the box.
        title: Base title label (prefixed with `[agent-id]` when set).
        agent_id: Agent identifier for the title prefix.
        collapsed: Initial collapsed state.
        classes: CSS classes for the box.

    Returns:
        Collapsible widget with the given content.
    """
    return TrackedCollapsible(
        *children,
        title=_titled(title, agent_id),
        collapsed=collapsed,
        classes=classes,
    )


def create_action_box(
    *children: Widget,
    title: str,
    agent_id: str = "",
    classes: str = "",
) -> tuple[TrackedCollapsible, Vertical]:
    """Create a tool-call box with an appended trace container for nested results.

    Args:
        *children: Content widgets to display before the trace container.
        title: Base title label (prefixed with `[agent-id]` when set).
        agent_id: Agent identifier for the title prefix.
        classes: CSS classes for the box.

    Returns:
        Tuple of the Collapsible widget and the nested trace container.
    """
    trace_container = Vertical(classes="tool-trace-container")
    content = Vertical(*children, trace_container, classes="tool-call-content")
    box = create_box(content, title=title, agent_id=agent_id, collapsed=False, classes=classes)
    return box, trace_container


def create_user_input_box(content: str, agent_id: str = "") -> TrackedCollapsible:
    """Create an expanded collapsible box displaying the submitted user input.

    Args:
        content: The user's submitted prompt text.
        agent_id: Agent identifier for the title prefix.

    Returns:
        Collapsible widget with the input text, expanded by default.
    """
    # Use plain text here so Textual's selection API can extract content.
    text = Static(content, markup=False)
    return create_box(text, title="User Input", agent_id=agent_id, classes="user-input-box")


def create_markdown_box(
    title: str,
    agent_id: str = "",
    classes: str = "",
) -> tuple[TrackedCollapsible, Markdown]:
    """Create an expanded collapsible box for streaming markdown content.

    Args:
        title: Base title label (prefixed with `[agent-id]` when set).
        agent_id: Agent identifier for the title prefix.
        classes: CSS classes for the box.

    Returns:
        Tuple of the Collapsible widget and the Markdown widget inside it.
    """
    md = Markdown()
    box = create_box(md, title=title, agent_id=agent_id, classes=classes)
    return box, md


def create_exec_output_box(agent_id: str = "") -> tuple[TrackedCollapsible, RichLog]:
    """Create a collapsible box for streaming execution output.

    Args:
        agent_id: Agent identifier for the title prefix.

    Returns:
        Tuple of the Collapsible widget and the RichLog widget inside it.
    """
    log = RichLog(wrap=True, markup=False)
    box = create_box(log, title="Execution Output", agent_id=agent_id, classes="exec-output-box")
    return box, log


async def finalize_exec_output(log: RichLog, text: str | None, images: list[Path]) -> None:
    """Replace a streaming RichLog with a selectable Static widget.

    RichLog does not support Textual's native text selection. This swaps
    it for a plain Static after streaming completes.

    Args:
        log: Streaming log widget to replace.
        text: Final text output.
        images: Generated image paths to append.
    """
    parts: list[str] = []
    if text:
        parts.append(text.rstrip("\n"))
    if images:
        parts.append("Produced images:\n" + "\n".join(f"  {path}" for path in images))
    if parts and log.parent is not None:
        static = Static("\n".join(parts), markup=False)
        await log.parent.mount(static, after=log)
        await log.remove()
    elif images:
        log.write("Produced images:\n" + "\n".join(f"  {path}" for path in images))


def create_error_box(message: str, agent_id: str = "") -> TrackedCollapsible:
    """Create a collapsible box displaying an error message.

    Args:
        message: Error message to display.
        agent_id: Agent identifier for the title prefix.

    Returns:
        Collapsible widget with error-styled text.
    """
    text = Static(message, classes="error-text")
    return create_box(text, title="Error", agent_id=agent_id, classes="error-box")
