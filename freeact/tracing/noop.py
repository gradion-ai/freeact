import datetime as dt
from typing import Any

from freeact.tracing.base import Span, Trace, TracerProvider


class NoopSpan(Span):
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
        pass

    def end(self) -> None:
        pass

    @property
    def trace_id(self) -> str | None:
        return None

    @property
    def span_id(self) -> str | None:
        return None


class NoopTrace(Trace):
    def span(
        self,
        name: str,
        start_time: dt.datetime | None = None,
        end_time: dt.datetime | None = None,
        metadata: Any | None = None,
        input: Any | None = None,
        output: Any | None = None,
        status_message: str | None = None,
    ) -> NoopSpan:
        return NoopSpan()

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
        pass

    def end(self) -> None:
        pass

    @property
    def trace_id(self) -> str | None:
        return None


class NoopTracer(TracerProvider):
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
    ) -> NoopTrace:
        return NoopTrace()

    async def shutdown(self) -> None:
        pass
