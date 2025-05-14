from unittest.mock import AsyncMock, Mock

import pytest

from freeact.tracing.base import Trace, TracerProvider
from freeact.tracing.context import (
    TracingContextManager,
    _tracing_active_session_id_context,
    _tracing_active_trace_context,
    _tracing_tracer_provider_context,
    get_active_trace,
    get_active_tracing_session_id,
    get_tracer_provider,
    session,
    start,
    use_trace,
)
from freeact.tracing.langfuse import LangfuseTracer, LangfuseTracingConfig
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


@pytest.fixture
def langfuse_tracing_config():
    return LangfuseTracingConfig(
        public_key="test-public-key",
        secret_key="test-secret-key",
        host="https://test-host.com",
    )


@pytest.fixture(autouse=True)
def clear_tracer_context():
    token = _tracing_tracer_provider_context.set(None)
    yield
    _tracing_tracer_provider_context.reset(token)


@pytest.fixture(autouse=True)
def clear_session_context():
    token = _tracing_active_session_id_context.set(None)
    yield
    _tracing_active_session_id_context.reset(token)


@pytest.fixture(autouse=True)
def clear_trace_context():
    token = _tracing_active_trace_context.set(None)
    yield
    _tracing_active_trace_context.reset(token)


def test_get_tracer_provider_with_default():
    tracer = get_tracer_provider()
    assert isinstance(tracer, NoopTracer)


def test_get_tracer_provider_with_context(tracer):
    token = _tracing_tracer_provider_context.set(tracer)
    try:
        tracer = get_tracer_provider()
        assert tracer == tracer
    finally:
        _tracing_tracer_provider_context.reset(token)


@pytest.mark.asyncio
async def test_tracing_context_manager(tracer):
    async with TracingContextManager(tracer):
        assert _tracing_tracer_provider_context.get() == tracer

    assert _tracing_tracer_provider_context.get() is None
    tracer.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_tracing_context_manager_nesting_prevention(tracer):
    first_tracer = Mock(spec=TracerProvider)
    token = _tracing_tracer_provider_context.set(first_tracer)

    try:
        context_manager = TracingContextManager(tracer)
        with pytest.raises(RuntimeError, match="TracingContextManager cannot be nested"):
            async with context_manager:
                pass
    finally:
        _tracing_tracer_provider_context.reset(token)


@pytest.mark.asyncio
async def test_start_tracing_with_langfuse_config(langfuse_tracing_config):
    async with start(config=langfuse_tracing_config) as context_manager:
        assert isinstance(context_manager, TracingContextManager)
        assert isinstance(context_manager._tracer_provider, LangfuseTracer)


@pytest.mark.asyncio
async def test_start_tracing_with_default_config():
    async with start() as context_manager:
        assert isinstance(context_manager, TracingContextManager)
        assert isinstance(context_manager._tracer_provider, LangfuseTracer)


@pytest.mark.asyncio
async def test_start_tracing_with_unsupported_config():
    class UnsupportedConfig:
        pass

    with pytest.raises(ValueError, match="Unsupported tracing config"):
        async with start(config=UnsupportedConfig()):  # type: ignore
            pass


def test_get_tracing_session_id_default():
    session_id = get_active_tracing_session_id()
    assert session_id is None


def test_get_tracing_session_id_with_context():
    test_session_id = "test-session-id"
    token = _tracing_active_session_id_context.set(test_session_id)
    try:
        session_id = get_active_tracing_session_id()
        assert session_id == test_session_id
    finally:
        _tracing_active_session_id_context.reset(token)


@pytest.mark.asyncio
async def test_session_context_manager():
    test_session_id = "test-session-id"

    async with session(test_session_id) as result:
        assert _tracing_active_session_id_context.get() == test_session_id
        assert result == test_session_id

    assert _tracing_active_session_id_context.get() is None


@pytest.mark.asyncio
async def test_session_context_manager_nested():
    test_session_id_1 = "test-session-id-1"
    test_session_id_2 = "test-session-id-2"

    async with session(test_session_id_1) as result_1:
        async with session(test_session_id_2) as result_2:
            assert _tracing_active_session_id_context.get() == test_session_id_2
            assert result_2 == test_session_id_2
        assert _tracing_active_session_id_context.get() == test_session_id_1
        assert result_1 == test_session_id_1

    assert _tracing_active_session_id_context.get() is None


def test_get_active_trace_with_default():
    trace = get_active_trace()
    assert isinstance(trace, NoopTrace)


def test_get_active_trace_with_context(trace):
    token = _tracing_active_trace_context.set(trace)
    try:
        active_trace = get_active_trace()
        assert active_trace == trace
    finally:
        _tracing_active_trace_context.reset(token)


@pytest.mark.asyncio
async def test_trace_context_manager_async(trace):
    async with use_trace(trace) as active_trace:
        assert _tracing_active_trace_context.get() == trace
        assert active_trace == trace

    assert _tracing_active_trace_context.get() is None


@pytest.mark.asyncio
async def test_trace_context_manager_nested(trace):
    first_trace = Mock(spec=Trace)
    first_trace.trace_id = "first-trace-id"
    second_trace = trace

    async with use_trace(first_trace) as trace1:
        assert _tracing_active_trace_context.get() == first_trace
        assert trace1 == first_trace

        async with use_trace(second_trace) as trace2:
            assert _tracing_active_trace_context.get() == second_trace
            assert trace2 == second_trace

        assert _tracing_active_trace_context.get() == first_trace

    assert _tracing_active_trace_context.get() is None


@pytest.mark.asyncio
async def test_trace_context_manager_with_exception(trace):
    try:
        async with use_trace(trace):
            assert _tracing_active_trace_context.get() == trace
            raise ValueError("Test exception")
    except ValueError:
        assert _tracing_active_trace_context.get() is None
