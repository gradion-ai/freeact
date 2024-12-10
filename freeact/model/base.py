from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, List

from freeact.skills import SkillInfo


@dataclass
class AssistantMessage(ABC):
    content: str

    @property
    @abstractmethod
    def tool_use_id(self) -> str | None: ...

    @property
    @abstractmethod
    def tool_use_name(self) -> str | None: ...

    @property
    @abstractmethod
    def code(self) -> str | None: ...


class CodeActModel(ABC):
    @abstractmethod
    def stream_request(
        self,
        user_query: str,
        skill_infos: List[SkillInfo],
        **kwargs,
    ) -> AsyncIterator[str | AssistantMessage]: ...

    @abstractmethod
    def stream_feedback(
        self,
        feedback: str,
        is_error: bool,
        tool_use_id: str | None,
        tool_use_name: str | None,
        **kwargs,
    ) -> AsyncIterator[str | AssistantMessage]: ...
