import asyncio
import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

import litellm

from freeact.tracing.base import Span, Trace, TracerProvider, TracingConfig


def _get_env_var(key: str, required: bool = False, conversion_fn: Callable[[str], Any] | None = None) -> Any:
    value = os.getenv(key)
    if value is None and required:
        raise ValueError(f"Environment variable {key} is not set")
    if value is not None and conversion_fn is not None:
        return conversion_fn(value)
    return value


@dataclass
class LangfuseTracingConfig(TracingConfig):
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
        return cls(
            public_key=_get_env_var("LANGFUSE_PUBLIC_KEY", required=True),
            secret_key=_get_env_var("LANGFUSE_SECRET_KEY", required=True),
            host=_get_env_var("LANGFUSE_HOST", required=True),
            environment=_get_env_var("LANGFUSE_ENVIRONMENT"),
            release=_get_env_var("LANGFUSE_RELEASE"),
            debug=_get_env_var("LANGFUSE_DEBUG", conversion_fn=lambda x: x.lower() == "true"),
            threads=_get_env_var("LANGFUSE_THREADS", conversion_fn=int),
            max_retries=_get_env_var("LANGFUSE_MAX_RETRIES", conversion_fn=int),
            timeout_in_s=_get_env_var("LANGFUSE_TIMEOUT_IN_S", conversion_fn=int),
            sample_rate=_get_env_var("LANGFUSE_SAMPLE_RATE", conversion_fn=float),
        )


class LangfuseSpan(Span):
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
        self._span.end()

    @property
    def trace_id(self) -> str | None:
        return self._span.trace_id

    @property
    def span_id(self) -> str | None:
        return self._span.id

    @property
    def native(self):
        return self._span


class LangfuseTrace(Trace):
    def __init__(self, trace):
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
        pass

    @property
    def trace_id(self) -> str | None:
        return self._trace.id

    @property
    def native(self):
        return self._trace


class LangfuseTracer(TracerProvider):
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
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._pool, self._client.shutdown)
        self._pool.shutdown(wait=True)
