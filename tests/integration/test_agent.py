import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from freeact.agent import CodeActAgent, CodeActAgentTurn, CodeExecution, CodeExecutionResult
from freeact.executor import CodeExecutionContainer, CodeExecutor
from freeact.model.base import CodeActModelResponse, CodeActModelTurn
from freeact.model.claude.model import Claude
from freeact.model.gemini.model.chat import Gemini
from freeact.model.qwen.model import QwenCoder
from tests import TEST_ROOT_PATH
from tests.helpers.flaky import rerun_on_google_genai_resource_exhausted

GEMINI_BACKOFF_WAIT_TIME = 5
GEMINI_BACKOFF_MAX_RETRIES = 10


@pytest.fixture(scope="module")
async def workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        shared_skills_path = Path(temp_dir) / "skills" / "shared" / "user_repository"
        shared_skills_path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            TEST_ROOT_PATH / "helpers" / "skills" / "user_repository", shared_skills_path, dirs_exist_ok=True
        )
        yield temp_dir


@pytest.fixture(scope="module")
async def executor(workspace: str):
    async with CodeExecutionContainer(
        tag="ghcr.io/gradion-ai/ipybox:basic",
        workspace_path=workspace,
        env={
            "PYTHONDONTWRITEBYTECODE": "1"
        },  # Prevent creation of __pycache__ directories created by ipybox root container which cannot be deleted
    ) as container:
        async with CodeExecutor(
            key="test",
            port=container.port,
            workspace=container.workspace,
        ) as executor:
            yield executor


@pytest.fixture(scope="module")
async def skill_sources(executor):
    return await executor.get_module_sources(
        module_names=["user_repository.api"],
    )


@pytest.fixture
def gemini(skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return Gemini(
        model_name="gemini-2.0-flash-exp",
        skill_sources=skill_sources if use_skill_sources else None,
        temperature=0.0,
        max_tokens=1024,
    )


@pytest.fixture
def qwen_coder(qwen_model_name, skill_sources, request):
    use_skill_sources = "skill_sources" in request.node.fixturenames  # check if the test requires skill sources

    return QwenCoder(
        model_name=qwen_model_name,
        skill_sources=skill_sources if use_skill_sources else None,
    )


@pytest.fixture(
    params=[
        pytest.param("claude"),
        pytest.param(
            "gemini",
            marks=pytest.mark.flaky(
                max_runs=GEMINI_BACKOFF_MAX_RETRIES,
                rerun_filter=rerun_on_google_genai_resource_exhausted(GEMINI_BACKOFF_WAIT_TIME),
            ),
        ),
        pytest.param("qwen_coder"),
    ]
)
def agent(request, executor):
    model = request.getfixturevalue(request.param)
    return CodeActAgent(model=model, executor=executor)


def run_agent(agent: CodeActAgent, user_query: str, skill_sources: str | None = None):
    kwargs: dict[str, Any] = {}
    if isinstance(agent.model, Claude):
        kwargs["skill_sources"] = skill_sources

    return agent.run(user_query=user_query, **kwargs)


async def collect_output(agent_turn: CodeActAgentTurn) -> list[CodeActModelResponse | CodeExecutionResult]:
    output: list[CodeActModelResponse | CodeExecutionResult] = []
    async for activity in agent_turn.stream():
        match activity:
            case CodeActModelTurn() as model_turn:
                model_response = await model_turn.response()
                output.append(model_response)

            case CodeExecution() as execution:
                execution_result = await execution.result()
                output.append(execution_result)
    return output


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_returns_text_response(agent):
    agent_turn = run_agent(agent, "Do not generate any code. Just respond with the text 'Hello, world!'")
    output = await collect_output(agent_turn)

    assert len(output) == 1
    assert isinstance(output[0], CodeActModelResponse)
    assert output[0].code is None
    assert output[0].text.strip() == "Hello, world!"


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_returns_code_response(agent):
    agent_turn = run_agent(
        agent, "What is 25 raised to the power of 0.235? Use the math library to solve this problem."
    )
    output = await collect_output(agent_turn)

    assert len(output) == 3
    assert isinstance(output[0], CodeActModelResponse)
    assert output[0].code is not None

    assert isinstance(output[1], CodeExecutionResult)
    assert output[1].is_error is False

    assert isinstance(output[2], CodeActModelResponse)
    assert output[2].code is None

    response = await agent_turn.response()
    assert "2.13" in response.text


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_returns_follow_up_code_response(agent):
    agent_turn_1 = run_agent(
        agent, "What is 25 raised to the power of 0.235? Use the math library to solve this problem."
    )
    await collect_output(agent_turn_1)

    response_1 = await agent_turn_1.response()
    assert "2.13" in response_1.text

    agent_turn_2 = run_agent(agent, "What is the square root of the result?")
    output = await collect_output(agent_turn_2)

    assert len(output) == 3
    assert isinstance(output[0], CodeActModelResponse)
    assert output[0].code is not None

    assert isinstance(output[1], CodeExecutionResult)
    assert output[1].is_error is False

    assert isinstance(output[2], CodeActModelResponse)
    assert output[2].code is None

    response_2 = await agent_turn_2.response()
    assert "1.45" in response_2.text


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_returns_follow_up_text_response(agent):
    agent_turn_1 = run_agent(
        agent, "What is 25 raised to the power of 0.235? Use the math library to solve this problem."
    )
    await collect_output(agent_turn_1)

    response_1 = await agent_turn_1.response()
    assert "2.13" in response_1.text

    agent_turn_2 = run_agent(agent, "Reply with the result again. Do not generate any code for this.")
    output = await collect_output(agent_turn_2)

    assert len(output) == 1
    assert isinstance(output[0], CodeActModelResponse)
    assert output[0].code is None

    response_2 = await agent_turn_2.response()
    assert "2.13" in response_2.text


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_uses_provided_skills(agent, skill_sources):
    agent_turn = run_agent(
        agent,
        "What is the name of the user with id 'user-123' in the user repository?",
        skill_sources=skill_sources,
    )
    await collect_output(agent_turn)

    response = await agent_turn.response()
    assert "user_a37c1f54" in response.text


@pytest.mark.asyncio(loop_scope="module")
async def test_agent_recovers_from_skill_error(agent, skill_sources):
    agent_turn = run_agent(
        agent,
        "What is the email address of the user with id 'user-123' in the user repository?",
        skill_sources=skill_sources,
    )
    output = await collect_output(agent_turn)

    code_exection_result = next(o for o in output if isinstance(o, CodeExecutionResult))
    assert code_exection_result.is_error is True

    response = await agent_turn.response()
    assert "user.a37c1f54@mytestdomain.com" in response.text
