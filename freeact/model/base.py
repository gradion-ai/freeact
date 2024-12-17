from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class CodeActModelResponse(ABC):
    text: str
    is_error: bool

    @property
    @abstractmethod
    def tool_use_id(self) -> str | None: ...

    @property
    @abstractmethod
    def tool_use_name(self) -> str | None: ...

    @property
    @abstractmethod
    def code(self) -> str | None: ...


@dataclass
class StreamRetry:
    cause: str
    retry_wait_time: float


class CodeActModelTurn(ABC):
    @abstractmethod
    async def response(self) -> CodeActModelResponse: ...

    @abstractmethod
    def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]: ...


class CodeActModel(ABC):
    @abstractmethod
    def request(
        self,
        user_query: str,
        **kwargs,
    ) -> CodeActModelTurn: ...

    @abstractmethod
    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> CodeActModelTurn: ...
