import json
from typing import Any

from rich.segment import Segment
from rich.syntax import Syntax
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.keys import Keys
from textual.message import Message
from textual.strip import Strip
from textual.widgets import Collapsible, Markdown, RichLog, Static, TextArea

# Register Alt+Enter (ESC + CR) to produce the same key event as Ctrl+J,
# which PromptInput handles as newline insertion. Without this, the xterm
# parser drops the \x1b\r sequence entirely in basic keyboard mode.
ANSI_SEQUENCES_KEYS["\x1b\r"] = (Keys.ControlJ,)  # type: ignore[index]

_PROMPT_GUTTER = "> "
_GUTTER_WIDTH = len(_PROMPT_GUTTER)


class PromptInput(TextArea):
    """Multi-line input that submits on Enter and inserts newline on Alt+Enter.

    Displays a `> ` gutter on the first line of the input.
    """

    DEFAULT_CSS = """
    PromptInput {
        height: auto;
        max-height: 12;
        min-height: 3;
    }
    """

    class Submitted(Message):
        """Posted when the user submits their prompt."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.show_line_numbers = False

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


class ApprovalBar(Static):
    """Inline approval prompt with keyboard shortcuts matching the legacy UI."""

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
        """Posted when the user makes an approval decision."""

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
        super().__init__("Approve? [Y/n/a/s]: ", **kwargs)

    def action_decide(self, decision: int) -> None:
        self.post_message(self.Decided(decision))


# --- Collapsible box factory functions ---


def _titled(label: str, agent_id: str, corr_id: str = "") -> str:
    """Format a box title with an `[agent_id]` prefix and optional `[corr_id]`."""
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
    syntax = Syntax(content, "text", theme="monokai", line_numbers=False)
    box = Collapsible(
        Static(syntax),
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
    tool_name: str, tool_args: dict[str, Any], agent_id: str = "", corr_id: str = ""
) -> Collapsible:
    """Create a collapsible box displaying a tool call with JSON arguments.

    Args:
        tool_name: Name of the tool being called.
        tool_args: Tool arguments to display as JSON.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget with formatted JSON arguments.
    """
    args_json = json.dumps(tool_args, indent=2)
    syntax = Syntax(args_json, "json", theme="monokai")
    box = Collapsible(
        Static(syntax),
        title=_titled(f"Tool: {tool_name}", agent_id, corr_id),
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


def create_tool_output_box(content: str, agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a collapsed collapsible box for tool output.

    Args:
        content: Tool output text (truncated to 500 chars for display).
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget with truncated output, collapsed by default.
    """
    display_content = content[:500] + "..." if len(content) > 500 else content
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


def create_read_file_box(tool_args: dict[str, Any], agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a collapsible box for a file read request.

    Args:
        tool_args: Tool arguments containing `path` and optional `head`/`tail`.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget showing the path and any range parameters.
    """
    path = tool_args.get("path", "unknown")
    filename = path.rsplit("/", 1)[-1] if "/" in path else path
    parts: list[str] = [path]
    if "head" in tool_args:
        parts.append(f"head: {tool_args['head']}")
    if "tail" in tool_args:
        parts.append(f"tail: {tool_args['tail']}")
    box = Collapsible(
        Static("\n".join(parts)),
        title=_titled(f"Read: {filename}", agent_id, corr_id),
        collapsed=False,
        classes="read-file-box",
    )
    return box


def create_read_multiple_files_box(tool_args: dict[str, Any], agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a collapsible box for a multi-file read request.

    Args:
        tool_args: Tool arguments containing `paths` list.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget listing the paths to read.
    """
    paths: list[str] = tool_args.get("paths", [])
    path_list = "\n".join(f"  {p}" for p in paths)
    box = Collapsible(
        Static(path_list),
        title=_titled(f"Read: {len(paths)} files", agent_id, corr_id),
        collapsed=False,
        classes="read-files-box",
    )
    return box


def create_write_file_box(tool_args: dict[str, Any], agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a collapsible box for a file write request.

    Args:
        tool_args: Tool arguments containing `path` and `content`.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget with syntax-highlighted file content.
    """
    path = tool_args.get("path", "unknown")
    content = tool_args.get("content", "")
    ext = path.rsplit(".", 1)[-1] if "." in path else "text"
    syntax = Syntax(content, ext, theme="monokai", line_numbers=True)
    box = Collapsible(
        Static(syntax),
        title=_titled(f"Write: {path}", agent_id, corr_id),
        collapsed=False,
        classes="write-file-box",
    )
    return box


def create_read_output_box(
    title: str,
    filenames: list[str],
    content: str,
    agent_id: str = "",
    lexer: str = "",
    corr_id: str = "",
) -> Collapsible:
    """Create a collapsed collapsible box for file read output.

    Shows filenames followed by syntax-highlighted content.

    Args:
        title: Box title (e.g. ``"Read Output: config.json"``).
        filenames: File paths to display at the top of the box.
        content: File content to display.
        agent_id: Agent identifier for the title prefix.
        lexer: Explicit Pygments lexer name. When empty, auto-detected
            from the first filename's extension.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget with filenames and content, collapsed by default.
    """
    if not lexer and filenames:
        first = filenames[0]
        lexer = first.rsplit(".", 1)[-1] if "." in first else "text"
    lexer = lexer or "text"
    syntax = Syntax(content, lexer, theme="monokai", line_numbers=True)
    children: list[Static] = []
    if filenames:
        children.append(Static("\n".join(filenames)))
    children.append(Static(syntax))
    box = Collapsible(
        *children,
        title=_titled(title, agent_id, corr_id),
        collapsed=True,
        classes="tool-output-box",
    )
    return box


def create_diff_box(tool_args: dict[str, Any], agent_id: str = "", corr_id: str = "") -> Collapsible:
    """Create a collapsible box displaying a unified diff for file edits.

    Formats `filesystem_edit_file` tool arguments as a unified diff.
    Supports both camelCase (`oldText`/`newText`) and snake_case
    (`old_text`/`new_text`) keys in the `edits` array.

    Args:
        tool_args: Tool arguments containing `path` and `edits`.
        agent_id: Agent identifier for the title prefix.
        corr_id: Correlation identifier for the title.

    Returns:
        Collapsible widget with syntax-highlighted diff.
    """
    path = tool_args.get("path", "unknown")
    edits: list[dict[str, str]] = tool_args.get("edits", [])

    diff_lines = [
        f"--- a/{path}",
        f"+++ b/{path}",
    ]
    for edit in edits:
        old_text = edit.get("oldText") or edit.get("old_text", "")
        new_text = edit.get("newText") or edit.get("new_text", "")
        diff_lines.append("@@ edit @@")
        for line in old_text.splitlines():
            diff_lines.append(f"-{line}")
        for line in new_text.splitlines():
            diff_lines.append(f"+{line}")

    diff_text = "\n".join(diff_lines)
    syntax = Syntax(diff_text, "diff", theme="monokai")
    box = Collapsible(
        Static(syntax),
        title=_titled(f"Edit: {path}", agent_id, corr_id),
        collapsed=False,
        classes="diff-box",
    )
    return box
