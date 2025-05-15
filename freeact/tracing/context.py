import atexit
import contextvars
import logging
import os
import signal
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from freeact.tracing.base import Trace, TracerProvider
from freeact.tracing.langfuse import LangfuseTracer
from freeact.tracing.noop import NoopTrace, NoopTracer

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_tracing_setup_lock = threading.RLock()
_tracing_shutdown_lock = threading.RLock()


def get_tracer_provider() -> TracerProvider:
    global _tracer_provider
    return _tracer_provider or NoopTracer()


def configure(
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str | None = None,
    **kwargs,
) -> None:
    """API DOC TODO"""
    global _tracer_provider

    with _tracing_setup_lock:
        if _tracer_provider is not None:
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

        _tracer_provider = LangfuseTracer(
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


def _shutdown_tracing() -> None:
    global _tracer_provider

    with _tracing_shutdown_lock:
        if _tracer_provider is not None:
            try:
                _tracer_provider.shutdown()
            except Exception as e:
                logger.error(f"Error during tracing shutdown: {e}")
            finally:
                _tracer_provider = None


def _shutdown_signal_handler(signum, frame):
    # This handler processes SIGTERM and SIGHUP signals.
    # It calls sys.exit() which will in turn invoke the atexit handler.
    sys.exit(128 + signum)


def shutdown() -> None:
    _shutdown_tracing()


_active_trace_context: contextvars.ContextVar[Trace | None] = contextvars.ContextVar(
    "tracing_active_trace",
    default=None,
)


def get_active_trace() -> Trace:
    return _active_trace_context.get() or NoopTrace()


@asynccontextmanager
async def with_trace(trace: Trace) -> AsyncIterator[Trace]:
    """API DOC TODO"""
    token = _active_trace_context.set(trace)
    try:
        yield trace
    finally:
        _active_trace_context.reset(token)


_active_session_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tracing_active_session_id",
    default=None,
)


def get_active_tracing_session_id() -> str | None:
    return _active_session_id_context.get()


@asynccontextmanager
async def session(session_id: str | None = None) -> AsyncIterator[str]:
    """API DOC TODO"""
    _session_id = session_id or create_session_id()
    token = _active_session_id_context.set(_session_id)
    try:
        yield _session_id
    finally:
        _active_session_id_context.reset(token)


def create_session_id() -> str:
    return str(uuid.uuid4())[:8]
