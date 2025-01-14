import os
import re
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn, StreamRetry
from freeact.model.generic.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
)
from openai import AsyncOpenAI

GenericModelName = Literal["accounts/fireworks/models/qwen2p5-coder-32b-instruct"]


@dataclass
class GenericResponse(CodeActModelResponse):
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


class QwenTurn(CodeActModelTurn):
    def __init__(self, client: AsyncOpenAI, messages: list[dict], temperature: float, max_tokens: int):
        self.client = client
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._response: str = ""
        self._stream_consumed = False

    async def response(self) -> GenericResponse:
        if not self._stream_consumed:
            async for _ in self.stream():
                pass
        # TODO: include token usage data into response object
        return GenericResponse(text=self._response, is_error=False)

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        response = await self.client.chat.completions.create(
            model="accounts/fireworks/models/qwen2p5-coder-32b-instruct",
            messages=self.messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices[0].delta.content is not None:
                text = chunk.choices[0].delta.content
                yield text
                self._response += text

        # Add the assistant's response to the message history after streaming is complete
        self.messages.append({"role": "assistant", "content": self._response})
        self._stream_consumed = True


class Qwen(CodeActModel):
    """A `CodeActModel` implementation based on Fireworks' Qwen model.

    Args:
        model_name: The specific Qwen model to use
        skill_sources: Skill module sources to include in the system instruction
        temperature: Controls randomness in the model's output (0.0 = deterministic)
        max_tokens: Maximum number of tokens in the model's response
    """

    def __init__(
        self,
        model_name: GenericModelName = "accounts/fireworks/models/qwen2p5-coder-32b-instruct",
        skill_sources: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ):
        self._model_name = model_name
        self._client = AsyncOpenAI(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=os.environ.get("FIREWORKS_API_KEY"),
        )
        self._messages = [
            {"role": "system", "content": SYSTEM_TEMPLATE.format(python_modules=skill_sources or "")}
        ]
        self._temperature = temperature
        self._max_tokens = max_tokens

    def request(self, user_query: str, **kwargs) -> QwenTurn:
        self._messages.append({"role": "user", "content": user_query})
        return QwenTurn(self._client, self._messages, self._temperature, self._max_tokens)

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None, tool_use_name: str | None, **kwargs
    ) -> QwenTurn:
        template = EXECUTION_OUTPUT_TEMPLATE if not is_error else EXECUTION_ERROR_TEMPLATE
        feedback_message = {"role": "user", "content": template.format(execution_feedback=feedback)}
        self._messages.append(feedback_message)
        return QwenTurn(self._client, self._messages, self._temperature, self._max_tokens)
