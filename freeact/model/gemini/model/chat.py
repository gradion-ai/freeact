import re
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from google import genai
from google.genai.chats import AsyncChat
from google.genai.types import GenerateContentConfig

from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn, StreamRetry
from freeact.model.gemini.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
)

GeminiModelName = Literal["gemini-2.0-flash-exp",]


@dataclass
class GeminiResponse(CodeActModelResponse):
    @property
    def tool_use_id(self) -> str | None:
        return None

    @property
    def tool_use_name(self) -> str | None:
        return None

    @property
    def code(self) -> str | None:
        blocks = self._extract_code_blocks(self.text)

        if not blocks:
            return None

        return "\n\n".join(blocks)

    @staticmethod
    def _extract_code_blocks(text: str):
        pattern = r"```(?:python|tool_code)\s*(.*?)(?:\s*```|\s*$)"
        return re.findall(pattern, text, re.DOTALL)


class GeminiTurn(CodeActModelTurn):
    def __init__(self, chat: AsyncChat, message: str):
        self.chat = chat
        self.message = message

        self._response: str = ""
        self._stream_consumed = False

    async def response(self) -> GeminiResponse:
        if not self._stream_consumed:
            async for _ in self.stream():
                pass
        return GeminiResponse(text=self._response, is_error=False)

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for chunk in self.chat.send_message_stream(self.message):
            text = chunk.text
            if text is not None:
                yield text
                self._response += text

        self._stream_consumed = True


class Gemini(CodeActModel):
    """A `CodeActModel` implementation based on Google's Gemini 2 chat API.

    Args:
        model_name: The specific Gemini 2 model to use
        skill_sources: Skill module sources to include in the system instruction
        temperature: Controls randomness in the model's output (0.0 = deterministic)
        max_tokens: Maximum number of tokens in the model's response
    """

    def __init__(
        self,
        model_name: GeminiModelName = "gemini-2.0-flash-exp",
        skill_sources: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ):
        self._model_name = model_name
        self._client = genai.Client(http_options={"api_version": "v1alpha"})
        self._chat = self._client.aio.chats.create(
            model=model_name,
            config=GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_modalities=["TEXT"],
                system_instruction=SYSTEM_TEMPLATE.format(python_modules=skill_sources or ""),
            ),
        )

    def request(self, user_query: str, **kwargs) -> GeminiTurn:
        return GeminiTurn(self._chat, user_query)

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None, tool_use_name: str | None, **kwargs
    ) -> GeminiTurn:
        template = EXECUTION_OUTPUT_TEMPLATE if not is_error else EXECUTION_ERROR_TEMPLATE
        return GeminiTurn(self._chat, template.format(execution_feedback=feedback))
