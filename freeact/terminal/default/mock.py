import asyncio
from collections.abc import AsyncIterator, Sequence

from pydantic_ai import UserContent

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

MOCK_AGENT_ID = "mock-agent"

_THINKING_TEXT = """\
Let me analyze the user's request. I need to consider the best approach \
to solve this problem. I'll break it down into steps and implement a solution.\
"""

_RESPONSE_TEXT = """\
Here's my analysis of the problem:

1. **First step**: Identify the key components
2. **Second step**: Implement the solution
3. **Third step**: Verify correctness

Let me write some code to implement this.\
"""

_CODE_ACTION = """\
import os
from pathlib import Path

def process_data(input_path: str) -> dict:
    \"\"\"Process data from the given path.\"\"\"
    path = Path(input_path)
    results = {}
    for file in path.glob("*.txt"):
        with open(file) as f:
            results[file.name] = len(f.readlines())
    return results

result = process_data("/tmp/data")
print(result)
"""

_EXEC_OUTPUT_LINES = [
    "Processing files...\n",
    "Found 3 files\n",
    "  data_01.txt: 42 lines\n",
    "  data_02.txt: 18 lines\n",
    "  data_03.txt: 95 lines\n",
    "Done.\n",
]

_FINAL_RESPONSE = """\
The code processed 3 files successfully:
- `data_01.txt`: 42 lines
- `data_02.txt`: 18 lines
- `data_03.txt`: 95 lines

Total: **155 lines** across all files.\
"""

_TOOL_ARGS_JSON = {
    "query": "SELECT count(*) FROM users WHERE active = true",
    "database": "production",
    "timeout": 30,
}

_FILESYSTEM_READ_ARGS = {
    "path": ".freeact/permissions.json",
}

_DIFF_TOOL_ARGS = {
    "path": "src/config.py",
    "old_text": "DEBUG = True\nLOG_LEVEL = 'verbose'",
    "new_text": "DEBUG = False\nLOG_LEVEL = 'warning'",
}

_LONG_OUTPUT_LINES = [f"Line {i:04d}: Processing batch item {i} of 200...\n" for i in range(1, 201)]


async def _stream_text(text: str, delay: float = 0.03) -> AsyncIterator[str]:
    """Yield text in small chunks with realistic delays."""
    words = text.split(" ")
    for i, word in enumerate(words):
        chunk = word if i == 0 else f" {word}"
        yield chunk
        await asyncio.sleep(delay)


class MockAgent:
    """Mock agent that yields realistic event sequences for UI testing.

    Each turn (based on `_turn_count`) runs a different scenario.
    """

    def __init__(self) -> None:
        self._turn_count = 0

    async def stream(self, prompt: str | Sequence[UserContent]) -> AsyncIterator[AgentEvent]:
        self._turn_count += 1

        match self._turn_count % 5:
            case 1:
                async for event in self._scenario_code_action():
                    yield event
            case 2:
                async for event in self._scenario_tool_call():
                    yield event
            case 3:
                async for event in self._scenario_pre_approved():
                    yield event
            case 4:
                async for event in self._scenario_diff():
                    yield event
            case 0:
                async for event in self._scenario_long_output():
                    yield event

    async def _scenario_code_action(self) -> AsyncIterator[AgentEvent]:
        """Thinking -> Response -> Code Action (approval) -> Exec Output -> Final Response."""
        # Thinking
        async for chunk in _stream_text(_THINKING_TEXT):
            yield ThoughtsChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Thoughts(content=_THINKING_TEXT, agent_id=MOCK_AGENT_ID)

        # Response
        async for chunk in _stream_text(_RESPONSE_TEXT):
            yield ResponseChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Response(content=_RESPONSE_TEXT, agent_id=MOCK_AGENT_ID)

        # Code action (needs approval)
        request = ApprovalRequest(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": _CODE_ACTION},
            agent_id=MOCK_AGENT_ID,
        )
        yield request
        approved = await request.approved()
        if not approved:
            return

        # Execution output
        for line in _EXEC_OUTPUT_LINES:
            yield CodeExecutionOutputChunk(text=line, agent_id=MOCK_AGENT_ID)
            await asyncio.sleep(0.05)
        yield CodeExecutionOutput(text="".join(_EXEC_OUTPUT_LINES), images=[], agent_id=MOCK_AGENT_ID)

        # Final response
        async for chunk in _stream_text(_FINAL_RESPONSE):
            yield ResponseChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Response(content=_FINAL_RESPONSE, agent_id=MOCK_AGENT_ID)

    async def _scenario_tool_call(self) -> AsyncIterator[AgentEvent]:
        """Tool call with JSON args (approval needed)."""
        async for chunk in _stream_text("I need to query the database to get user counts."):
            yield ThoughtsChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Thoughts(content="I need to query the database to get user counts.", agent_id=MOCK_AGENT_ID)

        request = ApprovalRequest(
            tool_name="database_query",
            tool_args=_TOOL_ARGS_JSON,
            agent_id=MOCK_AGENT_ID,
        )
        yield request
        approved = await request.approved()
        if not approved:
            yield ResponseChunk(content="Tool call was rejected.", agent_id=MOCK_AGENT_ID)
            yield Response(content="Tool call was rejected.", agent_id=MOCK_AGENT_ID)
            return

        yield ToolOutput(content="Result: 1,247 active users", agent_id=MOCK_AGENT_ID)  # type: ignore[arg-type]

        async for chunk in _stream_text("The database shows **1,247 active users**."):
            yield ResponseChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Response(content="The database shows **1,247 active users**.", agent_id=MOCK_AGENT_ID)

    async def _scenario_pre_approved(self) -> AsyncIterator[AgentEvent]:
        """Pre-approved filesystem tool (within .freeact/) -> collapsed box, no prompt."""
        async for chunk in _stream_text("Let me check the current permissions."):
            yield ThoughtsChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Thoughts(content="Let me check the current permissions.", agent_id=MOCK_AGENT_ID)

        request = ApprovalRequest(
            tool_name="filesystem_read_file",
            tool_args=_FILESYSTEM_READ_ARGS,
            agent_id=MOCK_AGENT_ID,
        )
        yield request
        await request.approved()

        yield ToolOutput(  # type: ignore[arg-type]
            content='{"allowed_tools": ["ipybox_execute_ipython_cell"]}',
            agent_id=MOCK_AGENT_ID,
        )

        async for chunk in _stream_text("The permissions file shows one tool is always approved."):
            yield ResponseChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Response(
            content="The permissions file shows one tool is always approved.",
            agent_id=MOCK_AGENT_ID,
        )

    async def _scenario_diff(self) -> AsyncIterator[AgentEvent]:
        """filesystem_text_edit with diff display."""
        async for chunk in _stream_text("I'll update the configuration to disable debug mode."):
            yield ThoughtsChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Thoughts(
            content="I'll update the configuration to disable debug mode.",
            agent_id=MOCK_AGENT_ID,
        )

        request = ApprovalRequest(
            tool_name="filesystem_text_edit",
            tool_args=_DIFF_TOOL_ARGS,
            agent_id=MOCK_AGENT_ID,
        )
        yield request
        approved = await request.approved()
        if not approved:
            yield ResponseChunk(content="Edit was rejected.", agent_id=MOCK_AGENT_ID)
            yield Response(content="Edit was rejected.", agent_id=MOCK_AGENT_ID)
            return

        yield ToolOutput(content="File updated successfully.", agent_id=MOCK_AGENT_ID)  # type: ignore[arg-type]

        async for chunk in _stream_text("Configuration updated: debug mode disabled, log level set to warning."):
            yield ResponseChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Response(
            content="Configuration updated: debug mode disabled, log level set to warning.",
            agent_id=MOCK_AGENT_ID,
        )

    async def _scenario_long_output(self) -> AsyncIterator[AgentEvent]:
        """Long streaming output to test scroll behavior."""
        async for chunk in _stream_text("Running a batch processing job with 200 items."):
            yield ThoughtsChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Thoughts(
            content="Running a batch processing job with 200 items.",
            agent_id=MOCK_AGENT_ID,
        )

        request = ApprovalRequest(
            tool_name="ipybox_execute_ipython_cell",
            tool_args={"code": "for i in range(1, 201):\n    print(f'Processing batch item {i} of 200...')"},
            agent_id=MOCK_AGENT_ID,
        )
        yield request
        approved = await request.approved()
        if not approved:
            return

        for line in _LONG_OUTPUT_LINES:
            yield CodeExecutionOutputChunk(text=line, agent_id=MOCK_AGENT_ID)
            await asyncio.sleep(0.02)
        yield CodeExecutionOutput(
            text="".join(_LONG_OUTPUT_LINES),
            images=[],
            agent_id=MOCK_AGENT_ID,
        )

        async for chunk in _stream_text("Batch processing complete: all 200 items processed successfully."):
            yield ResponseChunk(content=chunk, agent_id=MOCK_AGENT_ID)
        yield Response(
            content="Batch processing complete: all 200 items processed successfully.",
            agent_id=MOCK_AGENT_ID,
        )


def run_demo() -> None:
    """Run the mock demo application."""
    from freeact.terminal.default.app import FreeactApp

    agent = MockAgent()
    app = FreeactApp(agent_stream=agent.stream, main_agent_id=MOCK_AGENT_ID)
    app.run()


if __name__ == "__main__":
    run_demo()
