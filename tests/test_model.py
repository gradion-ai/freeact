from typing import AsyncIterator, List

from freeact.agent import CodeActModel, CodeActModelCall, CodeActModelResponse
from freeact.skills import SkillInfo


class MockModelResponse(CodeActModelResponse):
    def __init__(
        self, text: str, code: str | None = None, tool_use_id: str | None = None, tool_use_name: str | None = None
    ):
        super().__init__(text=text)
        self._code = code
        self._tool_use_id = tool_use_id
        self._tool_use_name = tool_use_name

    @property
    def tool_use_id(self) -> str | None:
        return self._tool_use_id

    @property
    def tool_use_name(self) -> str | None:
        return self._tool_use_name

    @property
    def code(self) -> str | None:
        return self._code


class MockModelCall(CodeActModelCall):
    def __init__(self, response: CodeActModelResponse):
        self.response_obj = response
        self.stream_chunks = ["chunk1", "chunk2"]

    async def response(self) -> CodeActModelResponse:
        return self.response_obj

    async def stream(self) -> AsyncIterator[str]:
        for chunk in self.stream_chunks:
            yield chunk


class MockModel(CodeActModel):
    def __init__(self, responses: List[MockModelResponse]):
        self.responses = responses
        self.current_response = 0

    def request(self, user_query: str, skill_infos: List[SkillInfo], **kwargs) -> MockModelCall:
        response = self.responses[self.current_response]
        self.current_response += 1
        return MockModelCall(response)

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None, tool_use_name: str | None, **kwargs
    ) -> MockModelCall:
        response = self.responses[self.current_response]
        self.current_response += 1
        return MockModelCall(response)


# Only mock model definition at the moment (used by agent tests) ...
