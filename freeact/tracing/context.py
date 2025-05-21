import atexit
import contextvars
import logging
import signal
import sys
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator

from freeact.tracing.base import Span, Trace, Tracer
from freeact.tracing.langfuse import LangfuseTracer
from freeact.tracing.noop import NoopSpan, NoopTrace, NoopTracer

logger = logging.getLogger(__name__)

_tracer: Tracer | None = None
_tracing_setup_lock = threading.RLock()
_tracing_shutdown_lock = threading.RLock()

_active_trace_context: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "tracing_active_trace",
    default=None,
)
_active_span_context: contextvars.ContextVar[Span | None] = contextvars.ContextVar(
    "tracing_active_span",
    default=None,
)
_active_session_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tracing_active_session_id",
    default=None,
)


def configure(**kwargs) -> None:
    """Configures agent tracing using a [`Langfuse`](https://langfuse.com) backend. Once configured, all agent activities, code executions and model calls are automatically captured and exported to Langfuse.

    Accepts all [Langfuse configuration options](https://python.reference.langfuse.com/langfuse/decorators#LangfuseDecorator.configure).
    Configuration options can be provided as parameters to `configure()` or via environment variables.

    Should be called at application startup.

    Args:
        **kwargs: Langfuse configuration parameters.
    """
    global _tracer

    with _tracing_setup_lock:
        if _tracer is not None:
            logger.warning("Tracing is already configured. Call 'tracing.shutdown()' first to reconfigure.")
            return

        _tracer = LangfuseTracer(**kwargs)

        atexit.register(_shutdown_tracing)

        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGHUP):
                try:
                    signal.signal(sig, _shutdown_signal_handler)
                except (ValueError, OSError):
                    pass


def shutdown() -> None:
    """Shuts down agent tracing and flushes pending traces to the backend.

    `shutdown()` is called automatically on application exit. For manual control, call this function explicitly.
    """
    _shutdown_tracing()


def _shutdown_tracing() -> None:
    global _tracer

    with _tracing_shutdown_lock:
        if _tracer is not None:
            try:
                _tracer.shutdown()
            except Exception as e:
                logger.error(f"Error during tracing shutdown: {e}")
            finally:
                _tracer = None


def _shutdown_signal_handler(signum, frame):
    # This handler processes SIGTERM and SIGHUP signals.
    # It calls sys.exit() which will in turn invoke the atexit handler.
    sys.exit(128 + signum)


@asynccontextmanager
async def trace(
    name: str,
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> AsyncIterator[Trace]:
    """Context manager for

    - creating a new [`Trace`][freeact.tracing.base.Trace] using the globally
      configured [`Tracer`][freeact.tracing.base.Tracer].
    - setting the trace as the active trace for the scope of the context.

    The trace might be associated with a session according to the following precedence:

    1. Active session from [`session`][freeact.tracing.context.session] context
    2. Explicitly provided `session_id` parameter
    3. No session association if neither is available

    Args:
        name: Name of the trace.
        input: Input data associated with the trace.
        session_id: Session id to assign the trace to. Defaults to the active session.
    """
    active_trace = await get_tracer().trace(
        name=name,
        input=input,
        session_id=get_active_session_id() or session_id,
    )
    token = _active_trace_context.set(active_trace)
    try:
        yield active_trace
    except Exception:
        _active_trace_context.reset(token)
        raise
    else:
        _active_trace_context.reset(token)
    finally:
        await active_trace.end()


@asynccontextmanager
async def span(
    name: str,
    input: dict[str, Any] | None = None,
) -> AsyncIterator[Span]:
    """Context manager for

    - creating a new [`Span`][freeact.tracing.base.Span] within the active [`Trace`][freeact.tracing.base.Trace].
    - setting the span as the active span for the scope of the context.

    Args:
        name: Name of the span.
        input: Input data associated with the span.
    """
    active_span = await get_active_trace().span(
        name=name,
        input=input,
    )
    token = _active_span_context.set(active_span)
    try:
        yield active_span
    except Exception:
        _active_span_context.reset(token)
        raise
    else:
        _active_span_context.reset(token)
    finally:
        await active_span.end()


@contextmanager
def session(session_id: str | None = None) -> Iterator[str]:
    """Context manager that creates a session scope for tracing operations.

    All tracing operations within this context are associated with the specified session id.

    Args:
        session_id: Identifier for the session. A random session id is generated if not specified.
    """
    active_session_id = session_id or create_session_id()
    token = _active_session_id_context.set(active_session_id)
    try:
        yield active_session_id
    finally:
        _active_session_id_context.reset(token)


def get_tracer() -> Tracer:
    global _tracer
    return _tracer or NoopTracer()


def get_active_trace() -> Trace:
    return _active_trace_context.get() or NoopTrace()


def get_active_span() -> Span:
    return _active_span_context.get() or NoopSpan()


def get_active_session_id() -> str | None:
    return _active_session_id_context.get()


def create_session_id() -> str:
    return str(uuid.uuid4())[:8]
