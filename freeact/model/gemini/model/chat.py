import re
from dataclasses import dataclass
from typing import AsyncIterator, Literal

from google import genai
from google.genai.chats import AsyncChat
from google.genai.types import GenerateContentConfig, ThinkingConfig

from freeact.model.base import CodeActModel, CodeActModelResponse, CodeActModelTurn, StreamRetry
from freeact.model.gemini.prompt import default, thinking

GeminiModelName = Literal[
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite-preview-02-05",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-thinking-exp",
    "gemini-2.0-flash-thinking-exp-01-21",
]


@dataclass
class GeminiResponse(CodeActModelResponse):
    thoughts: str = ""

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
        pattern = r"```(?:python|tool_code|tool)\s*(.*?)(?:\s*```|\s*$)"
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
        # TODO: include token usage data into response object
        return GeminiResponse(text=self._response, is_error=False)

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for chunk in await self.chat.send_message_stream(self.message):
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
        **kwargs: Additional keyword arguments to pass to the Google Gen AI client.
    """

    def __init__(
        self,
        model_name: GeminiModelName = "gemini-2.0-flash",
        skill_sources: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs,
    ):
        is_thinking_model = "thinking" in model_name.lower()

        if is_thinking_model:
            # ------------------------------------------------------
            #  EXPERIMENTAL
            # ------------------------------------------------------
            self.system_template = thinking.SYSTEM_TEMPLATE.format(
                python_modules=skill_sources or "",
                python_packages=thinking.EXAMPLE_PYTHON_PACKAGES,
                rest_apis=thinking.EXAMPLE_REST_APIS,
            )
            self.execution_error_template = thinking.EXECUTION_ERROR_TEMPLATE
            self.execution_output_template = thinking.EXECUTION_OUTPUT_TEMPLATE
            self.thinking_config = ThinkingConfig(include_thoughts=True)
        else:
            self.system_template = default.SYSTEM_TEMPLATE.format(python_modules=skill_sources or "")
            self.execution_error_template = default.EXECUTION_ERROR_TEMPLATE
            self.execution_output_template = default.EXECUTION_OUTPUT_TEMPLATE
            self.thinking_config = None

        self._client = genai.Client(**kwargs, http_options={"api_version": "v1alpha"})
        self._chat = self._client.aio.chats.create(
            model=model_name,
            config=GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_modalities=["TEXT"],
                system_instruction=self.system_template,
                thinking_config=self.thinking_config,
            ),
        )

    def request(self, user_query: str, **kwargs) -> GeminiTurn:
        return GeminiTurn(self._chat, user_query)

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None, tool_use_name: str | None, **kwargs
    ) -> GeminiTurn:
        feedback_template = self.execution_error_template if is_error else self.execution_output_template
        return GeminiTurn(self._chat, feedback_template.format(execution_feedback=feedback))
