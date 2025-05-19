import datetime as dt
from typing import Any

from freeact.tracing.base import Span, Trace, Tracer


class NoopSpan(Span):
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
        pass

    async def end(self) -> None:
        pass

    @property
    def trace_id(self) -> str | None:
        return None

    @property
    def span_id(self) -> str | None:
        return None


class NoopTrace(Trace):
    async def span(
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
        pass

    async def end(self) -> None:
        pass

    @property
    def trace_id(self) -> str | None:
        return None


class NoopTracer(Tracer):
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
    ) -> NoopTrace:
        return NoopTrace()

    def shutdown(self) -> None:
        pass
