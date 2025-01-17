import re
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict

from openai import AsyncOpenAI

from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn, StreamRetry


@dataclass
class OpenAIClientResponse(CodeActModelResponse):
    @property
    def tool_use_id(self) -> str | None:
        return None

    @property
    def tool_use_name(self) -> str | None:
        return None

    @property
    def code(self) -> str | None:
        return self._extract_code_block(self.text)

    @staticmethod
    def _extract_code_block(text: str) -> str | None:
        match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
        return match.group(1).strip() if match else None


class OpenAIClientTurn(CodeActModelTurn):
    def __init__(self, iter: AsyncIterator[str | OpenAIClientResponse]):
        self._iter = iter
        self._response: OpenAIClientResponse | None = None

    async def response(self) -> OpenAIClientResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for elem in self._iter:
            match elem:
                case str():
                    yield elem
                case OpenAIClientResponse() as msg:
                    self._response = msg


class OpenAIClient(CodeActModel):
    def __init__(
        self,
        model_name: str,
        system_message: str,
        execution_output_template: str,
        execution_error_template: str,
        run_kwargs: Dict[str, Any] | None = None,
        **kwargs,
    ):
        self.model_name = model_name
        self.execution_output_template = execution_output_template
        self.execution_error_template = execution_error_template
        self.run_kwargs = run_kwargs or {}

        self._history = [{"role": "system", "content": system_message}]
        self._client = AsyncOpenAI(**kwargs)

    async def _stream(
        self,
        user_message,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str | OpenAIClientResponse]:
        messages = self._history + [user_message]
        response_text = ""

        stream = await self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk_text := chunk.choices[0].delta.content:
                response_text += chunk_text
                yield chunk_text

        response_message = OpenAIClientResponse(
            text=response_text,
            is_error=False,
        )

        self._history.append(user_message)
        self._history.append({"role": "assistant", "content": response_text})

        yield response_message

    def request(self, user_query: str, **kwargs) -> OpenAIClientTurn:
        user_message = {"role": "user", "content": user_query}
        return OpenAIClientTurn(self._stream(user_message, **self.run_kwargs, **kwargs))

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None = None, tool_use_name: str | None = None, **kwargs
    ) -> OpenAIClientTurn:
        feedback_template = self.execution_output_template if not is_error else self.execution_error_template
        feedback_message = {"role": "user", "content": feedback_template.format(execution_feedback=feedback)}
        return OpenAIClientTurn(self._stream(feedback_message, **self.run_kwargs, **kwargs))
