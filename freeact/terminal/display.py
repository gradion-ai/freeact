import json
import os
import platform
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.filters import has_completions
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text

from freeact.terminal.completion import AtFileCompleter


def _create_key_bindings() -> KeyBindings:
    """Create key bindings for multiline input with completion support.

    - Enter: Submit input (or close completion menu if visible)
    - Tab: Accept completion; opens next level for directories, closes for files
    - Option/Alt+Enter: Insert newline
    """
    kb = KeyBindings()

    @kb.add("enter", filter=~has_completions)
    def submit(event) -> None:
        event.app.exit(result=event.app.current_buffer.text)

    @kb.add("escape", "enter")
    def newline(event) -> None:
        event.current_buffer.insert_text("\n")

    @kb.add("tab", filter=~has_completions)
    def tab_start_completion(event) -> None:
        event.current_buffer.start_completion()

    @kb.add("tab", filter=has_completions)
    def tab_accept_completion(event) -> None:
        buffer = event.current_buffer
        state = buffer.complete_state
        if state is None:
            return

        # If no completion selected, select the first one
        if state.complete_index is None and state.completions:
            buffer.go_to_completion(0)

        # Check if current path ends with separator (directory)
        text = buffer.document.text_before_cursor
        is_directory = text.endswith(os.sep)

        # Close menu, then reopen if directory
        buffer.complete_state = None
        if is_directory:
            buffer.start_completion()

    @kb.add("enter", filter=has_completions)
    def enter_accept_completion(event) -> None:
        # Completion text is already in buffer when selected.
        # Just close the completion menu.
        event.current_buffer.complete_state = None

    return kb


def _get_newline_key_hint() -> str:
    """Return platform-appropriate key hint for newline."""
    return "Option" if platform.system() == "Darwin" else "Alt"


class Display:
    """Rich-based terminal rendering and user input handling.

    Renders agent events (thoughts, responses, tool calls, code actions)
    using Rich formatting and handles user prompts via prompt_toolkit.
    """

    def __init__(
        self,
        console: Console,
        user_header_color: str = "dodger_blue1",
        thoughts_header_color: str = "dim",
        thoughts_color: str = "dim",
        response_header_color: str = "green",
        response_color: str | None = None,
        tool_panel_color: str = "yellow",
        tool_output_header_color: str = "navajo_white3",
        tool_output_color: str = "navajo_white3",
        exec_panel_color: str = "yellow",
        exec_output_header_color: str = "navajo_white3",
        exec_output_color: str = "navajo_white3",
        image_panel_color: str = "magenta",
        approval_color: str = "yellow",
        goodbye_color: str = "dim",
        warning_color: str = "yellow",
    ):
        """Initialize display with console and color configuration.

        Args:
            console: Rich Console for output rendering.
            user_header_color: Color for the "User" section header.
            thoughts_header_color: Color for the "Thinking" section header.
            thoughts_color: Color for streamed thinking content.
            response_header_color: Color for the "Response" section header.
            response_color: Color for streamed response content.
            tool_panel_color: Border color for tool call panels.
            tool_output_header_color: Color for the "Tool Output" header.
            tool_output_color: Color for tool output content.
            exec_panel_color: Border color for code action panels.
            exec_output_header_color: Color for the "Code Action Output" header.
            exec_output_color: Color for code execution output.
            image_panel_color: Border color for image output panels.
            approval_color: Color for approval prompts.
            goodbye_color: Color for the goodbye message.
            warning_color: Color for warning messages.
        """
        self._console = console
        self._session: PromptSession[str] = PromptSession(
            multiline=True,
            key_bindings=_create_key_bindings(),
            completer=AtFileCompleter(expanduser=True),
            complete_while_typing=True,
            complete_style=CompleteStyle.COLUMN,
        )

        self.user_header_color = user_header_color
        self.thoughts_header_color = thoughts_header_color
        self.thoughts_color = thoughts_color
        self.response_header_color = response_header_color
        self.response_color = response_color
        self.tool_panel_color = tool_panel_color
        self.tool_output_header_color = tool_output_header_color
        self.tool_output_color = tool_output_color
        self.exec_panel_color = exec_panel_color
        self.exec_output_header_color = exec_output_header_color
        self.exec_output_color = exec_output_color
        self.image_panel_color = image_panel_color
        self.approval_color = approval_color
        self.goodbye_color = goodbye_color
        self.warning_color = warning_color

    # --- Headers ---

    def show_user_header(self) -> None:
        self._console.print(Rule("User", style=self.user_header_color, characters="━"))

    def show_thoughts_header(self, agent_id: str = "") -> None:
        title = f"Thinking \\[{agent_id}]" if agent_id else "Thinking"
        self._console.print(Rule(title, style=self.thoughts_header_color, characters="━"))

    def show_response_header(self, agent_id: str = "") -> None:
        title = f"Response \\[{agent_id}]" if agent_id else "Response"
        self._console.print(Rule(title, style=self.response_header_color, characters="━"))

    def show_tool_output_header(self, agent_id: str = "") -> None:
        title = f"Tool Output \\[{agent_id}]" if agent_id else "Tool Output"
        self._console.print(Rule(title, style=self.tool_output_header_color, characters="━"))

    def show_exec_output_header(self, agent_id: str = "") -> None:
        title = f"Code Action Output \\[{agent_id}]" if agent_id else "Code Action Output"
        self._console.print(Rule(title, style=self.exec_output_header_color, characters="━"))

    # --- Panels ---

    def show_code_action(self, code: str, agent_id: str = "") -> None:
        title = f"Code Action \\[{agent_id}]" if agent_id else "Code Action"
        syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
        panel = Panel(
            syntax,
            title=title,
            title_align="left",
            border_style=self.exec_panel_color,
        )
        self._console.print(panel)

    def show_tool_call(self, tool_name: str, tool_args: dict[str, Any], agent_id: str = "") -> None:
        title = f"Tool: {tool_name} \\[{agent_id}]" if agent_id else f"Tool: {tool_name}"
        args_json = json.dumps(tool_args, indent=2)
        syntax = Syntax(args_json, "json", theme="monokai")
        panel = Panel(
            syntax,
            title=title,
            title_align="left",
            border_style=self.tool_panel_color,
        )
        self._console.print(panel)

    # --- Output display ---

    def print_thoughts_chunk(self, content: str) -> None:
        self._console.print(content, end="", highlight=False, style=self.thoughts_color)

    def print_response_chunk(self, content: str) -> None:
        self._console.print(content, end="", highlight=False, style=self.response_color)

    def show_tool_output(self, content: str) -> None:
        display_content = content[:500] + "..." if len(content) > 500 else content
        self._console.print(Text(display_content, style=self.tool_output_color))
        self._console.print()

    def show_exec_output(self, text: str | None, images: list[Path]) -> None:
        if text:
            rich_text = Text.from_ansi(text, style=self.exec_output_color)
            self._console.print(rich_text)
            self._console.print()

        if images:
            paths_str = "\n".join(str(path) for path in images)
            panel = Panel(
                paths_str,
                title="Produced Images",
                title_align="left",
                border_style=self.image_panel_color,
            )
            self._console.print(panel)
            self._console.print()

    def finalize_thoughts(self) -> None:
        self._console.print()

    def finalize_response(self) -> None:
        self._console.print()

    # --- Utility ---

    def show_approval_newline(self) -> None:
        self._console.print()

    # --- Messages ---

    def show_empty_input_warning(self) -> None:
        self._console.print(Text("Please enter a non-empty message", style=self.warning_color))

    def show_goodbye(self) -> None:
        self._console.print(Text("Goodbye!", style=self.goodbye_color))

    # --- Input ---

    async def get_user_input(self, prompt_prefix: str = "") -> str | None:
        """Prompt for user input with quit detection.

        Args:
            prompt_prefix: Text to display before the prompt indicator.

        Returns:
            User input text, empty string for blank input, or `None` if
                the user entered 'q' to quit.
        """
        hint = _get_newline_key_hint()
        prompt = f"'q': quit, {hint}+Enter: newline\n\n{prompt_prefix}> "

        text = await self._session.prompt_async(prompt)

        if self._console.record:
            self._console.print(prompt, highlight=False, end="")
            self._console.print(text, highlight=False)

        text = text.strip()

        if not text:
            return ""
        if text.lower() == "q":
            return None
        return text

    async def get_approval(self) -> int:
        """Prompt for tool execution approval.

        Accepts Y (yes), n (no), a (always), or s (session) responses.

        Returns:
            Approval level: 0 = reject, 1 = approve once, 2 = always,
                3 = session.
        """
        prompt = "Approve? [Y/n/a/s]: "
        response = await self._session.prompt_async(HTML(f"<b><style fg='ansiyellow'>{prompt}</style></b>"))

        if self._console.record:
            self._console.print(prompt, highlight=False, end="", style=f"bold {self.approval_color}")
            self._console.print(response, highlight=False)

        response = response.strip().lower()

        match response:
            case "a" | "always":
                return 2
            case "s" | "session":
                return 3
            case "n" | "no":
                return 0
            case _:
                return 1
