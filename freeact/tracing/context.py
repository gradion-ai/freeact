import contextvars
from contextlib import asynccontextmanager
from typing import AsyncIterator

from freeact.tracing.base import Trace, TracerProvider, TracingConfig
from freeact.tracing.langfuse import LangfuseTracer, LangfuseTracingConfig
from freeact.tracing.noop import NoopTrace, NoopTracer

_tracing_tracer_provider_context: contextvars.ContextVar[TracerProvider | None] = contextvars.ContextVar(
    "tracing_tracer_provider",
    default=None,
)


def get_tracer_provider() -> TracerProvider:
    return _tracing_tracer_provider_context.get() or NoopTracer()


class TracingContextManager:
    """Context manager enabling tracing functionality using the supplied [`TracerProvider`][freeact.tracing.base.TracerProvider].
    It manages the lifecycle of the tracer provider.

    Args:
        tracer_provider: The tracer provider to use for tracing.

    Returns:
        The tracer provider.
    """

    def __init__(self, tracer_provider: TracerProvider):
        self._tracer_provider = tracer_provider
        self._token: contextvars.Token | None = None

    async def __aenter__(self):
        current_provider = _tracing_tracer_provider_context.get()
        if current_provider is not None:
            raise RuntimeError("TracingContextManager cannot be nested. A tracer provider is already active.")

        self._token = _tracing_tracer_provider_context.set(self._tracer_provider)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._tracer_provider.shutdown()
        if self._token:
            _tracing_tracer_provider_context.reset(self._token)
        self._token = None


def _default_tracing_config() -> TracingConfig:
    return LangfuseTracingConfig.from_env()


def start(
    config: TracingConfig | None = None,
) -> TracingContextManager:
    """Enables tracing functionality by setting up a [`TracerProvider`][freeact.tracing.base.TracerProvider] based on the supplied [`TracingConfig`][freeact.tracing.base.TracingConfig].
    By default, the [`LangfuseTracingConfig`][freeact.tracing.langfuse.LangfuseTracingConfig] is used, setting up the [`LangfuseTracer`][freeact.tracing.langfuse.LangfuseTracer].

    Args:
        config: The tracing config to use.

    Returns:
        The tracing context manager managing the lifecycle of the tracer provider.
    """
    if config is None:
        config = _default_tracing_config()

    match config:
        case LangfuseTracingConfig():
            return TracingContextManager(LangfuseTracer(config=config))
        case _:
            raise ValueError(f"Unsupported tracing config: {config}")


_tracing_active_trace_context: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "tracing_active_trace",
    default=None,
)


def get_active_trace() -> Trace:
    return _tracing_active_trace_context.get() or NoopTrace()


@asynccontextmanager
async def use_trace(trace: Trace) -> AsyncIterator[Trace]:
    """Context manager setting the active trace in the current context.

    Args:
        trace: The trace to set as active.

    Returns:
        The active trace.
    """
    token = _tracing_active_trace_context.set(trace)
    try:
        yield trace
    finally:
        _tracing_active_trace_context.reset(token)


_tracing_active_session_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tracing_active_session_id",
    default=None,
)


def get_active_tracing_session_id() -> str | None:
    return _tracing_active_session_id_context.get()


@asynccontextmanager
async def session(session_id: str) -> AsyncIterator[str]:
    """Context manager setting the active tracing session id in the current context.

    Args:
        session_id: The session id to set as active.

    Returns:
        The active session id.
    """
    token = _tracing_active_session_id_context.set(session_id)
    try:
        yield session_id
    finally:
        _tracing_active_session_id_context.reset(token)
