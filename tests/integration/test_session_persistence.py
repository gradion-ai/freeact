import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_core import to_jsonable_python

from freeact.agent import Agent
from freeact.agent.config import Config
from freeact.agent.config.config import _ConfigPaths
from freeact.agent.store import SessionStore
from tests.conftest import DeltaToolCalls, collect_stream, get_tool_return_parts


def _create_unpatched_config(stream_function, tmp_path: Path) -> Config:
    freeact_dir = _ConfigPaths(tmp_path).freeact_dir
    freeact_dir.mkdir(exist_ok=True)
    (freeact_dir / "agent.json").write_text(json.dumps({"model": "test"}))
    config = Config(working_dir=tmp_path)
    config.model = FunctionModel(stream_function=stream_function)
    config.model_settings = {}
    config.mcp_servers = {}
    return config


@asynccontextmanager
async def unpatched_agent(stream_function, tmp_path: Path, session_store: SessionStore):
    config = _create_unpatched_config(stream_function, tmp_path)
    agent = Agent(config=config, session_store=session_store)
    async with agent:
        yield agent


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

        config = _create_unpatched_config(stream_function, tmp_path)
        session_store = SessionStore(sessions_root=config.sessions_dir, session_id="session-1")
        agent = Agent(config=config, session_store=session_store)

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

        config = _create_unpatched_config(stream_function, tmp_path)
        session_store = SessionStore(sessions_root=config.sessions_dir, session_id="session-1")
        seed_messages = [
            ModelRequest(parts=[UserPromptPart(content="old prompt")]),
            ModelResponse(parts=[]),
        ]
        session_store.append(agent_id="main", messages=seed_messages)
        sub_file = config.sessions_dir / "session-1" / "sub-dead.jsonl"
        sub_file.write_text("{not-json}\n")

        async with unpatched_agent(stream_function, tmp_path, session_store) as agent:
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

        config = _create_unpatched_config(stream_function, tmp_path)
        session_store = SessionStore(sessions_root=config.sessions_dir, session_id="session-1")
        agent = Agent(config=config, session_store=session_store)

        async with agent:
            await collect_stream(agent, "run subagent")

        session_dir = config.sessions_dir / "session-1"
        assert (session_dir / "main.jsonl").exists()
        sub_files = list(session_dir.glob("sub-*.jsonl"))
        assert len(sub_files) >= 1
        assert sub_files[0].read_text().strip() != ""
