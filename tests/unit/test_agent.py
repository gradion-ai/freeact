from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from ipybox import Execution, ExecutionError

from freeact.agent import CodeActAgent, CodeAction, MaxStepsReached
from tests.unit.test_model import MockModel, MockModelResponse, MockModelTurn


@pytest.fixture
def mock_executor():
    executor = Mock()
    executor.working_dir = Path("/tmp/mock_skills/123")
    executor.images_dir = Path("/tmp")
    executor.workspace = Mock()
    executor.workspace.shared_skills_path = Path("/tmp/mock_skills")
    return executor


@pytest.mark.asyncio
async def test_simple_conversation_no_code(mock_executor):
    """Test a simple conversation where the model just responds with text."""
    model = MockModel([MockModelResponse(text="Hello! I can help you.", code=None)])
    agent = CodeActAgent(model, mock_executor)

    turn = agent.run("Hi there!")
    response = await turn.response()
    assert response.text == "Hello! I can help you."


@pytest.mark.asyncio
async def test_code_execution_success(mock_executor):
    """Test successful code execution flow."""
    model = MockModel(
        [
            MockModelResponse(text="Let me help", code="print('hello')", tool_use_id="123", tool_use_name="python"),
            MockModelResponse(text="All done!", code=None),
        ]
    )

    async def mock_stream(timeout):
        yield "hello\n"

    mock_execution = AsyncMock(spec=Execution)
    mock_execution.stream = mock_stream
    mock_execution.result.return_value = Mock(text="hello\n", images=[])

    mock_executor.submit = AsyncMock(return_value=mock_execution)

    agent = CodeActAgent(model, mock_executor)
    turn = agent.run("Run some code")

    responses = []
    async for item in turn.stream():
        responses.append(item)

    assert len(responses) == 3  # Initial ModelTurn, CodeAct, and final ModelTurn
    assert isinstance(responses[0], MockModelTurn)  # Initial response
    assert isinstance(responses[1], CodeAction)  # Code execution
    assert isinstance(responses[2], MockModelTurn)  # Final "All done!" response

    response = await turn.response()
    assert response.text == "All done!"


@pytest.mark.asyncio
async def test_max_iterations_reached(mock_executor):
    """Test that MaxIterationsReached is raised when limit is hit."""

    def code_response(i: int) -> MockModelResponse:
        return MockModelResponse(text=f"Step {i}", code=f"print({i})", tool_use_id=f"{i}", tool_use_name="python")

    responses = [code_response(i) for i in range(3)]
    responses.append(MockModelResponse(text="Done"))

    model = MockModel(responses)

    async def mock_stream(timeout):
        yield "output\n"

    mock_execution = AsyncMock(spec=Execution)
    mock_execution.stream = mock_stream
    mock_execution.result.return_value = Mock(text="output\n", images=[])

    mock_executor.submit = AsyncMock(return_value=mock_execution)

    agent = CodeActAgent(model, mock_executor)
    turn = agent.run("Run code", max_steps=3)

    with pytest.raises(MaxStepsReached):
        async for _ in turn.stream():
            pass


@pytest.mark.asyncio
async def test_code_execution_error(mock_executor):
    """Test handling of code execution errors."""
    model = MockModel(
        [
            MockModelResponse(text="Let me try", code="invalid code", tool_use_id="123", tool_use_name="python"),
            MockModelResponse(text="Sorry, that failed", code=None),
        ]
    )

    mock_execution = AsyncMock(spec=Execution)
    mock_execution.stream.side_effect = ExecutionError("Error message", "Error trace")

    mock_executor.submit = AsyncMock(return_value=mock_execution)

    agent = CodeActAgent(model, mock_executor)
    turn = agent.run("Run some code")

    responses = []
    async for item in turn.stream():
        responses.append(item)

    assert len(responses) == 3
    assert isinstance(responses[0], MockModelTurn)  # Initial response
    assert isinstance(responses[1], CodeAction)  # Failed code execution
    assert isinstance(responses[2], MockModelTurn)  # Error feedback response

    last_model_response = await responses[2].response()
    assert last_model_response.text == "Sorry, that failed"
    assert last_model_response.code is None

    agent_response = await turn.response()
    assert agent_response.text == "Sorry, that failed"
