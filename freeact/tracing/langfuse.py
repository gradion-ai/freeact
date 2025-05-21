import datetime as dt
import os
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

    Accepts all [Langfuse configuration options](https://python.reference.langfuse.com/langfuse/decorators#LangfuseDecorator.configure).
    Configuration options can be provided as parameters to `configure()` or via environment variables.

    Args:
        **kwargs: Langfuse configuration parameters.
    """

    def __init__(
        self,
        **kwargs,
    ):
        from langfuse import Langfuse

        # we explicitly require these configuration parameters to be passed or set in the environment,
        # as Langfuse by default simply logs a warning if the parameters are not provided.
        public_key = self._get_config_param(
            param_name="public_key",
            param_value=kwargs.pop("public_key", None),
            env_var_name="LANGFUSE_PUBLIC_KEY",
        )
        secret_key = self._get_config_param(
            param_name="secret_key",
            param_value=kwargs.pop("secret_key", None),
            env_var_name="LANGFUSE_SECRET_KEY",
        )
        host = self._get_config_param(
            param_name="host",
            param_value=kwargs.pop("host", None),
            env_var_name="LANGFUSE_HOST",
        )

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

    def _get_config_param(self, param_name: str, param_value: Any | None, env_var_name: str) -> str:
        value = param_value or os.getenv(env_var_name)
        if value is None:
            raise ValueError(
                f"Langfuse configuration parameter `{param_name}` is missing. Provide it as an argument or set the `{env_var_name}` environment variable."
            )
        if not isinstance(value, str):
            raise ValueError(f"Langfuse configuration parameter `{param_name}` must be a non-empty string.")
        return value

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
