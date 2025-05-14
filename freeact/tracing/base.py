import datetime
from abc import ABC, abstractmethod
from typing import Any


class TracingConfig(ABC):
    """Base configuration class for tracing providers."""

    pass


class Span(ABC):
    """Represents a single operation within a trace. E.g. a function call, LLM call, code execution, etc."""

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
        pass

    @abstractmethod
    def end(self) -> None:
        """Marks the span as completed. Should be called when the operation represented by this span has completed."""
        pass

    @property
    @abstractmethod
    def trace_id(self) -> str | None:
        """The ID of the trace this span belongs to.

        Returns:
            The trace ID or None if not available.
        """
        pass

    @property
    @abstractmethod
    def span_id(self) -> str | None:
        """The ID of this span.

        Returns:
            The span ID or None if not available.
        """
        pass


class Trace(ABC):
    """Represents a complete trace of operations (e.g. a single agent run)."""

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
            A new ['Span'][freeact.tracing.base.Span] instance.
        """
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
        """Updates the trace.

        Args:
            name: Name of the trace.
            user_id: User identifier associated with this trace.
            session_id: Session identifier associated with this trace.
            input: Input data for the overall operation.
            output: Output data from the overall operation.
            metadata: Additional metadata associated with the trace.
            tags: List of tags to associate with this trace.
        """
        pass

    @abstractmethod
    def end(self) -> None:
        """Marks the trace as completed. Should be called when all operations within this trace have completed."""
        pass

    @property
    @abstractmethod
    def trace_id(self) -> str | None:
        """The ID of this trace.

        Returns:
            The trace ID or None if not available.
        """
        pass


class TracerProvider(ABC):
    """Provider for creating and managing traces and spans."""

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
        """Creates a new trace.

        Args:
            name: The name of the trace.
            user_id: User identifier to associate with this trace.
            session_id: Session identifier to associate with this trace.
            input: Input data for the overall operation.
            output: Output data from the overall operation.
            metadata: Additional metadata associated with the trace.
            tags: List of tags to associate with this trace.
            start_time: Start time of the trace.

        Returns:
            A new ['Trace'][freeact.tracing.base.Trace] instance.
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shuts down the tracer provider.

        Should be called when the application is shutting down to ensure that all pending traces and spans are completed and flushed.
        """
        pass
