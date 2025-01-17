import re
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict

from openai import AsyncOpenAI

from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn, StreamRetry


@dataclass
class GenericModelResponse(CodeActModelResponse):
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


class GenericModelTurn(CodeActModelTurn):
    def __init__(self, iter: AsyncIterator[str | GenericModelResponse]):
        self._iter = iter
        self._response: GenericModelResponse | None = None

    async def response(self) -> GenericModelResponse:
        if self._response is None:
            async for _ in self.stream():
                pass
        return self._response  # type: ignore

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for elem in self._iter:
            match elem:
                case str():
                    yield elem
                case GenericModelResponse() as msg:
                    self._response = msg


class GenericModel(CodeActModel):
    """A generic implementation of a code action model based on the [OpenAI Python SDK](https://github.com/openai/openai-python).

    This class can be used to integrate any model that is accessible via the OpenAI Python SDK.
    See [qwen](https://github.com/gradion-ai/freeact/tree/main/freeact/model/qwen) for an implementation example.

    Args:
        model_name: The provider-specific name of the model.
        system_message: The system message to guide the model to generate code actions.
        execution_output_template: Prompt template for formatting successful execution feedback.
            Must define an `{execution_feedback}` placeholder.
        execution_error_template: Prompt template for formatting execution error feedback.
            Must define an `{execution_feedback}` placeholder.
        run_kwargs: Optional dictionary of additional arguments passed to the model's
            [`request`][freeact.model.base.CodeActModel.request] and
            [`feedback`][freeact.model.base.CodeActModel.feedback] methods.
        **kwargs: Additional keyword arguments passed to `AsyncOpenAI` client constructor.
            (e.g. `api_key`, `base_url`, ..., etc.).
    """

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

        # TODO: alternative solution for models that don't support system messages
        self._history = [{"role": "system", "content": system_message}]
        self._client = AsyncOpenAI(**kwargs)

    async def _stream(
        self,
        user_message,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str | GenericModelResponse]:
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

        response_message = GenericModelResponse(
            text=response_text,
            is_error=False,
        )

        self._history.append(user_message)
        self._history.append({"role": "assistant", "content": response_text})

        yield response_message

    def request(self, user_query: str, **kwargs) -> GenericModelTurn:
        user_message = {"role": "user", "content": user_query}
        return GenericModelTurn(self._stream(user_message, **self.run_kwargs, **kwargs))

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None = None, tool_use_name: str | None = None, **kwargs
    ) -> GenericModelTurn:
        feedback_template = self.execution_output_template if not is_error else self.execution_error_template
        feedback_message = {"role": "user", "content": feedback_template.format(execution_feedback=feedback)}
        return GenericModelTurn(self._stream(feedback_message, **self.run_kwargs, **kwargs))
