import atexit
import contextvars
import logging
import os
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


def configure(
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str | None = None,
    **kwargs,
) -> None:
    """API DOC TODO"""
    global _tracer

    with _tracing_setup_lock:
        if _tracer is not None:
            logger.warning("Tracing is already configured. Call 'tracing.shutdown()' first to reconfigure.")
            return

        # we explicitly require these variables to be passed or set in the environment, as Langfuse by default
        # simply logs a warning if the variables are not set.
        _public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        _secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        _host = host or os.getenv("LANGFUSE_HOST")

        if _public_key is None or _secret_key is None or _host is None:
            raise ValueError(
                "Langfuse credentials and host are missing. Please provide them by either:\\n"
                "1. Passing `public_key`, `secret_key`, and `host` arguments.\\n"
                "2. Setting the environment variables `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST`."
            )

        _tracer = LangfuseTracer(
            public_key=_public_key,
            secret_key=_secret_key,
            host=_host,
            **kwargs,
        )

        atexit.register(_shutdown_tracing)

        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGHUP):
                try:
                    signal.signal(sig, _shutdown_signal_handler)
                except (ValueError, OSError):
                    pass


def shutdown() -> None:
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
    """API DOC TODO"""
    active_trace = await get_tracer().trace(
        name=name,
        input=input,
        session_id=get_active_session_id() or session_id,
    )
    token = _active_trace_context.set(active_trace)
    try:
        yield active_trace
    finally:
        _active_trace_context.reset(token)


@asynccontextmanager
async def span(
    name: str,
    input: dict[str, Any] | None = None,
) -> AsyncIterator[Span]:
    """API DOC TODO"""
    active_span = await get_active_trace().span(
        name=name,
        input=input,
    )
    token = _active_span_context.set(active_span)
    try:
        yield active_span
    finally:
        _active_span_context.reset(token)


@contextmanager
def session(session_id: str | None = None) -> Iterator[str]:
    """API DOC TODO"""
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
