import asyncio
import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

import litellm

from freeact.tracing.base import Span, Trace, TracerProvider, TracingConfig


def _get_env_var(
    key: str,
    required: bool = False,
    conversion_fn: Callable[[str], Any] | None = None,
) -> Any:
    """Helper to retrieve and convert environment variables.

    Args:
        key: The environment variable.
        required: If True, raises ValueError when the variable is not set.
        conversion_fn: Function to convert the string value to another type.

    Returns:
        The value of the environment variable, converted if a conversion_fn was provided.

    Raises:
        ValueError: If required is True and the environment variable is not set.
    """
    value = os.getenv(key)
    if value is None and required:
        raise ValueError(f"Environment variable {key} is not set")
    if value is not None and conversion_fn is not None:
        return conversion_fn(value)
    return value


@dataclass
class LangfuseTracingConfig(TracingConfig):
    """Configuration for the [langfuse](https://github.com/langfuse/langfuse) tracing client.
    See [langfuse docs](https://langfuse.com/docs/sdk/python/low-level-sdk) for more information.

    Args:
        public_key: Public API key of Langfuse project. Can be set via `LANGFUSE_PUBLIC_KEY` environment variable.
        secret_key: Secret API key of Langfuse project. Can be set via `LANGFUSE_SECRET_KEY` environment variable.
        host: Host of Langfuse API. Can be set via `LANGFUSE_HOST` environment variable.
        release: Release number/hash of the application to provide analytics grouped by release. Can be set via `LANGFUSE_RELEASE` environment variable.
        debug: Enables debug mode for more verbose logging. Can be set via `LANGFUSE_DEBUG` environment variable.
        threads: Number of consumer threads to execute network requests. Helps scaling the SDK for high load. Only increase this if you run into scaling issues. Can be set via `LANGFUSE_THREADS` environment variable.
        flush_at: Max batch size that's sent to the API. Can be set via `LANGFUSE_FLUSH_AT` environment variable.
        flush_interval: Max delay until a new batch is sent to the API. Can be set via `LANGFUSE_FLUSH_INTERVAL` environment variable.
        max_retries: Max number of retries in case of API/network errors. Can be set via `LANGFUSE_MAX_RETRIES` environment variable.
        timeout_in_s: Timeout of API requests in seconds. Defaults to 20 seconds. Can be set via `LANGFUSE_TIMEOUT_IN_S` environment variable.
        sample_rate: Sampling rate for tracing. If set to 0.2, only 20% of the data will be sent to the backend. Can be set via `LANGFUSE_SAMPLE_RATE` environment variable.
        environment: The tracing environment. Can be any lowercase alphanumeric string with hyphens and underscores that does not start with 'langfuse'. Can bet set via `LANGFUSE_TRACING_ENVIRONMENT` environment variable.
        mask (langfuse.types.MaskFunction): Masking function for 'input' and 'output' fields in events. Function must take a single keyword argument `data` and return a serializable, masked version of the data.
    """

    public_key: str
    secret_key: str
    host: str
    release: str | None = None
    debug: bool = False
    threads: int | None = None
    flush_at: int | None = None
    flush_interval: float | None = None
    max_retries: int | None = None
    timeout_in_s: int | None = None
    sample_rate: float | None = None
    environment: str | None = None
    mask = None

    @classmethod
    def from_env(cls) -> "LangfuseTracingConfig":
        """Creates a LangfuseTracingConfig from environment variables.

        Returns:
            A new LangfuseTracingConfig instance.

        Raises:
            ValueError: If any required environment variables are not set.
        """
        return cls(
            public_key=_get_env_var("LANGFUSE_PUBLIC_KEY", required=True),
            secret_key=_get_env_var("LANGFUSE_SECRET_KEY", required=True),
            host=_get_env_var("LANGFUSE_HOST", required=True),
            release=_get_env_var("LANGFUSE_RELEASE"),
            debug=_get_env_var("LANGFUSE_DEBUG", conversion_fn=lambda x: x.lower() == "true"),
            threads=_get_env_var("LANGFUSE_THREADS", conversion_fn=int),
            flush_at=_get_env_var("LANGFUSE_FLUSH_AT", conversion_fn=int),
            flush_interval=_get_env_var("LANGFUSE_FLUSH_INTERVAL", conversion_fn=float),
            max_retries=_get_env_var("LANGFUSE_MAX_RETRIES", conversion_fn=int),
            timeout_in_s=_get_env_var("LANGFUSE_TIMEOUT_IN_S", conversion_fn=int),
            sample_rate=_get_env_var("LANGFUSE_SAMPLE_RATE", conversion_fn=float),
            environment=_get_env_var("LANGFUSE_TRACING_ENVIRONMENT"),
        )


class LangfuseSpan(Span):
    """Represents a single operation within a trace (e.g. a function call, LLM call, code execution, etc.).

    Args:
        span: The native Langfuse span object to wrap.
    """

    def __init__(self, span):
        self._span = span

    def update(
        self,
        name: str | None = None,
        start_time: dt.datetime | None = None,
        end_time: dt.datetime | None = None,
        metadata: Any | None = None,
        input: Any | None = None,
        output: Any | None = None,
        status_message: str | None = None,
    ) -> None:
        """Updates the span.

        Args:
            name: Name of the span.
            start_time: Start time of the span.
            end_time: End time of the span.
            metadata: Additional metadata associated with the span.
            input: Input data for the span.
            output: Output data from the span.
            status_message: Status message for the span.
        """
        self._span.update(
            name=name,
            start_time=start_time,
            end_time=end_time,
            metadata=metadata,
            input=input,
            output=output,
            status_message=status_message,
        )

    def end(self) -> None:
        """Marks the span as completed. Should be called when the operation represented by this span has completed."""
        self._span.end()

    @property
    def trace_id(self) -> str | None:
        """The ID of the trace this span belongs to.

        Returns:
            The trace ID or None if not available.
        """
        return self._span.trace_id

    @property
    def span_id(self) -> str | None:
        """The ID of this span.

        Returns:
            The span ID or None if not available.
        """
        return self._span.id

    @property
    def native(self):
        return self._span


class LangfuseTrace(Trace):
    """Represents a complete trace of operations (e.g. a single agent run) in langfuse.

    Args:
        trace: The native Langfuse trace object to wrap.
    """

    def __init__(self, trace):
        """Initialize a new LangfuseTrace.

        Args:
            trace: The native Langfuse trace object to wrap.
        """
        self._trace = trace

    def update(
        self,
        name: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        metadata: Any | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Updates the trace.

        Args:
            name: Name of the trace.
            user_id: User identifier associated with this trace.
            session_id: Session identifier associated with this trace.
            input: Input data for the trace.
            output: Output data from the trace.
            metadata: Additional metadata associated with the trace.
            tags: List of tags to associate with this trace.
        """
        self._trace.update(
            name=name,
            user_id=user_id,
            session_id=session_id,
            input=input,
            output=output,
            metadata=metadata,
            tags=tags,
        )

    def span(
        self,
        name: str,
        start_time: dt.datetime | None = None,
        end_time: dt.datetime | None = None,
        metadata: Any | None = None,
        input: Any | None = None,
        output: Any | None = None,
        status_message: str | None = None,
    ) -> LangfuseSpan:
        """Creates a new span within this trace.

        Args:
            name: The name of the span.
            start_time: Start time of the span.
            end_time: End time of the span.
            metadata: Additional metadata associated with the span.
            input: Input data for the span.
            output: Output data from the span.
            status_message: Status message for the span.

        Returns:
            A new ['LangfuseSpan'][freeact.tracing.langfuse.LangfuseSpan] instance.
        """
        span_obj = self._trace.span(
            name=name,
            start_time=start_time,
            end_time=end_time,
            metadata=metadata,
            input=input,
            output=output,
            status_message=status_message,
        )
        return LangfuseSpan(span_obj)

    def end(self) -> None:
        """Marks the trace as complete. Note: This is a no-op in the Langfuse SDK as trace end is handled automatically."""
        pass

    @property
    def trace_id(self) -> str | None:
        """The ID of this trace.

        Returns:
            The trace ID or None if not available.
        """
        return self._trace.id

    @property
    def native(self):
        return self._trace


class LangfuseTracer(TracerProvider):
    """A [langfuse](https://github.com/langfuse/langfuse)-based tracer.

    This tracer uses the langfuse [low-level Python SDK](https://langfuse.com/docs/sdk/python/low-level-sdk) to
    create traces and spans, logging them to the langfuse backend.

    It also configures `litellm` to use langfuse for tracing LLM invocations.

    This tracer supports grouping of traces by session ids.

    Args:
        config: The [`LangfuseTracingConfig`][freeact.tracing.langfuse.LangfuseTracingConfig] config to use.
    """

    def __init__(
        self,
        config: LangfuseTracingConfig,
    ):
        from langfuse import Langfuse

        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

        self._client = Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key,
            host=config.host,
            environment=config.environment,
            release=config.release,
            debug=config.debug,
            threads=config.threads,
            flush_at=config.flush_at,
            flush_interval=config.flush_interval,
            max_retries=config.max_retries,
            timeout=config.timeout_in_s,
            sample_rate=config.sample_rate,
            mask=config.mask,
        )
        self._pool = ThreadPoolExecutor(max_workers=1)

    @property
    def client(self):
        """The underlying Langfuse client."""
        return self._client

    def create_trace(
        self,
        name: str,
        user_id: str | None = None,
        session_id: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        metadata: Any | None = None,
        tags: list[str] | None = None,
        start_time: dt.datetime | None = None,
    ) -> LangfuseTrace:
        """Creates a new trace in langfuse.

        Args:
            name: The name of the trace.
            user_id: User identifier to associate with this trace.
            session_id: Session identifier to associate with this trace.
            input: Input data for the trace.
            output: Output data from the trace.
            metadata: Additional metadata associated with the trace.
            tags: List of tags to associate with this trace.
            start_time: Start time of the trace.

        Returns:
            A new ['LangfuseTrace'][freeact.tracing.langfuse.LangfuseTrace] instance.
        """
        trace = self._client.trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            input=input,
            output=output,
            metadata=metadata,
            tags=tags,
            timestamp=start_time,
        )
        return LangfuseTrace(trace)

    async def shutdown(self) -> None:
        """Shuts down the tracer provider.

        Should be called when the application is shutting down to ensure that all pending traces and spans are completed and flushed.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._pool, self._client.shutdown)
        self._pool.shutdown(wait=True)
