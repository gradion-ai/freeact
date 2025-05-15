import datetime
from abc import ABC, abstractmethod
from typing import Any


class Span(ABC):
    @abstractmethod
    def update(
        self,
        name: str | None = None,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        metadata: Any | None = None,
        input: Any | None = None,
        output: Any | None = None,
        status_message: str | None = None,
    ) -> None:
        pass

    @abstractmethod
    def end(self) -> None:
        pass

    @property
    @abstractmethod
    def trace_id(self) -> str | None:
        pass

    @property
    @abstractmethod
    def span_id(self) -> str | None:
        pass


class Trace(ABC):
    @abstractmethod
    def span(
        self,
        name: str,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        metadata: Any | None = None,
        input: Any | None = None,
        output: Any | None = None,
        status_message: str | None = None,
    ) -> Span:
        pass

    @abstractmethod
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

    @abstractmethod
    def end(self) -> None:
        pass

    @property
    @abstractmethod
    def trace_id(self) -> str | None:
        pass


class TracerProvider(ABC):
    @abstractmethod
    def create_trace(
        self,
        name: str,
        user_id: str | None = None,
        session_id: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        metadata: Any | None = None,
        tags: list[str] | None = None,
        start_time: datetime.datetime | None = None,
    ) -> Trace:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass
