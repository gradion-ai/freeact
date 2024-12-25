from contextlib import asynccontextmanager
from typing import AsyncIterator

from google import genai
from google.genai.live import AsyncSession

from freeact.model.base import CodeActModel, CodeActModelTurn, StreamRetry
from freeact.model.gemini.model.chat import GeminiModelName, GeminiResponse
from freeact.model.gemini.prompt import EXECUTION_ERROR_TEMPLATE, EXECUTION_OUTPUT_TEMPLATE, SYSTEM_TEMPLATE


class GeminiLiveTurn(CodeActModelTurn):
    def __init__(self, iter: AsyncIterator[str | GeminiResponse]):
        self._iter = iter
        self._response: GeminiResponse | None = None

    async def response(self) -> GeminiResponse:
        async for elem in self.stream():
            pass
        return self._response  # type: ignore

    async def stream(self, emit_retry: bool = False) -> AsyncIterator[str | StreamRetry]:
        async for elem in self._iter:
            match elem:
                case str():
                    yield elem
                case GeminiResponse() as msg:
                    self._response = msg


@asynccontextmanager
async def GeminiLive(
    model_name: GeminiModelName = "gemini-2.0-flash-exp",
    skill_sources: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
):
    """
    Context manager for a `CodeActModel` implementation based on Google's Gemini 2 live API.

    Args:
        model_name: The specific Gemini 2 model to use
        skill_sources: Skill module sources to include in the system instruction.
        temperature: Controls randomness in the model's output (0.0 = deterministic)
        max_tokens: Maximum number of tokens in the model's response

    Example:
        ```python
        async with GeminiLive(model_name="gemini-2.0-flash-exp", skill_sources=skill_sources) as model:
            # use model with active session to Gemini 2 live API
            agent = CodeActAgent(model=model, ...)
        ```
    """

    client = genai.Client(http_options={"api_version": "v1alpha"})
    config = {
        "tools": [],
        "generation_config": {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "response_modalities": ["TEXT"],
            "system_instruction": SYSTEM_TEMPLATE.format(
                python_modules=skill_sources or "",
            ),
        },
    }

    async with client.aio.live.connect(model=model_name, config=config) as session:
        yield _GeminiLive(session)


class _GeminiLive(CodeActModel):
    def __init__(self, session: AsyncSession):
        self._session = session

    def request(self, user_query: str, **kwargs) -> GeminiLiveTurn:
        return GeminiLiveTurn(self._turn(user_query))

    def feedback(
        self, feedback: str, is_error: bool, tool_use_id: str | None, tool_use_name: str | None, **kwargs
    ) -> GeminiLiveTurn:
        template = EXECUTION_OUTPUT_TEMPLATE if not is_error else EXECUTION_ERROR_TEMPLATE
        return GeminiLiveTurn(self._turn(template.format(execution_feedback=feedback)))

    async def _turn(self, message: str) -> AsyncIterator[str | GeminiResponse]:
        await self._session.send(message, end_of_turn=True)

        accumulated_text = ""

        async for response in self._session.receive():
            server_content = response.server_content

            if server_content.turn_complete:
                yield GeminiResponse(text=accumulated_text, is_error=False)

            model_turn = server_content.model_turn

            if model_turn:
                for part in model_turn.parts:
                    text = part.text
                    if text is not None:
                        accumulated_text += text
                        yield text
