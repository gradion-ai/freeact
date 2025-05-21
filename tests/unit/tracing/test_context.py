from unittest.mock import Mock, patch

import pytest

from freeact.tracing import context
from freeact.tracing.base import Tracer
from freeact.tracing.context import (
    configure,
    get_active_session_id,
    get_active_trace,
    get_tracer,
    session,
    shutdown,
    trace,
)
from freeact.tracing.langfuse import LangfuseTracer
from freeact.tracing.noop import NoopTrace, NoopTracer


@pytest.fixture(autouse=True)
def clear_tracer():
    """Reset tracing provider before and after each test."""
    original_tracer = context._tracer
    context._tracer = None

    yield

    context._tracer = None

    try:
        if original_tracer:
            original_tracer.shutdown()
    except Exception:
        pass


def test_get_tracer_provider_with_default():
    tracer = get_tracer()
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
    assert get_tracer() == mock_tracer_instance


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
    assert get_tracer() == mock_tracer_instance


@patch("freeact.tracing.context.LangfuseTracer")
def test_configure_tracing_reconfiguration_attempt(mock_langfuse_tracer):
    """Test that attempting to reconfigure logs a warning."""
    mock_tracer_instance = Mock(spec=LangfuseTracer)
    mock_langfuse_tracer.return_value = mock_tracer_instance
    context._tracer = None

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
    mock_tracer = Mock(spec=Tracer)
    context._tracer = mock_tracer

    shutdown()

    mock_tracer.shutdown.assert_called_once()
    assert context._tracer is None


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
    active_session_id = get_active_session_id()
    assert active_session_id is None


def test_session_id_context_manager():
    test_session_id = "test-session-id"

    with session(test_session_id) as active_session_id:
        assert get_active_session_id() == active_session_id
        assert active_session_id == test_session_id
    assert get_active_session_id() is None


def test_session_id_context_manager_nested():
    test_session_id_1 = "test-session-id-1"
    test_session_id_2 = "test-session-id-2"

    with session(test_session_id_1) as result_1:
        with session(test_session_id_2) as result_2:
            assert get_active_session_id() == test_session_id_2
            assert result_2 == test_session_id_2
        assert get_active_session_id() == test_session_id_1
        assert result_1 == test_session_id_1
    assert get_active_session_id() is None


def test_get_active_trace_with_default():
    active_trace = get_active_trace()
    assert isinstance(active_trace, NoopTrace)


@pytest.mark.asyncio
async def test_trace_context_manager():
    async with trace(name="Test trace") as active_trace:
        assert get_active_trace() == active_trace
    assert isinstance(get_active_trace(), NoopTrace)


@pytest.mark.asyncio
async def test_trace_context_manager_nested():
    async with trace(name="Test trace 1") as active_trace_1:
        assert get_active_trace() == active_trace_1
        async with trace(name="Test trace 2") as active_trace_2:
            assert get_active_trace() == active_trace_2
        assert get_active_trace() == active_trace_1
    assert isinstance(get_active_trace(), NoopTrace)


@pytest.mark.asyncio
async def test_trace_context_manager_with_exception():
    try:
        async with trace(name="Test trace") as active_trace:
            assert get_active_trace() == active_trace
            raise ValueError("Test exception")
    except ValueError:
        assert isinstance(get_active_trace(), NoopTrace)
