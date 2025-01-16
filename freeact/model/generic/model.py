import os
import re
from dataclasses import dataclass
from typing import AsyncIterator

from openai import AsyncOpenAI

from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn, StreamRetry
from freeact.model.generic.prompt import (
    EXECUTION_ERROR_TEMPLATE,
    EXECUTION_OUTPUT_TEMPLATE,
    SYSTEM_TEMPLATE,
)


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
        # return self._extract_code_blocks(self.text)
        x = self._extract_code_blocks_backup(self.text)
        # if x is not None:
        #    return x.replace("\n```\n", "")
        return x

    @staticmethod
    def _extract_code_blocks(text: str) -> str | None:
        # match = re.search(r"```python\n(.*?)(?:```)?", text, re.DOTALL)
        match = re.search(r"```python\n(.*?)(?:```|\Z)", text, re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_code_blocks_backup(text: str) -> str | None:
        match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
        return match.group(1).strip() if match else None


class GenericTurn(CodeActModelTurn):
    def __init__(self, iter: AsyncIterator[str | GenericResponse]):
        self._iter = iter
        self._response: GenericResponse | None = None

    async def response(self) -> GenericResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for elem in self._iter:
            match elem:
                case str():
                    yield elem
                case GenericResponse() as msg:
                    self._response = msg


class GenericModel(CodeActModel):
    def __init__(
        self,
        model_name: str = "accounts/fireworks/models/qwen2p5-coder-32b-instruct",
        skill_sources: str | None = None,
    ):
        self.model_name = model_name
        self._history = [
            {
                "role": "system",
                "content": SYSTEM_TEMPLATE.format(python_modules=skill_sources or ""),
            }
        ]
        self._client = AsyncOpenAI(
            base_url="https://api.fireworks.ai/inference/v1",
            api_key=os.environ.get("FIREWORKS_API_KEY"),
        )

    async def _stream(
        self,
        user_message,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str | GenericResponse]:
        response_text = ""

        messages = self._history + [user_message]

        stream = await self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            # stop=["```\n"],
            stop=["```output", "<|im_start|>"],
            # stop_sequence_included=True
        )

        async for chunk in stream:
            if chunk_text := chunk.choices[0].delta.content:
                response_text += chunk_text
                yield chunk_text

            if chunk.choices[0].finish_reason == "stop":
                # print("Stream terminated by stop sequence")
                # yield "<-- terminated -->"
                pass

        # response_text += "\n```\n"
        # yield "\n```\n"

        response_message = GenericResponse(
            text=response_text,
            is_error=False,
        )

        self._history.append(user_message)
        self._history.append({"role": "assistant", "content": response_text})

        yield response_message

    def request(self, user_query: str, **kwargs) -> GenericTurn:
        user_message = {"role": "user", "content": user_query}
        return GenericTurn(self._stream(user_message, **kwargs))

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None = None, tool_use_name: str | None = None, **kwargs
    ) -> GenericTurn:
        feedback_template = EXECUTION_OUTPUT_TEMPLATE if not is_error else EXECUTION_ERROR_TEMPLATE
        feedback_message = {"role": "user", "content": feedback_template.format(execution_feedback=feedback)}
        return GenericTurn(self._stream(feedback_message, **kwargs))
