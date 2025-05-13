from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from freeact import CodeActAgent, CodeExecution
from freeact.tracing.base import Span, Trace, TracerProvider
from freeact.tracing.context import get_active_trace
from tests.unit.test_model import MockModel, MockModelResponse, MockModelTurn


class TracingMockModel(MockModel):
    def __init__(self, responses: List[MockModelResponse]):
        super().__init__(responses)
        self.request_trace: Trace | None = None
        self.feedback_trace: Trace | None = None

    def request(self, user_query: str, **kwargs) -> MockModelTurn:
        self.request_trace = get_active_trace()
        return super().request(user_query, **kwargs)

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None, tool_use_name: str | None, **kwargs
    ) -> MockModelTurn:
        self.feedback_trace = get_active_trace()
        return super().feedback(feedback, is_error, tool_use_id, tool_use_name, **kwargs)


@pytest.fixture
def trace():
    trace = Mock(spec=Trace)
    trace.span.return_value = Mock(spec=Span)
    trace.trace_id = "test-trace-id"
    return trace


@pytest.fixture
def tracer_provider(trace):
    provider = Mock(spec=TracerProvider)
    provider.create_trace.return_value = trace
    return provider


@pytest.fixture
def executor():
    return Mock()


@pytest.fixture
def code_execution():
    async def mock_stream(timeout):
        yield "output\n"

    execution = AsyncMock(spec=CodeExecution)
    execution.stream = mock_stream
    execution.result.return_value = Mock(text="output\n", images=[], is_error=False)
    return execution


@pytest.fixture(autouse=True)
def tracing_context(tracer_provider):
    context_patches = [
        patch("freeact.tracing.context.get_tracer_provider", return_value=tracer_provider),
        patch("freeact.tracing.context.get_active_tracing_session_id", return_value="test-session-id"),
    ]
    for p in context_patches:
        p.start()
    yield
    for p in context_patches:
        p.stop()


@pytest.mark.asyncio
async def test_agent_creates_trace(tracer_provider, trace, executor):
    """Test that the agent creates and updates a trace."""
    model = MockModel([MockModelResponse(text="Hello! I can help you.", code=None)])
    agent = CodeActAgent(model, executor)

    turn = agent.run("Hi there!")
    await turn.response()

    tracer_provider.create_trace.assert_called_once_with(
        name="Agent run",
        session_id="test-session-id",
        input={
            "user_query": "Hi there!",
            "max_steps": 30,
            "step_timeout": 120,
        },
    )

    trace.update.assert_called_with(output="Hello! I can help you.")
    trace.end.assert_called_once()


@pytest.mark.asyncio
async def test_agent_creates_span_for_code_execution(trace, executor, code_execution):
    """Test that the agent creates spans for code execution."""
    span = trace.span.return_value

    model = MockModel(
        [
            MockModelResponse(text="Let me help", code="print('hello')", tool_use_id="123", tool_use_name="python"),
            MockModelResponse(text="All done!", code=None),
        ]
    )

    executor.submit = AsyncMock(return_value=code_execution)

    agent = CodeActAgent(model, executor)
    turn = agent.run("Run some code")

    await turn.response()

    trace.span.assert_called_with(name="Code execution", input={"code": "print('hello')"})
    span.update.assert_called_with(output=code_execution.result.return_value)
    span.end.assert_called_once()


@pytest.mark.asyncio
async def test_trace_propagation_to_model(trace, executor, code_execution):
    """Test that the trace is properly propagated to the model."""
    model = TracingMockModel(
        [
            MockModelResponse(text="Let me help", code="print('hello')", tool_use_id="123", tool_use_name="python"),
            MockModelResponse(text="All done!", code=None),
        ]
    )

    executor.submit = AsyncMock(return_value=code_execution)

    agent = CodeActAgent(model, executor)
    turn = agent.run("Run some code")
    await turn.response()

    assert model.request_trace == trace
    assert model.feedback_trace == trace


@pytest.mark.asyncio
async def test_error_scenario_tracing(trace, executor):
    """Test that errors during code execution are properly traced."""
    span = trace.span.return_value

    model = MockModel(
        [
            MockModelResponse(text="Let me try", code="invalid code", tool_use_id="123", tool_use_name="python"),
            MockModelResponse(text="Sorry, that failed", code=None),
        ]
    )

    execution = AsyncMock(spec=CodeExecution)
    execution.stream = AsyncMock(return_value=AsyncMock())
    error_result = Mock(text="Error: invalid syntax", images=[], is_error=True)
    execution.result.return_value = error_result

    executor.submit = AsyncMock(return_value=execution)

    agent = CodeActAgent(model, executor)
    turn = agent.run("Run some code")

    await turn.response()

    span.update.assert_called_with(output=error_result)
    span.end.assert_called_once()
    trace.end.assert_called_once()
