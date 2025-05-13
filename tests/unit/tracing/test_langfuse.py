import datetime as dt
from unittest.mock import Mock, patch

import pytest

from freeact.tracing.langfuse import (
    LangfuseSpan,
    LangfuseTrace,
    LangfuseTracer,
    LangfuseTracingConfig,
)


@pytest.fixture
def langfuse_client():
    with patch("langfuse.Langfuse") as mock_langfuse_cls:
        mock_client = Mock()
        mock_langfuse_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def tracing_config():
    return LangfuseTracingConfig(
        public_key="test-public-key",
        secret_key="test-secret-key",
        host="https://test-host.com",
    )


@pytest.fixture
def tracer(langfuse_client, tracing_config):
    return LangfuseTracer(tracing_config)


def test_tracer_initialization(langfuse_client, tracing_config):
    """Test that the tracer initializes correctly with the given configuration."""
    with patch("freeact.tracing.langfuse.litellm") as mock_litellm:
        tracer = LangfuseTracer(tracing_config)

        assert "langfuse" in mock_litellm.success_callback
        assert "langfuse" in mock_litellm.failure_callback

    assert tracer.client == langfuse_client


def test_create_trace(tracer, langfuse_client):
    """Test creating a trace."""
    langfuse_client.trace.return_value = Mock()

    trace = tracer.create_trace(
        name="test-trace",
        user_id="test-user",
        session_id="test-session",
        metadata={"key": "value"},
        tags=["tag1", "tag2"],
    )

    langfuse_client.trace.assert_called_once_with(
        name="test-trace",
        user_id="test-user",
        session_id="test-session",
        input=None,
        output=None,
        metadata={"key": "value"},
        tags=["tag1", "tag2"],
        timestamp=None,
    )

    assert isinstance(trace, LangfuseTrace)


def test_trace_update(tracer, langfuse_client):
    """Test updating a trace."""
    langfuse_trace_mock = Mock()
    langfuse_client.trace.return_value = langfuse_trace_mock

    trace = tracer.create_trace(name="test-trace")

    trace.update(
        name="updated-name",
        user_id="updated-user",
        session_id="updated-session",
        input="test-input",
        output="test-output",
        metadata={"updated": "value"},
        tags=["updated-tag"],
    )

    langfuse_trace_mock.update.assert_called_once_with(
        name="updated-name",
        user_id="updated-user",
        session_id="updated-session",
        input="test-input",
        output="test-output",
        metadata={"updated": "value"},
        tags=["updated-tag"],
    )


def test_trace_get_trace_id(tracer, langfuse_client):
    """Test trace property."""
    langfuse_trace = Mock()
    langfuse_trace.id = "test-trace-id"
    langfuse_client.trace.return_value = langfuse_trace

    trace = tracer.create_trace(name="test-trace")

    assert trace.trace_id == "test-trace-id"


def test_trace_end(tracer, langfuse_client):
    """Test ending a trace (which doesn't do anything in this implementation)."""
    langfuse_trace = Mock()
    langfuse_client.trace.return_value = langfuse_trace

    trace = tracer.create_trace(name="test-trace")
    trace.end()

    langfuse_trace.end.assert_not_called()


def test_create_span(tracer, langfuse_client):
    """Test creating a span within a trace."""
    langfuse_trace = Mock()
    langfuse_trace.span.return_value = Mock()
    langfuse_client.trace.return_value = langfuse_trace

    trace = tracer.create_trace(name="test-trace")
    start_time = dt.datetime.now()
    end_time = start_time + dt.timedelta(seconds=5)

    span = trace.span(
        name="test-span",
        start_time=start_time,
        end_time=end_time,
        metadata={"span": "data"},
        input="span-input",
        output="span-output",
        status_message="success",
    )

    langfuse_trace.span.assert_called_once_with(
        name="test-span",
        start_time=start_time,
        end_time=end_time,
        metadata={"span": "data"},
        input="span-input",
        output="span-output",
        status_message="success",
    )

    assert isinstance(span, LangfuseSpan)


def test_span_update(tracer, langfuse_client):
    """Test updating a span."""
    langfuse_trace = Mock()
    langfuse_span = Mock()
    langfuse_trace.span.return_value = langfuse_span
    langfuse_client.trace.return_value = langfuse_trace

    trace = tracer.create_trace(name="test-trace")
    span = trace.span(name="test-span")

    start_time = dt.datetime.now()
    end_time = start_time + dt.timedelta(seconds=5)

    span.update(
        name="updated-span",
        start_time=start_time,
        end_time=end_time,
        metadata={"updated": "data"},
        input="updated-input",
        output="updated-output",
        status_message="updated-status",
    )

    langfuse_span.update.assert_called_once_with(
        name="updated-span",
        start_time=start_time,
        end_time=end_time,
        metadata={"updated": "data"},
        input="updated-input",
        output="updated-output",
        status_message="updated-status",
    )


def test_span_get_properties(tracer, langfuse_client):
    """Test span properties."""
    langfuse_trace = Mock()
    langfuse_span = Mock()
    langfuse_trace.span.return_value = langfuse_span
    langfuse_client.trace.return_value = langfuse_trace

    langfuse_span.trace_id = "test-trace-id"
    langfuse_span.id = "test-span-id"

    trace = tracer.create_trace(name="test-trace")
    span = trace.span(name="test-span")

    assert span.trace_id == "test-trace-id"
    assert span.span_id == "test-span-id"


def test_span_end(tracer, langfuse_client):
    """Test ending a span."""
    langfuse_trace = Mock()
    langfuse_span = Mock()
    langfuse_trace.span.return_value = langfuse_span
    langfuse_client.trace.return_value = langfuse_trace

    trace = tracer.create_trace(name="test-trace")
    span = trace.span(name="test-span")

    span.end()

    langfuse_span.end.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown(tracer, langfuse_client):
    await tracer.shutdown()

    langfuse_client.shutdown.assert_called_once()


def test_config_from_env():
    """Test creating config from environment variables."""
    with patch.dict(
        "os.environ",
        {
            "LANGFUSE_PUBLIC_KEY": "env-public-key",
            "LANGFUSE_SECRET_KEY": "env-secret-key",
            "LANGFUSE_HOST": "https://env-host.com",
            "LANGFUSE_ENVIRONMENT": "test",
            "LANGFUSE_RELEASE": "v1.0.0",
            "LANGFUSE_DEBUG": "true",
            "LANGFUSE_THREADS": "4",
            "LANGFUSE_MAX_RETRIES": "3",
            "LANGFUSE_TIMEOUT_IN_S": "30",
            "LANGFUSE_SAMPLE_RATE": "0.5",
        },
    ):
        config = LangfuseTracingConfig.from_env()

        assert config.public_key == "env-public-key"
        assert config.secret_key == "env-secret-key"
        assert config.host == "https://env-host.com"
        assert config.environment == "test"
        assert config.release == "v1.0.0"
        assert config.debug is True
        assert config.threads == 4
        assert config.max_retries == 3
        assert config.timeout_in_s == 30
        assert config.sample_rate == 0.5
