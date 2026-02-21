import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.segment import Segment
from rich.syntax import Syntax
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.binding import Binding
from textual.keys import Keys
from textual.message import Message
from textual.strip import Strip
from textual.widgets import Collapsible, Markdown, RichLog, Static, TextArea

from freeact.terminal.default.tool_data import (
    TextEditData,
    ToolOutputData,
)

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

    async def _on_key(self, event: "textual.events.Key") -> None:  # type: ignore[name-defined]  # noqa: F821
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
    """Inline approval prompt with legacy-compatible shortcuts."""

    can_focus = True

    DEFAULT_CSS = """
    ApprovalBar {
        height: auto;
        padding: 0 0 0 1;
        text-style: bold;
        color: $warning;
    }
    """

    class Decided(Message):
        """Message emitted when an approval decision is made."""

        def __init__(self, decision: int) -> None:
            super().__init__()
            self.decision = decision

    BINDINGS = [
        ("y", "decide(1)", "Yes"),
        ("enter", "decide(1)", "Yes"),
        ("n", "decide(0)", "No"),
        ("s", "decide(3)", "Session"),
        ("a", "decide(2)", "Always"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("Approve? [Y/n/a/s]", **kwargs)

    def action_decide(self, decision: int) -> None:
        self.post_message(self.Decided(decision))


# --- Collapsible box factory functions ---


def _titled(label: str, agent_id: str, corr_id: str = "") -> str:
    """Format a widget title with agent and correlation prefixes.

    Args:
        label: Base title label for the widget.
        agent_id: Agent identifier to include as a prefix.
        corr_id: Optional correlation identifier to include as a prefix.

    Returns:
        Title string formatted for collapsible box headers.
    """
    parts: list[str] = []
    if agent_id:
        parts.append(f"\\[{agent_id}]")
    if corr_id:
        parts.append(f"\\[{corr_id}]")
    parts.append(label)
    return " ".join(parts)


def create_user_input_box(content: str) -> Collapsible:
    """Create an expanded collapsible box displaying the submitted user input.

    Args:
        content: The user's submitted prompt text.

    Returns:
        Collapsible widget with the input text, expanded by default.
    """
    # Use plain text here so Textual's selection API can extract content.
    # Static.get_selection() does not currently support Rich Syntax renderables.
    text = Static(content, markup=False)
    box = Collapsible(
        text,
        title="User Input",
        collapsed=False,
        classes="user-input-box",
    )
    return box


def create_thoughts_box(agent_id: str = "") -> tuple[Collapsible, Markdown]:
    """Create an expanded collapsible box for streaming thoughts.

    Args:
        agent_id: Agent identifier for the title prefix.

    Returns:
        Tuple of the Collapsible widget and the Markdown widget inside it.
    """
    md = Markdown()
    box = Collapsible(md, title=_titled("Thinking", agent_id), collapsed=False, classes="thoughts-box")
    return box, md


def create_response_box(agent_id: str = "") -> tuple[Collapsible, Markdown]:
    """Create an expanded collapsible box for streaming response.

    Args:
        agent_id: Agent identifier for the title prefix.

    Returns:
        Tuple of the Collapsible widget and the Markdown widget inside it.
    """
    md = Markdown()
    box = Collapsible(md, title=_titled("Response", agent_id), collapsed=False, classes="response-box")
    return box, md


def create_code_action_box(code: str, agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a collapsible box displaying a Python code action.

    Args:
        code: Python source code to display.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget with syntax-highlighted Python code.
    """
    syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
    box = Collapsible(
        Static(syntax),
        title=_titled("Code Action", agent_id, corr_id),
        collapsed=False,
        classes="code-action-box",
    )
    return box


def create_tool_call_box(
    tool_name: str,
    tool_args: dict[str, Any],
    agent_id: str = "",
    corr_id: str = "",
    ptc: bool = False,
) -> Collapsible:
    """Create a collapsible box displaying a tool call with JSON arguments.

    Args:
        tool_name: Name of the tool being called.
        tool_args: Tool arguments to display as JSON.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.
        ptc: Whether this call is a programmatic tool call.

    Returns:
        Collapsible widget with formatted JSON arguments.
    """
    args_json = json.dumps(tool_args, indent=2)
    syntax = Syntax(args_json, "json", theme="monokai")
    title_prefix = "PTC" if ptc else "Tool Call"
    box = Collapsible(
        Static(syntax),
        title=_titled(f"{title_prefix}: {tool_name}", agent_id, corr_id),
        collapsed=False,
        classes="tool-call-box",
    )
    return box


def create_exec_output_box(agent_id: str = "", corr_id: str = "") -> tuple[Collapsible, RichLog]:
    """Create a collapsible box for streaming execution output.

    Args:
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Tuple of the Collapsible widget and the RichLog widget inside it.
    """
    log = RichLog(wrap=True, markup=False)
    box = Collapsible(
        log, title=_titled("Execution Output", agent_id, corr_id), collapsed=False, classes="exec-output-box"
    )
    return box, log


def finalize_exec_output(log: RichLog, text: str | None, images: list[Path]) -> None:
    """Finalize a streaming execution log with terminal output and image paths.

    Args:
        log: Target log widget to update.
        text: Final text output. When present, replaces streamed content.
        images: Generated image paths to append to the log.
    """
    if text:
        log.clear()
        syntax = Syntax(text.rstrip("\n"), "text", theme="monokai", line_numbers=True)
        log.write(syntax)
    if images:
        log.write("Produced images:\n" + "\n".join(f"  {path}" for path in images))


def create_tool_output_box(data: ToolOutputData, agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a collapsed box for generic tool output text.

    Args:
        data: Canonical tool output payload.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title prefix.

    Returns:
        Collapsible widget that displays truncated tool output.
    """
    display_content = data.content[:500] + "..." if len(data.content) > 500 else data.content
    syntax = Syntax(display_content, "text", theme="monokai", line_numbers=True)
    box = Collapsible(
        Static(syntax),
        title=_titled("Tool Output", agent_id, corr_id),
        collapsed=True,
        classes="tool-output-box",
    )
    return box


def create_error_box(message: str) -> Collapsible:
    """Create a collapsible box displaying an error message.

    Args:
        message: Error message to display.

    Returns:
        Collapsible widget with error-styled text.
    """
    box = Collapsible(
        Static(message, classes="error-text"),
        title="Error",
        collapsed=False,
        classes="error-box",
    )
    return box


def create_file_read_action_box(
    paths: tuple[str, ...],
    head: int | None,
    tail: int | None,
    agent_id: str = "",
    corr_id: str = "",
) -> Collapsible:
    """Create a collapsible box for a file read action.

    Args:
        paths: Target file paths.
        head: Optional head-line count for single-file reads.
        tail: Optional tail-line count for single-file reads.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget showing the requested paths and any range parameters.
    """
    if len(paths) == 1:
        path = paths[0]
        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        parts: list[str] = [path]
        if head is not None:
            parts.append(f"head: {head}")
        if tail is not None:
            parts.append(f"tail: {tail}")
        return Collapsible(
            Static("\n".join(parts)),
            title=_titled(f"Read Action: {filename}", agent_id, corr_id),
            collapsed=False,
            classes="read-file-box",
        )

    path_list = "\n".join(f"  {path}" for path in paths)
    return Collapsible(
        Static(path_list),
        title=_titled(f"Read Action: {len(paths)} files", agent_id, corr_id),
        collapsed=False,
        classes="read-files-box",
    )


def create_file_write_action_box(path: str, content: str, agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a box that previews a file write action.

    Args:
        path: Target file path.
        content: Full file content to be written.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title prefix.

    Returns:
        Collapsible widget with syntax-highlighted file content.
    """
    ext = path.rsplit(".", 1)[-1] if "." in path else "text"
    syntax = Syntax(content, ext, theme="monokai", line_numbers=True)
    box = Collapsible(
        Static(syntax),
        title=_titled(f"Write Action: {path}", agent_id, corr_id),
        collapsed=False,
        classes="write-file-box",
    )
    return box


def create_file_edit_action_box(
    path: str,
    edits: tuple[TextEditData, ...],
    agent_id: str = "",
    corr_id: str = "",
) -> Collapsible:
    """Create a box that renders file edits as a unified diff preview.

    Args:
        path: Target file path for the edit action.
        edits: Canonical text edits to apply.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title prefix.

    Returns:
        Collapsible widget containing a synthetic unified diff.
    """
    diff_lines = [
        f"--- a/{path}",
        f"+++ b/{path}",
    ]
    for edit in edits:
        old_text = edit.old_text
        new_text = edit.new_text
        diff_lines.append("@@ edit @@")
        for line in old_text.splitlines():
            diff_lines.append(f"-{line}")
        for line in new_text.splitlines():
            diff_lines.append(f"+{line}")

    diff_text = "\n".join(diff_lines)
    syntax = Syntax(diff_text, "diff", theme="monokai")
    box = Collapsible(
        Static(syntax),
        title=_titled(f"Edit Action: {path}", agent_id, corr_id),
        collapsed=False,
        classes="diff-box",
    )
    return box
