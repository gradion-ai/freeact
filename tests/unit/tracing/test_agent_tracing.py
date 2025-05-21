from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from freeact import CodeActAgent, CodeExecution
from freeact.tracing.base import Span, Trace, Tracer
from freeact.tracing.context import get_active_trace, session
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
    trace_mock = Mock(spec=Trace)
    span_mock = AsyncMock(spec=Span)

    trace_mock.span = AsyncMock(return_value=span_mock)
    trace_mock.update = AsyncMock()
    trace_mock.end = AsyncMock()

    trace_mock.trace_id = "test-trace-id"  # This is a property
    return trace_mock


@pytest.fixture
def tracer(trace):  # trace here is the trace_mock returned by the trace fixture
    tracer_mock = Mock(spec=Tracer)

    # Mocking the async method of Tracer
    tracer_mock.trace = AsyncMock(return_value=trace)
    return tracer_mock


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
def apply_mock_tracer(tracer):
    with patch("freeact.tracing.context.get_tracer", return_value=tracer) as p:
        yield p


@pytest.mark.asyncio
async def test_agent_creates_trace(tracer, trace, executor):
    """Test that the agent creates and updates a trace."""
    model = MockModel([MockModelResponse(text="Hello! I can help you.", code=None)])
    agent = CodeActAgent(model, executor)

    with session("test-session-id"):
        turn = agent.run("Hi there!")
        await turn.response()

    tracer.trace.assert_called_once_with(
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

    with session("test-session-id"):
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
    with session("test-session-id"):
        turn = agent.run("Run some code")
        await turn.response()

    assert model.request_trace == trace
    assert model.feedback_trace == trace


@pytest.mark.asyncio
async def test_error_scenario_tracing(trace, executor):
    """Test that errors during code execution are properly traced."""
    # Get the mock for the Span object from trace.span's return value
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
    with session("test-session-id"):
        turn = agent.run("Run some code")
        await turn.response()

    span.update.assert_called_with(output=error_result)
    span.end.assert_called_once()
    trace.end.assert_called_once()
