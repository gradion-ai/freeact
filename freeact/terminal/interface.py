"""Rich-based terminal interface for the freeact agent."""

from collections.abc import Sequence

from pydantic_ai import UserContent
from rich.console import Console

from freeact.agent import (
    Agent,
    ApprovalRequest,
    CodeExecutionOutput,
    Response,
    ResponseChunk,
    Thoughts,
    ThoughtsChunk,
    ToolOutput,
)
from freeact.media import parse_prompt
from freeact.permissions import PermissionManager
from freeact.terminal.display import Display


class Terminal:
    """Interactive terminal interface for conversing with an agent.

    Runs a conversation loop that streams agent events to the terminal,
    handles tool approval prompts, and manages permissions.
    """

    def __init__(
        self,
        agent: Agent,
        console: Console | None = None,
    ):
        """Initialize terminal with an agent.

        Args:
            agent: Agent instance to run conversations with.
            console: Rich Console for output. Creates a new console if
                not provided.
        """
        self._agent = agent
        self._display = Display(console or Console())
        self._permission_manager = PermissionManager()

    async def run(self) -> None:
        """Run the interactive conversation loop until the user quits."""
        await self._permission_manager.load()

        async with self._agent:
            await self._conversation_loop()

    async def _conversation_loop(self) -> None:
        """Main conversation loop handling user input and agent responses."""
        while True:
            self._display.show_user_header()

            user_input = await self._display.get_user_input()

            match user_input:
                case None:
                    self._display.show_goodbye()
                    break
                case "":
                    self._display.show_empty_input_warning()
                    continue
                case prompt:
                    content = parse_prompt(prompt)
                    await self._process_turn(content)

    async def _process_turn(self, prompt: str | Sequence[UserContent]) -> None:
        """Process a single conversation turn."""
        thoughts_header_shown = False
        response_header_shown = False

        async for event in self._agent.stream(prompt):
            match event:
                case ThoughtsChunk(content=content):
                    if not thoughts_header_shown:
                        self._display.show_thoughts_header()
                        thoughts_header_shown = True
                    self._display.print_thoughts_chunk(content)

                case Thoughts():
                    self._display.finalize_thoughts()
                    thoughts_header_shown = False

                case ResponseChunk(content=content):
                    if not response_header_shown:
                        self._display.show_response_header()
                        response_header_shown = True
                    self._display.print_response_chunk(content)

                case Response():
                    self._display.finalize_response()

                case ApprovalRequest() as request:
                    await self._handle_approval(request)

                case CodeExecutionOutput(text=text, images=images):
                    self._display.show_exec_output_header()
                    self._display.show_exec_output(text, images)

                case ToolOutput(content=content):
                    self._display.show_tool_output_header()
                    self._display.show_tool_output(str(content))

    async def _handle_approval(self, request: ApprovalRequest) -> None:
        """Handle tool approval request."""
        # Always display the tool call
        match request.tool_name:
            case "ipybox_execute_ipython_cell":
                code = request.tool_args.get("code", "")
                self._display.show_code_action(code)
            case _:
                self._display.show_tool_call(request.tool_name, request.tool_args)

        # Check if pre-approved
        if self._permission_manager.is_allowed(request.tool_name, request.tool_args):
            self._display.show_approval_newline()
            request.approve(True)
            return

        # Prompt for approval (0=reject, 1=approve, 2=always, 3=session)
        decision = await self._display.get_approval()
        self._display.show_approval_newline()

        match decision:
            case 2:
                await self._permission_manager.allow_always(request.tool_name)
            case 3:
                self._permission_manager.allow_session(request.tool_name)

        request.approve(decision != 0)
