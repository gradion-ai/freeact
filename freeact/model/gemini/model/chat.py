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
    PREAMBLE,
    PREAMBLE_THINKING,
    SYSTEM_TEMPLATE,
)

GeminiModelName = Literal[
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-thinking-exp-1219",
]


@dataclass
class GeminiResponse(CodeActModelResponse):
    thoughts: str

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
            blocks = self._extract_code_blocks(self.thoughts)

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

        self._thoughts: str = ""
        self._response: str = ""
        self._stream_consumed = False

    async def response(self) -> GeminiResponse:
        if not self._stream_consumed:
            async for _ in self.stream():
                pass
        return GeminiResponse(text=self._response, thoughts=self._thoughts, is_error=False)

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for chunk in self.chat.send_message_stream(self.message):
            text = chunk.text
            if text is not None:
                yield text
                self._response += text

        self._stream_consumed = True


class GeminiThinkingTurn(GeminiTurn):
    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        thinking = True
        yield "-- Thoughts --\n\n"

        async for chunk in self.chat.send_message_stream(self.message):
            if chunk.text is None:
                candidate = chunk.candidates[0]
                if candidate.content and candidate.content.parts:
                    chunk_text = candidate.content.parts[0].text
                    yield chunk_text
                    self._thoughts += chunk_text
            elif thinking:
                thinking = False
                yield "\n\n-- Response --\n\n"

            if not thinking:
                text = chunk.text
                if text is not None:
                    yield text
                    self._response += text

        self._stream_consumed = True


class Gemini(CodeActModel):
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
                candidate_count=1,
                response_modalities=["TEXT"],
                system_instruction=self._system_instruction(skill_sources),
            ),
        )

    def request(self, user_query: str, **kwargs) -> GeminiTurn | GeminiThinkingTurn:
        return self._create_turn(self._chat, user_query)

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None, tool_use_name: str | None, **kwargs
    ) -> GeminiTurn | GeminiThinkingTurn:
        template = EXECUTION_OUTPUT_TEMPLATE if not is_error else EXECUTION_ERROR_TEMPLATE
        return self._create_turn(self._chat, template.format(execution_feedback=feedback))

    def _system_instruction(self, skill_sources: str | None) -> str:
        system_preamble = PREAMBLE_THINKING if self._model_name == "gemini-2.0-flash-thinking-exp-1219" else PREAMBLE
        return SYSTEM_TEMPLATE.format(preamble=system_preamble, python_modules=skill_sources or "")

    def _create_turn(self, chat: AsyncChat, message: str) -> GeminiTurn | GeminiThinkingTurn:
        if self._model_name == "gemini-2.0-flash-thinking-exp-1219":
            return GeminiThinkingTurn(chat, message)
        else:
            return GeminiTurn(chat, message)
