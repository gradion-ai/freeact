import datetime as dt
from typing import Any

import litellm
from ipybox.utils import arun
from langfuse.client import StatefulSpanClient, StatefulTraceClient

from freeact.tracing.base import Span, Trace, Tracer


class LangfuseSpan(Span):
    def __init__(self, span: StatefulSpanClient):
        self._span = span

    async def update(
        self,
        name: str | None = None,
        start_time: dt.datetime | None = None,
        end_time: dt.datetime | None = None,
        metadata: Any | None = None,
        input: Any | None = None,
        output: Any | None = None,
        status_message: str | None = None,
    ) -> None:
        await arun(
            self._span.update,
            name=name,
            start_time=start_time,
            end_time=end_time,
            metadata=metadata,
            input=input,
            output=output,
            status_message=status_message,
        )

    async def end(self) -> None:
        await arun(self._span.end)

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
    def __init__(self, trace: StatefulTraceClient):
        self._trace = trace

    async def update(
        self,
        name: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        metadata: Any | None = None,
        tags: list[str] | None = None,
    ) -> None:
        await arun(
            self._trace.update,
            name=name,
            user_id=user_id,
            session_id=session_id,
            input=input,
            output=output,
            metadata=metadata,
            tags=tags,
        )

    async def span(
        self,
        name: str,
        start_time: dt.datetime | None = None,
        end_time: dt.datetime | None = None,
        metadata: Any | None = None,
        input: Any | None = None,
        output: Any | None = None,
        status_message: str | None = None,
    ) -> LangfuseSpan:
        span = await arun(
            self._trace.span,
            name=name,
            start_time=start_time,
            end_time=end_time,
            metadata=metadata,
            input=input,
            output=output,
            status_message=status_message,
        )
        return LangfuseSpan(span)

    async def end(self) -> None:
        pass

    @property
    def trace_id(self) -> str | None:
        return self._trace.id

    @property
    def native(self):
        return self._trace


class LangfuseTracer(Tracer):
    """A [langfuse](https://github.com/langfuse/langfuse)-based tracer.

    This tracer uses the Langfuse low-level Python SDK (https://langfuse.com/docs/sdk/python/low-level-sdk)
    to create trace data and transmit it to the Langfuse backend.

    Automatically configures `litellm` to route all LLM invocation telemetry to the Langfuse backend.

    Supports grouping of traces using a session identifier.

    Args:
        public_key: Public API key of the Langfuse project.
        secret_key: Secret API key of the Langfuse project.
        host: Host of the Langfuse API.
        **kwargs: Additional keyword arguments passed to the Langfuse client.
    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str,
        **kwargs,
    ):
        from langfuse import Langfuse

        self._litellm_success_callback_registered = False
        self._litellm_failure_callback_registered = False

        if "langfuse" not in litellm.success_callback:
            litellm.success_callback.append("langfuse")
            self._litellm_success_callback_registered = True

        if "langfuse" not in litellm.failure_callback:
            litellm.failure_callback.append("langfuse")
            self._litellm_failure_callback_registered = True

        self._client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            **kwargs,
        )

    @property
    def client(self):
        return self._client

    async def trace(
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
        trace = await arun(
            self._client.trace,
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

    def shutdown(self) -> None:
        if self._litellm_success_callback_registered:
            litellm.success_callback = [c for c in litellm.success_callback if c != "langfuse"]

        if self._litellm_failure_callback_registered:
            litellm.failure_callback = [c for c in litellm.failure_callback if c != "langfuse"]

        self._client.flush()
