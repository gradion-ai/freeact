from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, List

from freeact.skills import SkillInfo


@dataclass
class CodeActModelResponse(ABC):
    text: str

    @property
    @abstractmethod
    def tool_use_id(self) -> str | None: ...

    @property
    @abstractmethod
    def tool_use_name(self) -> str | None: ...

    @property
    @abstractmethod
    def code(self) -> str | None: ...


class CodeActModelCall(ABC):
    @abstractmethod
    async def response(self) -> CodeActModelResponse: ...

    @abstractmethod
    def stream(self) -> AsyncIterator[str]: ...


class CodeActModel(ABC):
    @abstractmethod
    def request(
        self,
        user_query: str,
        skill_infos: List[SkillInfo],
        **kwargs,
    ) -> CodeActModelCall: ...

    @abstractmethod
    def feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> CodeActModelCall: ...
