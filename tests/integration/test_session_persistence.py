import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import ipybox
import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo
from pydantic_core import to_jsonable_python

from freeact.agent import SessionStore
from tests.helpers import (
    FakeCodeExecutor,
    collect_stream,
    create_stream_function,
    create_task_stream_function,
    patched_agent,
    unpatched_agent,
)


def _sessions_dir(working_dir: Path) -> Path:
    return working_dir / ".freeact" / "sessions"


@pytest.mark.asyncio
async def test_agent_persists_incrementally_at_all_history_points(tmp_path: Path) -> None:
    stream_function = create_stream_function(tool_name="nonexistent_tool", tool_args={"arg": "value"})

    async with patched_agent(stream_function, tmp_dir=tmp_path, session_id="session-1") as agent:
        await collect_stream(agent, "persist this turn")

    session_file = _sessions_dir(tmp_path) / "session-1" / "main.jsonl"
    lines = [json.loads(line) for line in session_file.read_text().splitlines()]
    assert len(lines) == 4
    assert all("agent_id" not in line["meta"] for line in lines)


@pytest.mark.asyncio
async def test_resume_loads_only_main_history(tmp_path: Path) -> None:
    captured: dict[str, list[ModelMessage]] = {}

    async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
        captured["messages"] = messages
        yield "Resumed"

    session_store = SessionStore(sessions_root=_sessions_dir(tmp_path), session_id="session-1")
    seed_messages: list[ModelMessage] = [
        ModelRequest(parts=[UserPromptPart(content="old prompt")]),
        ModelResponse(parts=[]),
    ]
    session_store.append_messages(agent_id="main", messages=seed_messages)
    sub_file = _sessions_dir(tmp_path) / "session-1" / "sub-dead.jsonl"
    sub_file.write_text("{not-json}\n")

    async with patched_agent(stream_function, tmp_dir=tmp_path, session_id="session-1") as agent:
        await collect_stream(agent, "new prompt")

    assert "messages" in captured
    serialized_first = to_jsonable_python(captured["messages"][0], bytes_mode="base64")
    assert serialized_first == to_jsonable_python(seed_messages[0], bytes_mode="base64")
    match captured["messages"][-1]:
        case ModelRequest(parts=parts):
            assert len(parts) == 1
            assert isinstance(parts[0], UserPromptPart)
        case _:
            pytest.fail("Expected final item in model input to be ModelRequest")


@pytest.mark.asyncio
async def test_subagent_trace_written_to_subagent_file(tmp_path: Path) -> None:
    async with unpatched_agent(create_task_stream_function(), tmp_dir=tmp_path, session_id="session-1") as agent:
        await collect_stream(agent, "run subagent")

    session_dir = _sessions_dir(tmp_path) / "session-1"
    assert (session_dir / "main.jsonl").exists()
    sub_files = list(session_dir.glob("sub-*.jsonl"))
    assert len(sub_files) >= 1
    assert sub_files[0].read_text().strip() != ""


@pytest.mark.asyncio
async def test_large_tool_result_is_persisted_in_tool_results_directory(
    tmp_path: Path,
    stored_path_from_notice: Callable[[str, Path], Path],
    collect_tool_return_parts: Callable[[list[ModelMessage]], list[ToolReturnPart]],
) -> None:
    stream_function = create_stream_function(
        tool_name="ipybox_execute_ipython_cell",
        tool_args={"code": "print('large')"},
    )

    async def script(code: str) -> AsyncIterator[Any]:
        yield ipybox.CodeExecutionResult(text="line-1\nline-2\nline-3\n" + ("x" * 300), images=[])

    async with patched_agent(
        stream_function,
        FakeCodeExecutor(script=script),
        tmp_dir=tmp_path,
        session_id="session-1",
        tool_result_inline_max_bytes=32,
        tool_result_preview_chars=100,
    ) as agent:
        await collect_stream(agent, "persist large tool output")

    session_store = SessionStore(sessions_root=_sessions_dir(tmp_path), session_id="session-1")
    history = session_store.load_messages(agent_id="main")
    tool_returns = collect_tool_return_parts(history)
    assert len(tool_returns) == 1
    assert isinstance(tool_returns[0].content, str)
    notice = tool_returns[0].content
    assert "configured inline threshold (32 bytes)" in notice
    assert "Preview (~100 characters):" in notice

    stored_path = stored_path_from_notice(notice, tmp_path)
    assert stored_path.exists()
    assert stored_path.suffix == ".txt"
    assert stored_path.parent.name == "tool-results"
