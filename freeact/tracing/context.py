import contextvars

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


class TraceContext:
    def __init__(self, trace: Trace):
        self._trace = trace
        self._token: contextvars.Token | None = None

    def __enter__(self):
        self._token = _tracing_active_trace_context.set(self._trace)
        return self._trace

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            _tracing_active_trace_context.reset(self._token)
        self._token = None

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


def use_trace(trace: Trace) -> TraceContext:
    return TraceContext(trace)


_tracing_active_session_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tracing_active_session_id",
    default=None,
)


def get_active_tracing_session_id() -> str | None:
    return _tracing_active_session_id_context.get()


class TracingSessionContextManager:
    def __init__(self, session_id: str):
        self._session_id = session_id
        self._token: contextvars.Token[str | None] | None = None

    def __enter__(self) -> str:
        self._token = _tracing_active_session_id_context.set(self._session_id)
        return self._session_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token:
            _tracing_active_session_id_context.reset(self._token)
        self._token = None

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


def session(session_id: str) -> TracingSessionContextManager:
    return TracingSessionContextManager(session_id=session_id)
