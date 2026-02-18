"""Rich-based terminal interface for the freeact agent."""

import re
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
from freeact.terminal.legacy.display import Display

_AT_FILE_PATTERN = re.compile(r"@(\S+)")


def convert_at_references(text: str) -> str:
    """Convert `@path` references to `<attachment>...</attachment>` XML tags.

    Args:
        text: User input text with `@path` references.

    Returns:
        Text with `@path` references replaced by `<attachment>path</attachment>` tags.
    """
    return _AT_FILE_PATTERN.sub(r"<attachment>\1</attachment>", text)


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
        self._main_agent_id = agent.agent_id
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
                    content = parse_prompt(convert_at_references(prompt))
                    await self._process_turn(content)

    async def _process_turn(self, prompt: str | Sequence[UserContent]) -> None:
        """Process a single conversation turn."""
        thoughts_agent_id = ""
        response_agent_id = ""

        async for event in self._agent.stream(prompt):
            match event:
                case ThoughtsChunk(agent_id=aid, content=content) if aid == self._main_agent_id:
                    if thoughts_agent_id != aid:
                        self._display.show_thoughts_header(aid)
                        thoughts_agent_id = aid
                    self._display.print_thoughts_chunk(content)

                case Thoughts(agent_id=aid) if aid == self._main_agent_id:
                    self._display.finalize_thoughts()
                    thoughts_agent_id = ""

                case ResponseChunk(agent_id=aid, content=content) if aid == self._main_agent_id:
                    if response_agent_id != aid:
                        self._display.show_response_header(aid)
                        response_agent_id = aid
                    self._display.print_response_chunk(content)

                case Response(agent_id=aid) if aid == self._main_agent_id:
                    self._display.finalize_response()
                    response_agent_id = ""

                case ApprovalRequest() as request:
                    await self._handle_approval(request)

                case CodeExecutionOutput(agent_id=aid, text=text, images=images):  # if aid == self._main_agent_id:
                    self._display.show_exec_output_header(aid)
                    self._display.show_exec_output(text, images)

                case ToolOutput(agent_id=aid, content=content):  # if aid == self._main_agent_id:
                    self._display.show_tool_output_header(aid)
                    self._display.show_tool_output(str(content))

    async def _handle_approval(self, request: ApprovalRequest) -> None:
        """Handle tool approval request."""
        # Always display the tool call
        match request.tool_name:
            case "ipybox_execute_ipython_cell":
                code = request.tool_args.get("code", "")
                self._display.show_code_action(code, agent_id=request.agent_id)
            case _:
                self._display.show_tool_call(request.tool_name, request.tool_args, agent_id=request.agent_id)

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
