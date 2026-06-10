from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from textual.widgets import Markdown

from freeact.config import TerminalSection
from freeact.events import AgentEvent, Response, ResponseChunk
from freeact.permissions import PermissionManager
from freeact.terminal import PromptInput, TerminalApp


def create_app(tmp_path: Path) -> TerminalApp:
    async def stream(prompt: str) -> AsyncIterator[AgentEvent]:
        yield ResponseChunk(content="Hello ", agent_id="main")
        yield ResponseChunk(content="world", agent_id="main")
        yield Response(content="Hello world", agent_id="main")

    return TerminalApp(
        agent_id="main",
        stream=stream,
        cancel=lambda: None,
        skills_metadata=[],
        terminal_config=TerminalSection(),
        permissions=PermissionManager(working_dir=tmp_path, freeact_dir=tmp_path / ".freeact"),
        skip_permissions=False,
        working_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_submit_prompt_renders_response_and_reenables_input(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    async with app.run_test() as pilot:
        prompt_input = app.query_one("#prompt-input", PromptInput)
        prompt_input.insert("hi there")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

        response_markdown = app.query_one(".response-box Markdown", Markdown)
        assert "Hello world" in response_markdown.source
        assert not prompt_input.disabled
        assert prompt_input.text == ""
