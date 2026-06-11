# Covers behavior-inventory.md sections: 20 (terminal UI test harness)
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, TypeVar

from textual.app import App
from textual.pilot import Pilot
from textual.screen import Screen

from freeact.config import SkillMetadata, TerminalSection
from freeact.events import AgentEvent, ApprovalRequest, Response, ToolOutput
from freeact.terminal.app import TerminalApp
from freeact.terminal.widgets import PromptInput
from freeact.toolcalls import CodeAction, GenericCall, ToolCall

MAIN_AGENT_ID = "main-agent"

ScenarioFn = Callable[[str], AsyncIterator[AgentEvent]]

ScreenT = TypeVar("ScreenT", bound=Screen[Any])


class MockStreamAgent:
    """Deterministic agent stream helper for Textual app tests."""

    def __init__(self, scenario: ScenarioFn) -> None:
        self._scenario = scenario
        self.prompts: list[str] = []

    async def stream(self, content: str) -> AsyncIterator[AgentEvent]:
        self.prompts.append(content)
        async for event in self._scenario(content):
            yield event


class StubPermissionManager:
    """Permission manager stub with configurable pre-approval behavior."""

    def __init__(self, preapproved: bool = False) -> None:
        self._preapproved = preapproved
        self.allow_always_calls: list[ToolCall] = []
        self.allow_session_calls: list[ToolCall] = []

    def is_allowed(self, tool_call: ToolCall) -> bool:
        return self._preapproved

    def allow_always(self, tool_call: ToolCall) -> None:
        self.allow_always_calls.append(tool_call)

    def allow_session(self, tool_call: ToolCall) -> None:
        self.allow_session_calls.append(tool_call)


class StubClipboardAdapter:
    """Clipboard adapter stub with programmable paste responses."""

    def __init__(self, paste_values: list[str | None] | None = None) -> None:
        self.copy_calls: list[str] = []
        self.paste_calls = 0
        self._paste_values = paste_values or []

    def copy(self, text: str) -> bool:
        self.copy_calls.append(text)
        return True

    def paste(self) -> str | None:
        self.paste_calls += 1
        if self._paste_values:
            return self._paste_values.pop(0)
        return None


async def no_events(_: str) -> AsyncIterator[AgentEvent]:
    if False:
        yield Response(content="", agent_id=MAIN_AGENT_ID)


def approval_request(
    tool_call: ToolCall,
    corr_id: str,
    agent_id: str = MAIN_AGENT_ID,
    parent_corr_id: str = "",
) -> ApprovalRequest:
    return ApprovalRequest(
        tool_call=tool_call,
        agent_id=agent_id,
        corr_id=corr_id,
        parent_corr_id=parent_corr_id,
    )


def db_query_call() -> GenericCall:
    return GenericCall(tool_name="database_query", tool_args={"query": "SELECT 1"}, ptc=False)


def code_action_call(code: str = "print('ok')") -> CodeAction:
    return CodeAction(tool_name="ipybox_execute_ipython_cell", code=code)


def approval_scenario(tool_call: ToolCall, output: str | None = None, corr_id: str = "call-1") -> ScenarioFn:
    """Scenario yielding a single approval request, then optionally a tool output if approved."""

    async def scenario(_: str) -> AsyncIterator[AgentEvent]:
        request = approval_request(tool_call, corr_id)
        yield request
        if await request.approved() and output is not None:
            yield ToolOutput(content=output, agent_id=MAIN_AGENT_ID, corr_id=corr_id)

    return scenario


async def submit_prompt(app: TerminalApp, pilot: Pilot[Any], text: str = "hello") -> None:
    prompt = app.query_one("#prompt-input", PromptInput)
    prompt.insert(text)
    await pilot.press("enter")


def create_app(
    agent_stream: ScenarioFn,
    *,
    config: TerminalSection | None = None,
    cancel_fn: Callable[[], None] | None = None,
    permission_manager: StubPermissionManager | None = None,
    clipboard_adapter: StubClipboardAdapter | None = None,
    skills_metadata: list[SkillMetadata] | None = None,
    skip_permissions: bool = False,
    working_dir: Path | None = None,
) -> TerminalApp:
    return TerminalApp(
        agent_id=MAIN_AGENT_ID,
        stream=agent_stream,
        cancel=cancel_fn or (lambda: None),
        skills_metadata=skills_metadata or [],
        terminal_config=config or TerminalSection(),
        permissions=permission_manager or StubPermissionManager(),  # type: ignore[arg-type]
        skip_permissions=skip_permissions,
        working_dir=working_dir or Path.cwd(),
        clipboard_adapter=clipboard_adapter,
    )


def make_skill(name: str, description: str = "A skill") -> SkillMetadata:
    return SkillMetadata(name=name, description=description, path=Path(name) / "SKILL.md")


def find_screen(app: App[Any], screen_type: type[ScreenT]) -> ScreenT:
    screen = next((s for s in app.screen_stack if isinstance(s, screen_type)), None)
    assert screen is not None, f"no {screen_type.__name__} on screen stack"
    return screen
