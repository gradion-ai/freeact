import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from freeact import (
    CodeActAgent,
    CodeActAgentTurn,
    CodeActModelResponse,
    CodeActModelTurn,
    CodeExecution,
    CodeExecutionContainer,
    CodeExecutionResult,
    CodeExecutor,
    CodeProvider,
)
from tests import TEST_ROOT_PATH


@pytest_asyncio.fixture
async def workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        shared_skills_path = Path(temp_dir) / "skills" / "shared" / "user_repository"
        shared_skills_path.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            TEST_ROOT_PATH / "helpers" / "skills" / "user_repository", shared_skills_path, dirs_exist_ok=True
        )
        yield temp_dir


@pytest_asyncio.fixture
async def container(workspace: str):
    async with CodeExecutionContainer(
        tag="ghcr.io/gradion-ai/ipybox:basic",
        workspace_path=workspace,
        workspace_key="test",
        env={
            "PYTHONDONTWRITEBYTECODE": "1"
        },  # Prevent creation of __pycache__ directories created by ipybox root container which cannot be deleted
    ) as container:
        yield container


@pytest_asyncio.fixture
async def executor(container):
    async with CodeExecutor(
        workspace=container.workspace,
        port=container.executor_port,
    ) as executor:
        yield executor


@pytest_asyncio.fixture
async def skill_sources(container):
    async with CodeProvider(
        workspace=container.workspace,
        port=container.resource_port,
    ) as provider:
        return await provider.get_sources(
            module_names=["user_repository.api"],
        )


@pytest.fixture(
    params=[
        pytest.param("claude"),
        pytest.param("gemini"),
        pytest.param("qwen"),
    ]
)
def agent(request, executor):
    model = request.getfixturevalue(request.param)
    return CodeActAgent(model=model, executor=executor)


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


@pytest.mark.asyncio(loop_scope="package")
async def test_agent_returns_text_response(agent):
    agent_turn = agent.run(user_query="Do not generate any code. Just respond with the text 'Hello, world!'")
    output = await collect_output(agent_turn)

    assert len(output) == 1
    assert isinstance(output[0], CodeActModelResponse)
    assert output[0].code is None
    assert output[0].text.strip() == "Hello, world!"


@pytest.mark.asyncio(loop_scope="package")
async def test_agent_returns_code_response(agent):
    agent_turn = agent.run(
        user_query="What is 25 raised to the power of 0.235? Use the math library to solve this problem."
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


@pytest.mark.asyncio(loop_scope="package")
async def test_agent_returns_follow_up_code_response(agent):
    agent_turn_1 = agent.run(
        user_query="What is 25 raised to the power of 0.235? Use the math library to solve this problem and print with 6 digits precision.",
    )
    await collect_output(agent_turn_1)

    response_1 = await agent_turn_1.response()
    assert "2.13" in response_1.text

    agent_turn_2 = agent.run(user_query="What is the square root of the result? Print with 6 digits precision.")
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


@pytest.mark.asyncio(loop_scope="package")
async def test_agent_returns_follow_up_text_response(agent):
    agent_turn_1 = agent.run(
        user_query="What is 25 raised to the power of 0.235? Use the math library to solve this problem."
    )
    await collect_output(agent_turn_1)

    response_1 = await agent_turn_1.response()
    assert "2.13" in response_1.text

    agent_turn_2 = agent.run(
        user_query="Show the numerical result again enclosed on backticks. Do not generate any code for this."
    )
    output = await collect_output(agent_turn_2)

    assert len(output) == 1
    assert isinstance(output[0], CodeActModelResponse)
    assert output[0].code is None

    response_2 = await agent_turn_2.response()
    assert "2.13" in response_2.text


@pytest.mark.asyncio(loop_scope="package")
async def test_agent_uses_provided_skills(agent, skill_sources):
    agent_turn = agent.run(
        user_query="What is the name of the user with id 'user-123' in the user repository?",
    )
    await collect_output(agent_turn)

    response = await agent_turn.response()
    assert "user_a37c1f54" in response.text


@pytest.mark.asyncio(loop_scope="package")
async def test_agent_recovers_from_skill_error(agent, skill_sources):
    agent_turn = agent.run(
        user_query="What is the email address of the user with id 'user-123' in the user repository?",
    )
    output = await collect_output(agent_turn)

    code_exection_result = next(o for o in output if isinstance(o, CodeExecutionResult))
    assert code_exection_result.is_error is True

    response = await agent_turn.response()
    assert "user.a37c1f54@mytestdomain.com" in response.text
