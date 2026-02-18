import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from pydantic_ai import UserContent
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Markdown

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
from freeact.terminal.default.screens import FilePickerScreen
from freeact.terminal.default.widgets import (
    ApprovalBar,
    PromptInput,
    create_code_action_box,
    create_diff_box,
    create_exec_output_box,
    create_response_box,
    create_thoughts_box,
    create_tool_call_box,
    create_tool_output_box,
)
from freeact.terminal.legacy.interface import convert_at_references

AgentStreamFn = "Callable[[str | Sequence[UserContent]], AsyncIterator[AgentEvent]]"


class FreeactApp(App[None]):
    """Main Textual application for the freeact terminal interface."""

    DEFAULT_CSS = """
    #conversation {
        height: 1fr;
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
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
    ]

    def __init__(
        self,
        agent_stream: "Callable[[str | Sequence[UserContent]], AsyncIterator[AgentEvent]]",  # type: ignore[name-defined]  # noqa: F821
        permission_manager: PermissionManager | None = None,
        main_agent_id: str = "",
    ) -> None:
        super().__init__()
        self._agent_stream = agent_stream
        self._permission_manager = permission_manager or PermissionManager()
        self._main_agent_id = main_agent_id
        self._approval_future: asyncio.Future[int] | None = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="conversation")
        with Vertical(id="input-dock"):
            yield PromptInput(id="prompt-input")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", PromptInput).focus()

    async def _mount_and_scroll(self, conversation: VerticalScroll, *widgets: "textual.widget.Widget") -> None:  # type: ignore[name-defined]  # noqa: F821
        """Mount widgets into the conversation and scroll to bottom."""
        for widget in widgets:
            await conversation.mount(widget)
        conversation.scroll_end(animate=False)

    # --- Prompt submission ---

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        content = parse_prompt(convert_at_references(event.text))
        self._process_turn(content)

    @work(exclusive=True)
    async def _process_turn(self, content: str | Sequence[UserContent]) -> None:
        prompt_input = self.query_one("#prompt-input", PromptInput)
        conversation = self.query_one("#conversation", VerticalScroll)
        prompt_input.disabled = True
        conversation.anchor()

        thoughts_stream: "Markdown.MarkdownStream | None" = None
        response_stream: "Markdown.MarkdownStream | None" = None
        exec_log = None

        try:
            async for event in self._agent_stream(content):
                match event:
                    case ThoughtsChunk(agent_id=aid, content=chunk) if aid == self._main_agent_id:
                        if thoughts_stream is None:
                            box, md = create_thoughts_box(aid)
                            await self._mount_and_scroll(conversation, box)
                            thoughts_stream = Markdown.get_stream(md)

                        await thoughts_stream.write(chunk)

                    case Thoughts(agent_id=aid) if aid == self._main_agent_id:
                        if thoughts_stream is not None:
                            await thoughts_stream.stop()
                            thoughts_stream = None
                            last_box = conversation.query(".thoughts-box").last()
                            last_box.collapsed = True

                    case ResponseChunk(agent_id=aid, content=chunk) if aid == self._main_agent_id:
                        if response_stream is None:
                            box, md = create_response_box(aid)
                            await self._mount_and_scroll(conversation, box)
                            response_stream = Markdown.get_stream(md)

                        await response_stream.write(chunk)

                    case Response(agent_id=aid) if aid == self._main_agent_id:
                        if response_stream is not None:
                            await response_stream.stop()
                            response_stream = None

                    case ApprovalRequest() as request:
                        await self._handle_approval(request, conversation)

                    case CodeExecutionOutputChunk(agent_id=aid, text=text):
                        if exec_log is None:
                            box, exec_log = create_exec_output_box(aid)
                            await self._mount_and_scroll(conversation, box)
                        exec_log.write(text)

                    case CodeExecutionOutput(agent_id=aid):
                        if exec_log is not None:
                            last_box = conversation.query(".exec-output-box").last()
                            last_box.collapsed = True
                        exec_log = None

                    case ToolOutput(agent_id=aid, content=tool_content):
                        box = create_tool_output_box(str(tool_content), aid)
                        await self._mount_and_scroll(conversation, box)
        finally:
            prompt_input.disabled = False
            prompt_input.focus()

    # --- Approval handling ---

    async def _handle_approval(
        self,
        request: ApprovalRequest,
        conversation: VerticalScroll,
    ) -> None:
        # Mount the appropriate display box
        match request.tool_name:
            case "ipybox_execute_ipython_cell":
                code = request.tool_args.get("code", "")
                box = create_code_action_box(code, agent_id=request.agent_id)
                await self._mount_and_scroll(conversation, box)
            case "filesystem_text_edit":
                box = create_diff_box(request.tool_args, agent_id=request.agent_id)
                await self._mount_and_scroll(conversation, box)
            case _:
                box = create_tool_call_box(
                    request.tool_name,
                    request.tool_args,
                    agent_id=request.agent_id,
                )
                await self._mount_and_scroll(conversation, box)

        # Check if pre-approved
        if self._permission_manager.is_allowed(request.tool_name, request.tool_args):
            box.collapsed = True
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

        match decision:
            case 2:
                await self._permission_manager.allow_always(request.tool_name)
            case 3:
                self._permission_manager.allow_session(request.tool_name)

        request.approve(decision != 0)

    def on_approval_bar_decided(self, event: ApprovalBar.Decided) -> None:
        if self._approval_future is not None and not self._approval_future.done():
            self._approval_future.set_result(event.decision)

    # --- File picker integration ---

    def on_text_area_changed(self, event: "textual.widgets.TextArea.Changed") -> None:  # type: ignore[name-defined]  # noqa: F821
        if event.text_area.id != "prompt-input":
            return
        text = event.text_area.text
        cursor = event.text_area.cursor_location
        row, col = cursor
        lines = text.split("\n")
        if row < len(lines) and col > 0 and col <= len(lines[row]):
            if lines[row][col - 1] == "@":
                self._open_file_picker()

    def _open_file_picker(self) -> None:
        async def handle_result(path: Path | None) -> None:
            if path is not None:
                prompt_input = self.query_one("#prompt-input", PromptInput)
                prompt_input.insert(str(path))

        self.push_screen(FilePickerScreen(), callback=handle_result)
