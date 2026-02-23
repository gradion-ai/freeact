import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall
from pydantic_core import to_jsonable_python

from freeact.agent import Agent, CodeExecutionOutput
from freeact.agent.store import SessionStore
from tests.helpers import DeltaToolCalls, collect_stream, create_test_config, get_tool_return_parts, unpatched_agent


class TestSessionPersistence:
    @pytest.mark.asyncio
    async def test_agent_persists_incrementally_at_all_history_points(self, tmp_path: Path):
        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            if get_tool_return_parts(messages):
                yield "Done"
            else:
                yield {
                    0: DeltaToolCall(
                        name="nonexistent_tool",
                        json_args=json.dumps({"arg": "value"}),
                        tool_call_id="call_unknown",
                    )
                }

        config = create_test_config(tmp_dir=tmp_path, stream_function=stream_function)
        agent = Agent(config=config, session_id="session-1")

        async with agent:
            await collect_stream(agent, "persist this turn")

        session_file = config.sessions_dir / "session-1" / "main.jsonl"
        lines = [json.loads(line) for line in session_file.read_text().splitlines()]
        assert len(lines) == 4
        assert all("agent_id" not in line["meta"] for line in lines)

    @pytest.mark.asyncio
    async def test_resume_loads_only_main_history(self, tmp_path: Path):
        captured: dict[str, list[ModelMessage]] = {}

        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str]:
            captured["messages"] = messages
            yield "Resumed"

        config = create_test_config(tmp_dir=tmp_path, stream_function=stream_function)
        session_store = SessionStore(sessions_root=config.sessions_dir, session_id="session-1")
        seed_messages = [
            ModelRequest(parts=[UserPromptPart(content="old prompt")]),
            ModelResponse(parts=[]),
        ]
        session_store.append_messages(agent_id="main", messages=seed_messages)
        sub_file = config.sessions_dir / "session-1" / "sub-dead.jsonl"
        sub_file.write_text("{not-json}\n")

        async with unpatched_agent(stream_function, tmp_dir=tmp_path, session_id="session-1") as agent:
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
    async def test_subagent_trace_written_to_subagent_file(self, tmp_path: Path):
        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            tool_names = [tool.name for tool in info.function_tools]
            if get_tool_return_parts(messages):
                yield "Parent done"
            elif "subagent_task" in tool_names:
                yield {
                    0: DeltaToolCall(
                        name="subagent_task",
                        json_args=json.dumps({"prompt": "Subtask"}),
                        tool_call_id="call_task",
                    )
                }
            else:
                yield "Subagent response"

        config = create_test_config(tmp_dir=tmp_path, stream_function=stream_function)
        agent = Agent(config=config, session_id="session-1")

        async with agent:
            await collect_stream(agent, "run subagent")

        session_dir = config.sessions_dir / "session-1"
        assert (session_dir / "main.jsonl").exists()
        sub_files = list(session_dir.glob("sub-*.jsonl"))
        assert len(sub_files) >= 1
        assert sub_files[0].read_text().strip() != ""

    @pytest.mark.asyncio
    async def test_large_tool_result_is_persisted_in_tool_results_directory(self, tmp_path: Path):
        async def stream_function(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
            if get_tool_return_parts(messages):
                yield "Done"
            else:
                yield {
                    0: DeltaToolCall(
                        name="ipybox_execute_ipython_cell",
                        json_args=json.dumps({"code": "print('large')"}),
                        tool_call_id="call_code",
                    )
                }

        config = create_test_config(
            tmp_dir=tmp_path,
            stream_function=stream_function,
            tool_result_inline_max_bytes=32,
            tool_result_preview_lines=2,
        )
        agent = Agent(config=config, session_id="session-1")

        async def large_code_output(code: str):
            _ = code
            yield CodeExecutionOutput(text="line-1\nline-2\nline-3\n" + ("x" * 300), images=[])

        agent._ipybox_execute_ipython_cell = large_code_output  # type: ignore[method-assign]

        async with agent:
            await collect_stream(agent, "persist large tool output")

        session_store = SessionStore(sessions_root=config.sessions_dir, session_id="session-1")
        history = session_store.load_messages(agent_id="main")
        tool_returns = [
            part
            for message in history
            for part in (message.parts if isinstance(message, ModelRequest) else [])
            if isinstance(part, ToolReturnPart)
        ]
        assert len(tool_returns) == 1
        assert isinstance(tool_returns[0].content, str)
        notice = tool_returns[0].content
        assert "configured inline threshold (32 bytes)" in notice
        assert "Preview (first and last 2 lines):" in notice

        match = re.search(r"^Full content saved to: (.+)$", notice, flags=re.MULTILINE)
        assert match is not None
        stored_path = tmp_path / match.group(1)
        assert stored_path.exists()
        assert stored_path.suffix == ".txt"
        assert stored_path.parent.name == "tool-results"
