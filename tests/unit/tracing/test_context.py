from unittest.mock import AsyncMock, Mock, patch

import pytest

import freeact.tracing.context as tracing_context
from freeact.tracing.base import Trace, TracerProvider
from freeact.tracing.context import (
    configure,
    get_active_trace,
    get_active_tracing_session_id,
    get_tracer_provider,
    session,
    shutdown,
    with_trace,
)
from freeact.tracing.langfuse import LangfuseTracer
from freeact.tracing.noop import NoopTrace, NoopTracer


@pytest.fixture
def trace():
    trace = Mock(spec=Trace)
    trace.trace_id = "test-trace-id"
    return trace


@pytest.fixture
def tracer():
    tracer = Mock(spec=TracerProvider)
    tracer.create_trace.return_value = Mock(spec=Trace)
    tracer.shutdown = AsyncMock()
    return tracer


@pytest.fixture(autouse=True)
def clear_tracer_provider():
    """Reset tracing provider before and after each test."""
    original_tracer_provider = tracing_context._tracer_provider
    tracing_context._tracer_provider = None

    yield

    tracing_context._tracer_provider = None

    try:
        if original_tracer_provider:
            original_tracer_provider.shutdown()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clear_session_context():
    token = tracing_context._active_session_id_context.set(None)
    yield
    tracing_context._active_session_id_context.reset(token)


@pytest.fixture(autouse=True)
def clear_trace_context():
    token = tracing_context._active_trace_context.set(None)
    yield
    tracing_context._active_trace_context.reset(token)


def test_get_tracer_provider_with_default():
    tracer = get_tracer_provider()
    assert isinstance(tracer, NoopTracer)


@patch("freeact.tracing.context.LangfuseTracer")
def test_configure_tracing_with_explicit_parameters(mock_langfuse_tracer):
    """Test configure method with explicit parameters."""
    mock_tracer_instance = Mock(spec=LangfuseTracer)
    mock_langfuse_tracer.return_value = mock_tracer_instance

    configure(
        public_key="test-public-key",
        secret_key="test-secret-key",
        host="https://test-host.com",
        debug=True,
    )

    mock_langfuse_tracer.assert_called_once_with(
        public_key="test-public-key",
        secret_key="test-secret-key",
        host="https://test-host.com",
        debug=True,
    )
    assert get_tracer_provider() == mock_tracer_instance


@patch("freeact.tracing.context.LangfuseTracer")
@patch.dict(
    "os.environ",
    {
        "LANGFUSE_PUBLIC_KEY": "env-public-key",
        "LANGFUSE_SECRET_KEY": "env-secret-key",
        "LANGFUSE_HOST": "https://env-host.com",
    },
    clear=True,
)
def test_configure_tracing_with_environment_variables(mock_langfuse_tracer):
    """Test configure method using environment variables."""
    mock_tracer_instance = Mock(spec=LangfuseTracer)
    mock_langfuse_tracer.return_value = mock_tracer_instance

    configure()

    mock_langfuse_tracer.assert_called_once_with(
        public_key="env-public-key",
        secret_key="env-secret-key",
        host="https://env-host.com",
    )
    assert get_tracer_provider() == mock_tracer_instance


@patch("freeact.tracing.context.LangfuseTracer")
def test_configure_tracing_reconfiguration_attempt(mock_langfuse_tracer):
    """Test that attempting to reconfigure logs a warning."""
    mock_tracer_instance = Mock(spec=LangfuseTracer)
    mock_langfuse_tracer.return_value = mock_tracer_instance
    tracing_context._tracer_provider = None

    configure(
        public_key="test-public-key",
        secret_key="test-secret-key",
        host="https://test-host.com",
    )

    mock_langfuse_tracer.assert_called_once()
    mock_langfuse_tracer.reset_mock()

    configure(
        public_key="new-public-key",
        secret_key="new-secret-key",
        host="https://new-host.com",
    )

    mock_langfuse_tracer.assert_not_called()


@patch.dict("os.environ", {}, clear=True)
def test_configure_tracing_missing_credentials():
    """Test that configure raises ValueError when credentials are missing."""
    with pytest.raises(ValueError, match="Langfuse credentials and host are missing"):
        configure()


def test_shutdown_successful():
    """Test successful tracer provider shutdown."""
    mock_tracer = Mock(spec=TracerProvider)
    tracing_context._tracer_provider = mock_tracer

    shutdown()

    mock_tracer.shutdown.assert_called_once()
    assert tracing_context._tracer_provider is None


@patch("freeact.tracing.context.atexit")
@patch("freeact.tracing.context.LangfuseTracer")
def test_configure_registers_atexit_handler(mock_langfuse_tracer, mock_atexit):
    """Test that configure registers an atexit handler."""
    mock_tracer_instance = Mock(spec=LangfuseTracer)
    mock_langfuse_tracer.return_value = mock_tracer_instance

    configure(
        public_key="test-public-key",
        secret_key="test-secret-key",
        host="https://test-host.com",
    )

    mock_atexit.register.assert_called_once()


def test_get_tracing_session_id_default():
    session_id = get_active_tracing_session_id()
    assert session_id is None


def test_get_tracing_session_id_with_context():
    test_session_id = "test-session-id"
    token = tracing_context._active_session_id_context.set(test_session_id)
    try:
        session_id = get_active_tracing_session_id()
        assert session_id == test_session_id
    finally:
        tracing_context._active_session_id_context.reset(token)


@pytest.mark.asyncio
async def test_session_context_manager():
    test_session_id = "test-session-id"

    async with session(test_session_id) as result:
        assert tracing_context._active_session_id_context.get() == test_session_id
        assert result == test_session_id

    assert tracing_context._active_session_id_context.get() is None


@pytest.mark.asyncio
async def test_session_context_manager_nested():
    test_session_id_1 = "test-session-id-1"
    test_session_id_2 = "test-session-id-2"

    async with session(test_session_id_1) as result_1:
        async with session(test_session_id_2) as result_2:
            assert tracing_context._active_session_id_context.get() == test_session_id_2
            assert result_2 == test_session_id_2
        assert tracing_context._active_session_id_context.get() == test_session_id_1
        assert result_1 == test_session_id_1

    assert tracing_context._active_session_id_context.get() is None


def test_get_active_trace_with_default():
    trace = get_active_trace()
    assert isinstance(trace, NoopTrace)


def test_get_active_trace_with_context(trace):
    token = tracing_context._active_trace_context.set(trace)
    try:
        active_trace = get_active_trace()
        assert active_trace == trace
    finally:
        tracing_context._active_trace_context.reset(token)


@pytest.mark.asyncio
async def test_trace_context_manager_async(trace):
    async with with_trace(trace) as active_trace:
        assert tracing_context._active_trace_context.get() == trace
        assert active_trace == trace

    assert tracing_context._active_trace_context.get() is None


@pytest.mark.asyncio
async def test_trace_context_manager_nested(trace):
    first_trace = Mock(spec=Trace)
    first_trace.trace_id = "first-trace-id"
    second_trace = trace

    async with with_trace(first_trace) as trace1:
        assert tracing_context._active_trace_context.get() == first_trace
        assert trace1 == first_trace

        async with with_trace(second_trace) as trace2:
            assert tracing_context._active_trace_context.get() == second_trace
            assert trace2 == second_trace

        assert tracing_context._active_trace_context.get() == first_trace

    assert tracing_context._active_trace_context.get() is None


@pytest.mark.asyncio
async def test_trace_context_manager_with_exception(trace):
    try:
        async with with_trace(trace):
            assert tracing_context._active_trace_context.get() == trace
            raise ValueError("Test exception")
    except ValueError:
        assert tracing_context._active_trace_context.get() is None
